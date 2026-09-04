import uuid
from typing import Any, Dict
from app.core.config import settings
from app.core.database import db
from app.core.security import now


async def grant_referral_bonus(enrollment: Dict[str, Any]) -> None:
    """Credit referral reward to referrer's wallet upon paid or completed enrollment."""
    code = enrollment.get("referral_code")
    if not code:
        return
    referrer = await db.users.find_one({"referral_code": code}, {"_id": 0})
    if not referrer:
        return
    # Avoid double-crediting for the same enrollment
    if await db.referral_rewards.find_one({"enrollment_id": enrollment["id"]}):
        return

    reward = settings.REFERRAL_REWARD
    await db.users.update_one({"id": referrer["id"]}, {"$inc": {"wallet_balance": reward}})
    await db.referral_rewards.insert_one({
        "id": str(uuid.uuid4()),
        "referrer_id": referrer["id"],
        "referred_id": enrollment["student_id"],
        "enrollment_id": enrollment["id"],
        "amount": reward,
        "created_at": now(),
    })
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": referrer["id"],
        "title": "Referral reward credited",
        "body": f"₹{reward:.0f} added to your CORZAAR wallet.",
        "kind": "reward",
        "created_at": now(),
        "read": False,
    })
