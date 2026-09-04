from typing import Any, Dict, Optional
from fastapi import Request
from app.core.config import settings
from app.core.database import db
from app.core.security import now
from app.core.stripe_integration import StripeCheckout
from app.services.referral_service import grant_referral_bonus


def stripe_client(request: Optional[Request] = None) -> StripeCheckout:
    """Create Stripe checkout client with configured webhook URL and secrets."""
    origin = ""
    if request is not None:
        origin = str(request.base_url).rstrip("/")
    webhook_url = f"{origin}/api/webhooks/stripe" if origin else ""
    return StripeCheckout(
        api_key=settings.STRIPE_API_KEY,
        webhook_url=webhook_url,
        webhook_secret=settings.STRIPE_WEBHOOK_SECRET or None,
    )


async def mark_paid(
    session_id: str,
    metadata: Dict[str, Any],
    payment_intent: Any,
    amount_total: Any,
    event_id: Optional[str] = None,
) -> None:
    """Reconcile payment as succeeded, activate enrollment, and grant referral bonus."""
    enrollment_id = (metadata or {}).get("enrollment_id")
    receipt = f"CZ-{(enrollment_id or session_id)[:8].upper()}"
    update: Dict[str, Any] = {
        "status": "succeeded",
        "stripe_payment_intent": payment_intent,
        "amount_total": amount_total,
        "receipt": receipt,
        "paid_at": now(),
    }
    if event_id:
        update["stripe_event_id"] = event_id

    await db.payments.update_one({"stripe_session_id": session_id}, {"$set": update})

    if enrollment_id:
        await db.enrollments.update_one(
            {"id": enrollment_id},
            {"$set": {"status": "active", "payment_status": "paid", "receipt": receipt, "paid_at": now()}},
        )
        enrollment = await db.enrollments.find_one({"id": enrollment_id}, {"_id": 0})
        if enrollment:
            await grant_referral_bonus(enrollment)
