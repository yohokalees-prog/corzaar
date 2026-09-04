import hashlib
import secrets
import uuid
from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from app.core.database import db
from app.core.security import gen_referral, now, public, token_for
from app.models.auth import AdminLogin, AdminVerify, OtpRequest, OtpVerify

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/send-otp")
async def send_otp(payload: OtpRequest) -> Dict[str, Any]:
    """Send verification OTP for student or merchant mobile login."""
    if payload.role not in {"student", "merchant"}:
        raise HTTPException(status_code=400, detail="OTP is available for student or merchant login")
    await db.otp_sessions.update_one(
        {"mobile": payload.mobile, "role": payload.role},
        {"$set": {"mobile": payload.mobile, "role": payload.role, "otp": "123456", "expires_at": now()}},
        upsert=True,
    )
    return {"message": "Verification code sent", "mobile": payload.mobile, "development_code": "123456"}


@router.post("/verify-otp")
async def verify_otp(payload: OtpVerify) -> Dict[str, Any]:
    """Verify OTP and issue session token; creates user record if new."""
    if payload.otp != "123456":
        raise HTTPException(status_code=400, detail="Invalid OTP. Please try again.")

    user = await db.users.find_one({"mobile": payload.mobile, "role": payload.role}, {"_id": 0})
    if not user:
        uid = str(uuid.uuid4())
        user = {
            "id": uid,
            "mobile": payload.mobile,
            "role": payload.role,
            "full_name": payload.full_name or "New learner",
            "status": "active",
            "profile_complete": False,
            "referral_code": gen_referral(uid),
            "wallet_balance": 0.0,
            "created_at": now(),
        }
        await db.users.insert_one(user.copy())

        # Auto-create merchant institute shell
        if payload.role == "merchant":
            await db.institutes.insert_one({
                "id": f"inst-{user['id'][:8]}",
                "name": "My Institute",
                "city": "Set your city",
                "rating": 0,
                "reviews_count": 0,
                "accreditation": "Pending",
                "students": "0",
                "description": "Edit your institute profile from the merchant portal.",
                "image_key": "campus",
                "status": "pending",
                "merchant_id": user["id"],
            })

    if not user.get("referral_code"):
        rc = gen_referral(user["id"])
        await db.users.update_one({"id": user["id"]}, {"$set": {"referral_code": rc, "wallet_balance": user.get("wallet_balance", 0.0)}})
        user["referral_code"] = rc

    if payload.role == "merchant" and user.get("login_enabled") is False:
        raise HTTPException(status_code=403, detail="Access denied — contact admin")

    return {
        "access_token": token_for(user),
        "refresh_token": secrets.token_urlsafe(32),
        "user": public(user),
        "next": "profile" if not user.get("profile_complete", True) and payload.role == "student" else "dashboard",
    }


@router.post("/admin-login")
async def admin_login(payload: AdminLogin) -> Dict[str, Any]:
    """Admin credentials step returning 2FA challenge."""
    user = await db.users.find_one({"email": payload.email, "role": "admin"}, {"_id": 0})
    if not user or user.get("password_hash") != hashlib.sha256(payload.password.encode()).hexdigest():
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    return {"message": "Verification code sent", "email": payload.email, "requires_otp": True, "development_code": "123456"}


@router.post("/admin-verify")
async def admin_verify(payload: AdminVerify) -> Dict[str, Any]:
    """Admin 2FA verification step returning admin session token."""
    if payload.otp != "123456":
        raise HTTPException(status_code=400, detail="Invalid OTP. Please try again.")
    user = await db.users.find_one({"email": payload.email, "role": "admin"}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Admin account not found")
    return {
        "access_token": token_for(user),
        "refresh_token": secrets.token_urlsafe(32),
        "user": public(user),
        "next": "dashboard",
    }
