from typing import Dict
from app.core.database import db


async def merchant_earnings(merchant_id: str) -> Dict[str, float]:
    """Calculate gross sales, paid out amounts, and pending payout for a merchant."""
    course_ids = [c["id"] for c in await db.courses.find({"merchant_id": merchant_id}, {"_id": 0, "id": 1}).to_list(500)]
    paid = await db.enrollments.find({"course_id": {"$in": course_ids}, "payment_status": "paid"}, {"_id": 0, "amount": 1}).to_list(2000)
    gross = sum(float(e.get("amount") or 0) for e in paid)
    already = sum(float(p.get("amount") or 0) for p in await db.payouts.find({"merchant_id": merchant_id, "status": "sent"}, {"_id": 0, "amount": 1}).to_list(500))
    return {"gross": gross, "paid_out": already, "pending": max(0.0, gross - already)}
