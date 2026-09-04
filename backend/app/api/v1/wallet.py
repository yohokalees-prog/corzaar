import uuid
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException
from app.core.config import settings
from app.core.database import db
from app.core.security import gen_referral, now, public_many
from app.dependencies.auth import require_roles
from app.models.payment import CashoutRequest
from app.services.audit_service import audit

router = APIRouter(prefix="/me", tags=["wallet"])


@router.get("/referrals")
async def my_referrals(user: Dict[str, Any] = Depends(require_roles("student"))) -> Dict[str, Any]:
    """Retrieve personal referral code, wallet balance, and list of referred friends."""
    code = user.get("referral_code") or gen_referral(user["id"])
    if not user.get("referral_code"):
        await db.users.update_one({"id": user["id"]}, {"$set": {"referral_code": code}})

    rewards = public_many(await db.referral_rewards.find({"referrer_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50))
    friends = []
    for r in rewards:
        friend = await db.users.find_one({"id": r["referred_id"]}, {"_id": 0, "full_name": 1, "mobile": 1})
        friends.append({
            "amount": r["amount"],
            "created_at": r["created_at"],
            "friend_name": (friend or {}).get("full_name") or "A friend",
        })

    return {
        "code": code,
        "reward_per_referral": settings.REFERRAL_REWARD,
        "discount_percent": settings.REFERRAL_DISCOUNT_PERCENT,
        "wallet_balance": float(user.get("wallet_balance") or 0),
        "friends": friends,
        "count": len(friends),
    }


@router.post("/cashouts")
async def request_cashout(
    payload: CashoutRequest,
    user: Dict[str, Any] = Depends(require_roles("student")),
) -> Dict[str, Any]:
    """Request a cashout of earned wallet balance to UPI."""
    balance = float(user.get("wallet_balance") or 0)
    if payload.amount > balance:
        raise HTTPException(status_code=400, detail="Amount exceeds wallet balance")
    if payload.amount < settings.MIN_CASHOUT:
        raise HTTPException(status_code=400, detail=f"Minimum cashout is ₹{settings.MIN_CASHOUT:.0f}")

    upi = payload.upi_id.strip()
    if "@" not in upi or len(upi) < 5:
        raise HTTPException(status_code=400, detail="Enter a valid UPI ID (e.g. name@upi)")

    # Lock the amount immediately from student wallet
    await db.users.update_one({"id": user["id"]}, {"$inc": {"wallet_balance": -payload.amount}})

    cashout = {
        "id": str(uuid.uuid4()),
        "student_id": user["id"],
        "student_name": user.get("full_name"),
        "amount": payload.amount,
        "upi_id": upi,
        "status": "pending",
        "reference": "",
        "created_at": now(),
    }
    await db.cashouts.insert_one(cashout.copy())
    await audit(user, "Cashout requested", "Cashouts", f"₹{payload.amount:.0f} to {upi}", cashout["id"])
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "title": "Cashout requested",
        "body": f"₹{payload.amount:.0f} to {upi} is under review.",
        "kind": "cashout",
        "created_at": now(),
        "read": False,
    })
    return cashout


@router.get("/cashouts")
async def my_cashouts(user: Dict[str, Any] = Depends(require_roles("student"))) -> List[Dict[str, Any]]:
    """List student's cashout requests."""
    return public_many(await db.cashouts.find({"student_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100))
