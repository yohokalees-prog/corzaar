import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.core.config import settings
from app.core.database import db
from app.core.security import now
from app.core.stripe_integration import CheckoutSessionRequest
from app.dependencies.auth import require_roles
from app.models.enrollment import CheckoutCreate
from app.services.payment_service import mark_paid, stripe_client

logger = logging.getLogger("corzaar.payments")
router = APIRouter(tags=["payments"])


@router.post("/payments/checkout")
async def create_checkout(
    payload: CheckoutCreate,
    request: Request,
    user: Dict[str, Any] = Depends(require_roles("student")),
) -> Dict[str, Any]:
    """Create a Stripe checkout session for an enrollment."""
    enrollment = await db.enrollments.find_one({"id": payload.enrollment_id, "student_id": user["id"]}, {"_id": 0})
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    if enrollment.get("payment_status") == "paid":
        return {"already_paid": True, "enrollment_id": enrollment["id"]}

    course = await db.courses.find_one({"id": enrollment["course_id"]}, {"_id": 0})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    amount = float(enrollment.get("amount") or course.get("fees") or 0)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="This enrollment has no amount due")

    origin = str(request.base_url).rstrip("/")
    return_base = settings.APP_PAYMENT_RETURN_URL or f"{origin}/api/payments/return"
    session_request = CheckoutSessionRequest(
        amount=amount,
        currency="inr",
        success_url=f"{return_base}?session_id={{CHECKOUT_SESSION_ID}}&status=success",
        cancel_url=f"{return_base}?session_id={{CHECKOUT_SESSION_ID}}&status=cancel",
        metadata={
            "user_id": user["id"],
            "enrollment_id": enrollment["id"],
            "course_id": course["id"],
            "course_title": course.get("title", ""),
        },
    )

    try:
        session = await stripe_client(request).create_checkout_session(session_request)
    except Exception as exc:
        logger.exception("Stripe checkout failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")

    await db.payments.update_one(
        {"stripe_session_id": session.session_id},
        {"$set": {
            "stripe_session_id": session.session_id,
            "enrollment_id": enrollment["id"],
            "user_id": user["id"],
            "course_id": course["id"],
            "amount": amount,
            "currency": "inr",
            "status": "pending",
            "created_at": now(),
        }},
        upsert=True,
    )
    return {"checkout_url": session.url, "session_id": session.session_id}


@router.get("/payments/status/{session_id}")
async def payment_status(
    session_id: str,
    request: Request,
    user: Dict[str, Any] = Depends(require_roles("student")),
) -> Dict[str, Any]:
    """Check payment status for a checkout session and mark as paid if succeeded."""
    record = await db.payments.find_one({"stripe_session_id": session_id, "user_id": user["id"]}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="Payment not found")

    if record.get("status") == "pending":
        try:
            result = await stripe_client(request).get_checkout_status(session_id)
            if result.payment_status == "paid":
                metadata = getattr(result, "metadata", None) or {"enrollment_id": record.get("enrollment_id")}
                await mark_paid(session_id, metadata, None, result.amount_total)
                record = await db.payments.find_one({"stripe_session_id": session_id}, {"_id": 0}) or record
        except Exception:
            logger.exception("Stripe status lookup failed")

    return {
        "session_id": session_id,
        "status": record.get("status"),
        "enrollment_id": record.get("enrollment_id"),
        "receipt": record.get("receipt"),
    }


@router.get("/payments/return", response_class=HTMLResponse)
async def payment_return(session_id: str = "", status: str = "success") -> str:
    """HTML return landing page after completing or cancelling Stripe checkout."""
    verb = "Payment successful" if status == "success" else "Payment cancelled"
    body_msg = (
        "You can return to the CORZAAR app. Your enrollment is active."
        if status == "success"
        else "You can retry the payment from the CORZAAR app."
    )
    return f"""<!doctype html><html><head><meta name=viewport content='width=device-width,initial-scale=1'><title>{verb}</title><style>body{{font-family:-apple-system,system-ui,Roboto,sans-serif;background:#FDFCFA;color:#1C1C1E;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}}.card{{max-width:360px;padding:32px;text-align:center;border-radius:20px;background:#fff;box-shadow:0 20px 40px rgba(0,0,0,.08)}}h1{{color:#2E5A44;font-size:22px;margin:12px 0 8px}}p{{color:#636366;line-height:1.5;font-size:14px}}</style></head><body><div class=card><h1>{verb}</h1><p>{body_msg}</p><p style='font-size:11px;color:#8e8e93;margin-top:24px'>Session: {session_id}</p></div></body></html>"""


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(default=None, alias="Stripe-Signature"),
) -> Dict[str, Any]:
    """Stripe webhook receiver for asynchronous payment confirmations."""
    payload = await request.body()
    try:
        event = await stripe_client(request).handle_webhook(payload, stripe_signature)
    except Exception:
        logger.exception("Stripe webhook verification failed")
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event_id = getattr(event, "event_id", None) or getattr(event, "id", None)
    if event_id and await db.payments.find_one({"stripe_event_id": event_id}):
        return {"received": True, "duplicate": True}

    if getattr(event, "payment_status", None) == "paid":
        metadata = getattr(event, "metadata", None) or {}
        await mark_paid(event.session_id, metadata, None, getattr(event, "amount_total", None), event_id)
    return {"received": True}
