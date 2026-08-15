import logging
from datetime import datetime, timedelta, timezone

import razorpay
from fastapi import APIRouter, Depends, HTTPException, Request

from app.database import supabase
from app.security import get_current_user
from app.config import settings

router = APIRouter(prefix="/payments", tags=["payments"])
logger = logging.getLogger("paperbanao")


def get_razorpay_client():
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        return None
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


@router.post("/create-link")
def create_payment_link(user: dict = Depends(get_current_user)):
    client = get_razorpay_client()
    if not client:
        raise HTTPException(500, "Payment system isn't configured right now.")

    try:
        link_data = {
            "amount": settings.PRO_PRICE_INR * 100,
            "currency": "INR",
            "accept_partial": False,
            "description": f"PaperBanao Pro - {settings.PRO_DURATION_DAYS} Days",
            "customer": {"name": user["username"], "email": user.get("email")} if user.get("email") else {"name": user["username"]},
            "notify": {"email": bool(user.get("email"))},
            "reminder_enable": True,
            "notes": {"username": user["username"]},
            # Razorpay redirects the browser here after payment, with query
            # params the frontend should forward to /payments/verify-callback
            "callback_url": f"{settings.FRONTEND_URL}/upgrade",
            "callback_method": "get",
        }
        link = client.payment_link.create(link_data)
        return {"payment_url": link["short_url"]}
    except Exception as e:
        logger.error(f"[Payment Link Error] {e}")
        raise HTTPException(500, "Couldn't create the payment link. Please try again.")


@router.post("/verify-callback")
def verify_callback(request_params: dict, user: dict = Depends(get_current_user)):
    """The frontend calls this with the query params Razorpay attached to
    the callback_url redirect (razorpay_payment_id, razorpay_signature, etc.)."""
    client = get_razorpay_client()
    if not client:
        raise HTTPException(500, "Payment system isn't configured right now.")

    required = ["razorpay_payment_link_id", "razorpay_payment_link_reference_id",
                "razorpay_payment_link_status", "razorpay_payment_id", "razorpay_signature"]
    if not all(k in request_params for k in required):
        raise HTTPException(400, "Missing payment verification parameters.")

    try:
        client.utility.verify_payment_link_signature(request_params)
    except razorpay.errors.SignatureVerificationError as e:
        logger.error(f"[Payment Signature Error] {e}")
        raise HTTPException(400, "Payment verification failed. If money was deducted, please contact support.")

    if request_params["razorpay_payment_link_status"] != "paid":
        return {"success": False, "message": "Payment not completed."}

    payment_id = request_params["razorpay_payment_id"]

    # Idempotency: don't double-credit if this callback fires twice
    existing = supabase.table("payments").select("payment_id").eq("payment_id", payment_id).execute()
    if existing.data:
        return {"success": True, "message": "Payment already processed."}

    try:
        link_details = client.payment_link.fetch(request_params["razorpay_payment_link_id"])
        paid_username = link_details.get("notes", {}).get("username")
    except Exception as e:
        logger.error(f"[Payment Link Fetch Error] {e}")
        raise HTTPException(500, "Couldn't confirm payment details. Please contact support.")

    if not paid_username or paid_username != user["username"]:
        raise HTTPException(400, "Payment does not match the logged-in account.")

    now = datetime.now(timezone.utc)
    current_expiry = None
    if user.get("pro_expires_at"):
        current_expiry = datetime.fromisoformat(user["pro_expires_at"])
    start_from = current_expiry if (current_expiry and current_expiry > now) else now
    new_expiry = start_from + timedelta(days=settings.PRO_DURATION_DAYS)

    supabase.table("users").update({
        "is_pro": True,
        "pro_expires_at": new_expiry.isoformat(),
    }).eq("username", paid_username).execute()

    supabase.table("payments").insert({
        "payment_id": payment_id,
        "username": paid_username,
        "amount_inr": settings.PRO_PRICE_INR,
    }).execute()

    return {"success": True, "message": f"Payment successful! Pro is active until {new_expiry.strftime('%d %b %Y')}."}

