import random
import smtplib
import logging
import threading
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

from app.database import supabase
from app.security import hash_password, verify_password, create_access_token, get_current_user
from app.schemas import SignupRequest, LoginRequest, TokenResponse, RequestPasswordReset, VerifyPasswordReset
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("paperbanao")

# --- Login rate limiting (in-memory) ---
# Tracks failed attempts per username. After MAX_LOGIN_ATTEMPTS failures,
# that username is locked out for LOCKOUT_DURATION. This is intentionally
# simple (no Redis/external store) since the app runs as a single instance;
# if it's ever scaled to multiple instances, this state won't be shared
# across them and each instance would track its own counts — an acceptable
# trade-off at this scale, but worth revisiting if that changes.
_login_lock = threading.Lock()
_login_attempts = {}  # username -> {"count": int, "locked_until": datetime | None}
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(seconds=60)


def _check_rate_limit(username: str):
    with _login_lock:
        record = _login_attempts.get(username)
        if record and record["locked_until"]:
            now = datetime.now(timezone.utc)
            if now < record["locked_until"]:
                remaining = int((record["locked_until"] - now).total_seconds())
                raise HTTPException(429, f"Too many failed attempts. Try again in {remaining}s.")
            _login_attempts[username] = {"count": 0, "locked_until": None}


def _record_failed_login(username: str):
    with _login_lock:
        record = _login_attempts.setdefault(username, {"count": 0, "locked_until": None})
        record["count"] += 1
        if record["count"] >= MAX_LOGIN_ATTEMPTS:
            record["locked_until"] = datetime.now(timezone.utc) + LOCKOUT_DURATION
            record["count"] = 0


def _record_successful_login(username: str):
    with _login_lock:
        _login_attempts.pop(username, None)


@router.get("/me")
def get_me(user: dict = Depends(get_current_user)):
    """Lets the frontend show usage/Pro status without re-decoding the JWT itself."""
    is_pro_effective = False
    if user.get("pro_expires_at"):
        try:
            is_pro_effective = datetime.fromisoformat(user["pro_expires_at"]) > datetime.now(timezone.utc)
        except ValueError:
            is_pro_effective = False
    return {
        "username": user["username"],
        "email": user.get("email"),
        "is_pro": is_pro_effective,
        "pro_expires_at": user.get("pro_expires_at"),
        "papers_generated": user.get("papers_generated", 0),
    }


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password")
def change_password(payload: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    if not verify_password(payload.current_password, user["password"]):
        raise HTTPException(400, "Current password is incorrect.")
    if len(payload.new_password) < 6:
        raise HTTPException(400, "New password must be at least 6 characters.")
    supabase.table("users").update({"password": hash_password(payload.new_password)}).eq("username", user["username"]).execute()
    return {"message": "Password updated."}


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest):
    username = payload.username.strip()
    email = payload.email.strip().lower()

    if len(username) < 3:
        raise HTTPException(400, "Username must be at least 3 characters.")
    if len(payload.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters.")

    existing = supabase.table("users").select("username").ilike("username", username).execute()
    if existing.data:
        raise HTTPException(409, "Username already exists.")
    existing_email = supabase.table("users").select("username").ilike("email", email).execute()
    if existing_email.data:
        raise HTTPException(409, "An account with this email already exists.")

    try:
        supabase.table("users").insert({
            "username": username,
            "password": hash_password(payload.password),
            "email": email,
            "papers_generated": 0,
            "is_pro": False,
        }).execute()
    except Exception as e:
        logger.error(f"[Signup Error] {e}")
        raise HTTPException(500, "Something went wrong creating your account.")

    return {"message": "Account created successfully."}


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    username = payload.username.strip()
    _check_rate_limit(username)

    res = supabase.table("users").select("*").eq("username", username).execute()
    if not res.data:
        _record_failed_login(username)
        raise HTTPException(401, "Invalid username or password.")

    user = res.data[0]
    if not verify_password(payload.password, user["password"]):
        _record_failed_login(username)
        raise HTTPException(401, "Invalid username or password.")

    _record_successful_login(username)
    token = create_access_token(username)
    return TokenResponse(access_token=token)


@router.post("/request-password-reset")
def request_password_reset(payload: RequestPasswordReset):
    identifier = payload.identifier.strip()
    generic_msg = {"message": "If that account exists, a reset code has been sent to its registered email."}

    res = supabase.table("users").select("username, email").or_(
        f"username.eq.{identifier},email.eq.{identifier.lower()}"
    ).execute()
    if not res.data:
        return generic_msg  # don't reveal whether the account exists

    user = res.data[0]
    if not user.get("email"):
        raise HTTPException(400, "This account has no email on file. Please contact support.")

    otp = f"{random.randint(0, 999999):06d}"
    otp_hash = hash_password(otp)
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()

    supabase.table("users").update({
        "reset_otp": otp_hash,
        "reset_otp_expires": expires_at,
    }).eq("username", user["username"]).execute()

    _send_otp_email(user["email"], otp)
    return generic_msg


@router.post("/reset-password")
def reset_password(payload: VerifyPasswordReset):
    import bcrypt
    identifier = payload.identifier.strip()

    res = supabase.table("users").select("username, reset_otp, reset_otp_expires").or_(
        f"username.eq.{identifier},email.eq.{identifier.lower()}"
    ).execute()
    if not res.data:
        raise HTTPException(400, "Incorrect code or account.")

    user = res.data[0]
    if not user.get("reset_otp") or not user.get("reset_otp_expires"):
        raise HTTPException(400, "No active reset request found. Please request a new code.")
    if datetime.fromisoformat(user["reset_otp_expires"]) < datetime.now(timezone.utc):
        raise HTTPException(400, "This code has expired. Please request a new one.")
    if not bcrypt.checkpw(payload.otp.encode(), user["reset_otp"].encode()):
        raise HTTPException(400, "Incorrect code.")
    if len(payload.new_password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters.")

    supabase.table("users").update({
        "password": hash_password(payload.new_password),
        "reset_otp": None,
        "reset_otp_expires": None,
    }).eq("username", user["username"]).execute()

    return {"message": "Password updated! Please log in with your new password."}


def _send_otp_email(to_email: str, otp: str):
    try:
        msg = MIMEText(
            f"Your PaperBanao password reset code is: {otp}\n\n"
            f"This code expires in 10 minutes. If you didn't request this, ignore this email."
        )
        msg["Subject"] = "PaperBanao - Password Reset Code"
        msg["From"] = settings.SMTP_USER
        msg["To"] = to_email

        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USER, [to_email], msg.as_string())
    except Exception as e:
        logger.error(f"[Email Send Error] {e}")
        # Don't fail the request just because the email didn't send —
        # the OTP is still valid, the user just won't have received it.
