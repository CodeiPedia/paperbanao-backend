import bcrypt
from datetime import datetime, timedelta, timezone
import jwt
from jwt import PyJWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.config import settings
from app.database import supabase

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, stored_hash: str) -> bool:
    # Compatible with hashes created by the existing Streamlit app (both use
    # bcrypt), so a user can log into either app with the same password.
    try:
        return bcrypt.checkpw(password.encode(), stored_hash.encode())
    except ValueError:
        return False

def create_access_token(username: str, session_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": username, "sid": session_id, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        username = payload.get("sub")
        session_id = payload.get("sid")
        if username is None:
            raise credentials_exception
        return username, session_id
    except PyJWTError:
        raise credentials_exception

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

session_invalidated_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="This account was logged in from another device. Please log in again.",
    headers={"WWW-Authenticate": "Bearer"},
)

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """FastAPI dependency: validates the JWT and returns the user's row
    from Supabase. Use this in any route that requires a logged-in user."""
    username, session_id = decode_access_token(token)
    res = supabase.table("users").select("*").eq("username", username).execute()
    if not res.data:
        raise credentials_exception
    user = res.data[0]
    # Single-device login: each login/signup stores a fresh session_id on
    # the user row and embeds the same value in the issued JWT. If a newer
    # login has happened elsewhere since this token was issued, the DB's
    # current_session_id will have moved on and no longer match — meaning
    # this token is from a now-superseded session, so we reject it with a
    # distinct message rather than the generic "invalid credentials" one.
    # Existing tokens issued before this feature shipped won't have a
    # current_session_id set yet, so they're left alone until next login.
    if user.get("current_session_id") and session_id != user["current_session_id"]:
        raise session_invalidated_exception
    return user

