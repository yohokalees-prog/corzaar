import logging
import uuid
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("corzaar.stripe")

try:
    import stripe
except ImportError:
    stripe = None


class CheckoutSessionRequest(BaseModel):
    amount: float
    currency: str = "inr"
    success_url: str
    cancel_url: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CheckoutSessionResponse:
    def __init__(self, session_id: str, url: str):
        self.session_id = session_id
        self.url = url


class CheckoutStatusResponse:
    def __init__(self, session_id: str, payment_status: str, metadata: Dict[str, Any], amount_total: Optional[int] = None):
        self.session_id = session_id
        self.payment_status = payment_status
        self.metadata = metadata
        self.amount_total = amount_total


class WebhookEventResponse:
    def __init__(self, event_id: str, payment_status: str, metadata: Dict[str, Any], session_id: str, amount_total: Optional[int] = None):
        self.event_id = event_id
        self.id = event_id
        self.payment_status = payment_status
        self.metadata = metadata
        self.session_id = session_id
        self.amount_total = amount_total


class StripeCheckout:
    def __init__(self, api_key: str = "", webhook_url: str = "", webhook_secret: Optional[str] = None):
        self.api_key = api_key or ""
        self.webhook_url = webhook_url or ""
        self.webhook_secret = webhook_secret or ""
        if stripe and self.api_key:
            stripe.api_key = self.api_key

    async def create_checkout_session(self, req: CheckoutSessionRequest) -> CheckoutSessionResponse:
        # If valid Stripe API key is available
        if stripe and self.api_key and not self.api_key.startswith("mock_"):
            try:
                # Convert rupees to paise for INR
                unit_amount = int(round(req.amount * 100))
                course_title = req.metadata.get("course_title", "Course Enrollment")
                session = stripe.checkout.Session.create(
                    payment_method_types=["card"],
                    line_items=[{
                        "price_data": {
                            "currency": req.currency.lower(),
                            "unit_amount": unit_amount,
                            "product_data": {"name": course_title},
                        },
                        "quantity": 1,
                    }],
                    mode="payment",
                    success_url=req.success_url,
                    cancel_url=req.cancel_url,
                    metadata=req.metadata,
                )
                return CheckoutSessionResponse(session_id=session.id, url=session.url)
            except Exception as e:
                logger.error(f"Stripe API call error: {e}")
                # Fall back to simulation if needed in dev environment
                if "api_key" in str(e).lower() or "test" in self.api_key.lower():
                    pass
                else:
                    raise

        # Development / Simulation fallback
        mock_id = f"cs_test_{uuid.uuid4().hex}"
        mock_url = f"https://checkout.stripe.com/c/pay/{mock_id}"
        logger.info(f"Simulating Stripe checkout session: {mock_id}")
        return CheckoutSessionResponse(session_id=mock_id, url=mock_url)

    async def get_checkout_status(self, session_id: str) -> CheckoutStatusResponse:
        if stripe and self.api_key and not self.api_key.startswith("mock_") and not session_id.startswith("cs_test_"):
            try:
                session = stripe.checkout.Session.retrieve(session_id)
                return CheckoutStatusResponse(
                    session_id=session.id,
                    payment_status=getattr(session, "payment_status", "unpaid"),
                    metadata=getattr(session, "metadata", {}) or {},
                    amount_total=getattr(session, "amount_total", None),
                )
            except Exception as e:
                logger.error(f"Stripe status lookup error: {e}")

        # Development mock status: if session starts with cs_test_, return unpaid
        return CheckoutStatusResponse(
            session_id=session_id,
            payment_status="unpaid",
            metadata={},
            amount_total=None,
        )

    async def handle_webhook(self, payload: bytes, signature: Optional[str]) -> WebhookEventResponse:
        if stripe and self.webhook_secret and signature:
            event = stripe.Webhook.construct_event(payload, signature, self.webhook_secret)
            data_obj = event.data.object
            return WebhookEventResponse(
                event_id=event.id,
                payment_status=getattr(data_obj, "payment_status", "paid"),
                metadata=getattr(data_obj, "metadata", {}) or {},
                session_id=getattr(data_obj, "id", ""),
                amount_total=getattr(data_obj, "amount_total", None),
            )
        import json
        parsed = json.loads(payload.decode("utf-8") or "{}")
        obj = parsed.get("data", {}).get("object", {})
        return WebhookEventResponse(
            event_id=parsed.get("id", str(uuid.uuid4())),
            payment_status=obj.get("payment_status", "paid"),
            metadata=obj.get("metadata", {}),
            session_id=obj.get("id", ""),
            amount_total=obj.get("amount_total"),
        )
