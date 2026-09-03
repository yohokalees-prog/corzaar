from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import logging
import os
import secrets
import uuid

import jwt
from dotenv import load_dotenv
from emergentintegrations.payments.stripe.checkout import CheckoutSessionRequest, StripeCheckout
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get("DB_NAME", "corzaar")]
SECRET_KEY = os.environ.get("JWT_SECRET", "corzaar-development-secret-key-please-configure-64chars")
ALGORITHM = "HS256"
STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY") or os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
APP_PAYMENT_RETURN_URL = os.environ.get("APP_PAYMENT_RETURN_URL", "")

app = FastAPI(title="CORZAAR IMS API", version="1.1.0")
api = APIRouter(prefix="/api")
logger = logging.getLogger("corzaar")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def public(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not doc:
        return None
    return {key: value for key, value in doc.items() if key != "_id"}


def public_many(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [item for item in (public(doc) for doc in docs) if item]


def token_for(user: Dict[str, Any]) -> str:
    return jwt.encode({"sub": user["id"], "role": user["role"], "exp": datetime.now(timezone.utc).timestamp() + 86400}, SECRET_KEY, algorithm=ALGORITHM)


async def current_user(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    try:
        payload = jwt.decode(authorization.split(" ", 1)[1], SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "Invalid or expired session") from exc
    user = await db.users.find_one({"id": payload.get("sub")}, {"_id": 0})
    if not user:
        raise HTTPException(401, "User not found")
    return user


def require_roles(*roles: str):
    async def dependency(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
        if user.get("role") not in roles:
            raise HTTPException(403, "Access denied for this role")
        return user
    return dependency


async def audit(user: Dict[str, Any], action: str, module: str, detail: str = "", target_id: str = "") -> None:
    await db.activity_logs.insert_one({"id": str(uuid.uuid4()), "action": action, "module": module, "role": user.get("role", ""), "actor_id": user.get("id"), "actor_name": user.get("full_name") or user.get("email") or user.get("mobile"), "detail": detail, "target_id": target_id, "created_at": now()})


async def recalc_rating(collection: str, target_id: str) -> None:
    field = "course_id" if collection == "courses" else "institute_id"
    reviews = await db.reviews.find({"target_type": collection, field: target_id}).to_list(500)
    if not reviews:
        return
    avg = round(sum(r["rating"] for r in reviews) / len(reviews), 1)
    await db[collection].update_one({"id": target_id}, {"$set": {"rating": avg, "reviews_count": len(reviews)}})


# ---------- Models ----------
class OtpRequest(BaseModel):
    mobile: str = Field(min_length=8, max_length=15)
    role: str = "student"


class OtpVerify(BaseModel):
    mobile: str
    otp: str
    role: str = "student"
    full_name: Optional[str] = None


class AdminLogin(BaseModel):
    email: str
    password: str


class AdminVerify(BaseModel):
    email: str
    otp: str


class ProfileUpdate(BaseModel):
    full_name: str
    email: Optional[str] = None
    date_of_birth: Optional[str] = None
    address: Optional[str] = None
    academic_qualifications: Optional[str] = None
    preferred_courses: List[str] = []
    language: str = "English"


class CartChange(BaseModel):
    course_id: str


class EnrollmentCreate(BaseModel):
    course_id: str
    batch_id: Optional[str] = None
    coupon_code: Optional[str] = None


class CheckoutCreate(BaseModel):
    enrollment_id: str


class MerchantRegistration(BaseModel):
    institute_name: str
    address: str
    contact_person: str
    mobile: str
    email: Optional[str] = None
    institute_details: str = ""
    bank_details: str
    documents: List[str] = []


class CourseCreate(BaseModel):
    title: str
    description: str
    category: str
    fees: float = 0
    duration: str = "8 weeks"
    curriculum: List[str] = []
    institute_id: Optional[str] = None


class BatchCreate(BaseModel):
    course_id: str
    schedule: str
    capacity: int = 30
    coordinator: str
    start_date: str
    end_date: str
    meet_link: Optional[str] = None


class AttendanceMark(BaseModel):
    student_id: str
    present: bool = True
    date: Optional[str] = None


class CouponCreate(BaseModel):
    code: str
    description: str = ""
    discount_percent: int = Field(ge=1, le=100)
    course_id: Optional[str] = None  # None => applies to all merchant courses


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    text: str = ""
    target_type: str  # "courses" or "institutes"
    target_id: str


class RefundRequest(BaseModel):
    enrollment_id: str
    reason: str


class CouponValidate(BaseModel):
    code: str
    course_id: str


# ---------- Seed ----------
@app.on_event("startup")
async def seed_demo_data() -> None:
    if await db.institutes.count_documents({}) == 0:
        await db.institutes.insert_many([
            {"id": "inst-apex", "name": "Apex Institute of Technology", "city": "Bengaluru", "rating": 4.8, "reviews_count": 0, "accreditation": "NAAC A+", "students": "12k+", "description": "Industry-led programs for the builders of tomorrow.", "image_key": "campus", "status": "approved", "merchant_id": None},
            {"id": "inst-global", "name": "Global Business Academy", "city": "Mumbai", "rating": 4.7, "reviews_count": 0, "accreditation": "AICTE approved", "students": "8k+", "description": "Practical business education with a global outlook.", "image_key": "business", "status": "approved", "merchant_id": None},
            {"id": "inst-design", "name": "Northstar Design School", "city": "Pune", "rating": 4.9, "reviews_count": 0, "accreditation": "UGC recognized", "students": "4k+", "description": "Make meaningful work with a sharp creative practice.", "image_key": "design", "status": "approved", "merchant_id": None},
        ])
    if await db.courses.count_documents({}) == 0:
        await db.courses.insert_many([
            {"id": "course-product", "title": "Product Design Foundations", "institute_id": "inst-design", "category": "Design", "duration": "10 weeks", "fees": 14999, "rating": 4.9, "reviews_count": 0, "students": 1240, "mode": "Live online", "description": "Turn real user problems into clear, compelling product experiences.", "curriculum": ["Design research", "Interaction design", "Portfolio studio"], "status": "published", "is_featured": True, "image_key": "design", "merchant_id": None},
            {"id": "course-data", "title": "Data Analytics with Python", "institute_id": "inst-apex", "category": "Technology", "duration": "12 weeks", "fees": 18999, "rating": 4.8, "reviews_count": 0, "students": 2100, "mode": "Hybrid", "description": "Build confidence with data, dashboards, and decision-making.", "curriculum": ["Python essentials", "SQL and dashboards", "Capstone project"], "status": "published", "is_featured": True, "image_key": "campus", "merchant_id": None},
            {"id": "course-marketing", "title": "Digital Marketing Sprint", "institute_id": "inst-global", "category": "Business", "duration": "6 weeks", "fees": 0, "rating": 4.7, "reviews_count": 0, "students": 3850, "mode": "Self-paced", "description": "A free practical sprint covering growth, content, and campaign strategy.", "curriculum": ["Customer journeys", "Content systems", "Growth experiments"], "status": "published", "is_featured": True, "image_key": "business", "merchant_id": None},
            {"id": "course-ai", "title": "Applied AI for Teams", "institute_id": "inst-apex", "category": "Technology", "duration": "8 weeks", "fees": 22999, "rating": 4.8, "reviews_count": 0, "students": 860, "mode": "Live online", "description": "Understand where AI creates leverage and how to ship responsibly.", "curriculum": ["AI foundations", "Workflow design", "Responsible deployment"], "status": "published", "is_featured": False, "image_key": "campus", "merchant_id": None},
        ])
    if not await db.users.find_one({"email": "admin@corzaar.com"}):
        await db.users.insert_one({"id": "admin-001", "email": "admin@corzaar.com", "password_hash": hashlib.sha256(b"Admin@123").hexdigest(), "role": "admin", "full_name": "CORZAAR Admin", "status": "active"})
    # useful indexes
    await db.payments.create_index("stripe_session_id", unique=True, sparse=True)
    await db.payments.create_index("stripe_event_id", unique=True, sparse=True)
    await db.reviews.create_index([("target_type", 1), ("target_id", 1), ("author_id", 1)], unique=True)


@api.get("/")
async def root() -> Dict[str, str]:
    return {"message": "CORZAAR IMS API", "status": "ok"}


# ---------- Auth ----------
@api.post("/auth/send-otp")
async def send_otp(payload: OtpRequest) -> Dict[str, Any]:
    if payload.role not in {"student", "merchant"}:
        raise HTTPException(400, "OTP is available for student or merchant login")
    await db.otp_sessions.update_one({"mobile": payload.mobile, "role": payload.role}, {"$set": {"mobile": payload.mobile, "role": payload.role, "otp": "123456", "expires_at": now()}}, upsert=True)
    return {"message": "Verification code sent", "mobile": payload.mobile, "development_code": "123456"}


@api.post("/auth/verify-otp")
async def verify_otp(payload: OtpVerify) -> Dict[str, Any]:
    if payload.otp != "123456":
        raise HTTPException(400, "Invalid OTP. Please try again.")
    user = await db.users.find_one({"mobile": payload.mobile, "role": payload.role}, {"_id": 0})
    if not user:
        user = {"id": str(uuid.uuid4()), "mobile": payload.mobile, "role": payload.role, "full_name": payload.full_name or "New learner", "status": "active", "profile_complete": False, "created_at": now()}
        await db.users.insert_one(user.copy())
        # auto-create a merchant institute shell so they can list courses
        if payload.role == "merchant":
            await db.institutes.insert_one({"id": f"inst-{user['id'][:8]}", "name": "My Institute", "city": "Set your city", "rating": 0, "reviews_count": 0, "accreditation": "Pending", "students": "0", "description": "Edit your institute profile from the merchant portal.", "image_key": "campus", "status": "pending", "merchant_id": user["id"]})
    if payload.role == "merchant" and user.get("login_enabled") is False:
        raise HTTPException(403, "Access denied — contact admin")
    return {"access_token": token_for(user), "refresh_token": secrets.token_urlsafe(32), "user": public(user), "next": "profile" if not user.get("profile_complete", True) and payload.role == "student" else "dashboard"}


@api.post("/auth/admin-login")
async def admin_login(payload: AdminLogin) -> Dict[str, Any]:
    user = await db.users.find_one({"email": payload.email, "role": "admin"}, {"_id": 0})
    if not user or user.get("password_hash") != hashlib.sha256(payload.password.encode()).hexdigest():
        raise HTTPException(401, "Invalid admin credentials")
    return {"message": "Verification code sent", "email": payload.email, "requires_otp": True, "development_code": "123456"}


@api.post("/auth/admin-verify")
async def admin_verify(payload: AdminVerify) -> Dict[str, Any]:
    if payload.otp != "123456":
        raise HTTPException(400, "Invalid OTP. Please try again.")
    user = await db.users.find_one({"email": payload.email, "role": "admin"}, {"_id": 0})
    if not user:
        raise HTTPException(401, "Admin account not found")
    return {"access_token": token_for(user), "refresh_token": secrets.token_urlsafe(32), "user": public(user), "next": "dashboard"}


# ---------- Discovery ----------
@api.get("/home")
async def home() -> Dict[str, Any]:
    courses = public_many(await db.courses.find({"status": "published"}, {"_id": 0}).sort("rating", -1).to_list(20))
    institutes = public_many(await db.institutes.find({"status": "approved"}, {"_id": 0}).sort("rating", -1).to_list(10))
    return {"hero": {"eyebrow": "LEARN WITH PURPOSE", "title": "Your next chapter starts here.", "subtitle": "Discover trusted institutes, practical courses, and a path that feels like yours.", "offer": "Scholarships up to 40% this month"}, "courses": courses, "institutes": institutes, "categories": ["All", "Design", "Technology", "Business", "Marketing"]}


@api.get("/courses")
async def list_courses(q: str = "", category: str = "All", price_max: Optional[float] = None) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {"status": "published"}
    if q:
        query["$or"] = [{"title": {"$regex": q, "$options": "i"}}, {"description": {"$regex": q, "$options": "i"}}]
    if category and category != "All":
        query["category"] = category
    if price_max is not None:
        query["fees"] = {"$lte": price_max}
    return public_many(await db.courses.find(query, {"_id": 0}).sort("rating", -1).to_list(50))


@api.get("/courses/{course_id}")
async def course_detail(course_id: str) -> Dict[str, Any]:
    course = public(await db.courses.find_one({"id": course_id}, {"_id": 0}))
    if not course:
        raise HTTPException(404, "Course not found")
    institute = public(await db.institutes.find_one({"id": course["institute_id"]}, {"_id": 0}))
    related = public_many(await db.courses.find({"category": course["category"], "id": {"$ne": course_id}, "status": "published"}, {"_id": 0}).to_list(4))
    reviews = public_many(await db.reviews.find({"target_type": "courses", "course_id": course_id}, {"_id": 0}).sort("created_at", -1).to_list(20))
    batches = public_many(await db.batches.find({"course_id": course_id, "status": "active"}, {"_id": 0}).to_list(10))
    return {"course": course, "institute": institute, "related": related, "reviews": reviews, "batches": batches}


@api.get("/institutes/{institute_id}")
async def institute_detail(institute_id: str) -> Dict[str, Any]:
    institute = public(await db.institutes.find_one({"id": institute_id}, {"_id": 0}))
    if not institute:
        raise HTTPException(404, "Institute not found")
    institute["courses"] = public_many(await db.courses.find({"institute_id": institute_id, "status": "published"}, {"_id": 0}).to_list(20))
    institute["testimonials"] = public_many(await db.reviews.find({"target_type": "institutes", "institute_id": institute_id}, {"_id": 0}).sort("created_at", -1).to_list(10))
    return institute


# ---------- Profile / Lists ----------
@api.get("/me")
async def me(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    return public(user) or {}


@api.put("/me/profile")
async def update_profile(payload: ProfileUpdate, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    updates = payload.model_dump()
    updates["profile_complete"] = True
    await db.users.update_one({"id": user["id"]}, {"$set": updates})
    updated = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    return public(updated) or {}


async def user_list(user: Dict[str, Any], field: str) -> List[str]:
    record = await db.user_lists.find_one({"user_id": user["id"]}, {"_id": 0})
    return (record or {}).get(field, [])


@api.get("/me/lists")
async def lists(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    return {"cart": await user_list(user, "cart"), "favorites": await user_list(user, "favorites")}


@api.post("/me/cart")
async def add_cart(payload: CartChange, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    course = await db.courses.find_one({"id": payload.course_id}, {"_id": 0})
    if not course:
        raise HTTPException(404, "Course unavailable")
    await db.user_lists.update_one({"user_id": user["id"]}, {"$addToSet": {"cart": payload.course_id}}, upsert=True)
    return await lists(user)


@api.delete("/me/cart/{course_id}")
async def remove_cart(course_id: str, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    await db.user_lists.update_one({"user_id": user["id"]}, {"$pull": {"cart": course_id}})
    return await lists(user)


@api.post("/me/favorites")
async def add_favorite(payload: CartChange, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    await db.user_lists.update_one({"user_id": user["id"]}, {"$addToSet": {"favorites": payload.course_id}}, upsert=True)
    return await lists(user)


@api.delete("/me/favorites/{course_id}")
async def remove_favorite(course_id: str, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    await db.user_lists.update_one({"user_id": user["id"]}, {"$pull": {"favorites": course_id}})
    return await lists(user)


# ---------- Coupons ----------
@api.post("/coupons/validate")
async def validate_coupon(payload: CouponValidate, user: Dict[str, Any] = Depends(require_roles("student"))) -> Dict[str, Any]:
    course = await db.courses.find_one({"id": payload.course_id}, {"_id": 0})
    if not course:
        raise HTTPException(404, "Course not found")
    coupon = await db.coupons.find_one({"code": payload.code.upper(), "status": "approved"}, {"_id": 0})
    if not coupon:
        raise HTTPException(400, "Coupon is invalid or not yet approved")
    if coupon.get("course_id") and coupon["course_id"] != payload.course_id:
        raise HTTPException(400, "Coupon is not valid for this course")
    if coupon.get("merchant_id") and coupon["merchant_id"] != course.get("merchant_id"):
        raise HTTPException(400, "Coupon is not valid for this course")
    fees = float(course.get("fees") or 0)
    discount = round(fees * (coupon["discount_percent"] / 100), 2)
    return {"code": coupon["code"], "discount_percent": coupon["discount_percent"], "discount": discount, "final": max(0, fees - discount)}


# ---------- Enrollment & Payments ----------
@api.post("/enrollments")
async def enroll(payload: EnrollmentCreate, user: Dict[str, Any] = Depends(require_roles("student"))) -> Dict[str, Any]:
    course = await db.courses.find_one({"id": payload.course_id}, {"_id": 0})
    if not course:
        raise HTTPException(404, "Course not found")
    existing = await db.enrollments.find_one({"student_id": user["id"], "course_id": payload.course_id, "status": {"$in": ["active", "pending_payment"]}}, {"_id": 0})
    if existing:
        return public(existing) or {}
    fees = float(course.get("fees") or 0)
    discount = 0.0
    coupon_code = None
    if payload.coupon_code and fees > 0:
        try:
            info = await validate_coupon(CouponValidate(code=payload.coupon_code, course_id=payload.course_id), user)
            discount = float(info["discount"])
            coupon_code = info["code"]
        except HTTPException:
            pass
    final = max(0, fees - discount)
    status = "active" if final == 0 else "pending_payment"
    enrollment = {"id": str(uuid.uuid4()), "student_id": user["id"], "course_id": payload.course_id, "batch_id": payload.batch_id, "status": status, "progress": 0, "amount": final, "original_amount": fees, "discount": discount, "coupon_code": coupon_code, "payment_status": "paid" if final == 0 else "pending", "created_at": now()}
    await db.enrollments.insert_one(enrollment.copy())
    if final == 0:
        await audit(user, "Free enrollment", "Enrollments", course["title"], enrollment["id"])
    return enrollment


def stripe_client(request: Optional[Request] = None) -> StripeCheckout:
    origin = ""
    if request is not None:
        origin = str(request.base_url).rstrip("/")
    webhook_url = f"{origin}/api/webhooks/stripe" if origin else ""
    return StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url, webhook_secret=STRIPE_WEBHOOK_SECRET or None)


@api.post("/payments/checkout")
async def create_checkout(payload: CheckoutCreate, request: Request, user: Dict[str, Any] = Depends(require_roles("student"))) -> Dict[str, Any]:
    enrollment = await db.enrollments.find_one({"id": payload.enrollment_id, "student_id": user["id"]}, {"_id": 0})
    if not enrollment:
        raise HTTPException(404, "Enrollment not found")
    if enrollment.get("payment_status") == "paid":
        return {"already_paid": True, "enrollment_id": enrollment["id"]}
    course = await db.courses.find_one({"id": enrollment["course_id"]}, {"_id": 0})
    if not course:
        raise HTTPException(404, "Course not found")
    amount = float(enrollment.get("amount") or course.get("fees") or 0)
    if amount <= 0:
        raise HTTPException(400, "This enrollment has no amount due")
    origin = str(request.base_url).rstrip("/")
    return_base = APP_PAYMENT_RETURN_URL or f"{origin}/api/payments/return"
    session_request = CheckoutSessionRequest(
        amount=amount,
        currency="inr",
        success_url=f"{return_base}?session_id={{CHECKOUT_SESSION_ID}}&status=success",
        cancel_url=f"{return_base}?session_id={{CHECKOUT_SESSION_ID}}&status=cancel",
        metadata={"user_id": user["id"], "enrollment_id": enrollment["id"], "course_id": course["id"], "course_title": course.get("title", "")},
    )
    try:
        session = await stripe_client(request).create_checkout_session(session_request)
    except Exception as exc:
        logger.exception("Stripe checkout failed")
        raise HTTPException(502, f"Stripe error: {exc}")
    await db.payments.update_one(
        {"stripe_session_id": session.session_id},
        {"$set": {"stripe_session_id": session.session_id, "enrollment_id": enrollment["id"], "user_id": user["id"], "course_id": course["id"], "amount": amount, "currency": "inr", "status": "pending", "created_at": now()}},
        upsert=True,
    )
    return {"checkout_url": session.url, "session_id": session.session_id}


@api.get("/payments/status/{session_id}")
async def payment_status(session_id: str, request: Request, user: Dict[str, Any] = Depends(require_roles("student"))) -> Dict[str, Any]:
    record = await db.payments.find_one({"stripe_session_id": session_id, "user_id": user["id"]}, {"_id": 0})
    if not record:
        raise HTTPException(404, "Payment not found")
    if record.get("status") == "pending":
        try:
            result = await stripe_client(request).get_checkout_status(session_id)
            if result.payment_status == "paid":
                metadata = getattr(result, "metadata", None) or {"enrollment_id": record.get("enrollment_id")}
                await _mark_paid(session_id, metadata, None, result.amount_total)
                record = await db.payments.find_one({"stripe_session_id": session_id}, {"_id": 0}) or record
        except Exception:
            logger.exception("Stripe status lookup failed")
    return {"session_id": session_id, "status": record.get("status"), "enrollment_id": record.get("enrollment_id"), "receipt": record.get("receipt")}


async def _mark_paid(session_id: str, metadata: Dict[str, Any], payment_intent: Any, amount_total: Any, event_id: Optional[str] = None) -> None:
    enrollment_id = (metadata or {}).get("enrollment_id")
    receipt = f"CZ-{(enrollment_id or session_id)[:8].upper()}"
    update: Dict[str, Any] = {"status": "succeeded", "stripe_payment_intent": payment_intent, "amount_total": amount_total, "receipt": receipt, "paid_at": now()}
    if event_id:
        update["stripe_event_id"] = event_id
    await db.payments.update_one({"stripe_session_id": session_id}, {"$set": update})
    if enrollment_id:
        await db.enrollments.update_one({"id": enrollment_id}, {"$set": {"status": "active", "payment_status": "paid", "receipt": receipt, "paid_at": now()}})


@api.get("/payments/return", response_class=HTMLResponse)
async def payment_return(session_id: str = "", status: str = "success") -> str:
    verb = "Payment successful" if status == "success" else "Payment cancelled"
    body_msg = "You can return to the CORZAAR app. Your enrollment is active." if status == "success" else "You can retry the payment from the CORZAAR app."
    return f"""<!doctype html><html><head><meta name=viewport content='width=device-width,initial-scale=1'><title>{verb}</title><style>body{{font-family:-apple-system,system-ui,Roboto,sans-serif;background:#FDFCFA;color:#1C1C1E;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}}.card{{max-width:360px;padding:32px;text-align:center;border-radius:20px;background:#fff;box-shadow:0 20px 40px rgba(0,0,0,.08)}}h1{{color:#2E5A44;font-size:22px;margin:12px 0 8px}}p{{color:#636366;line-height:1.5;font-size:14px}}</style></head><body><div class=card><h1>{verb}</h1><p>{body_msg}</p><p style='font-size:11px;color:#8e8e93;margin-top:24px'>Session: {session_id}</p></div></body></html>"""


@api.post("/webhooks/stripe")
async def stripe_webhook(request: Request, stripe_signature: Optional[str] = Header(default=None, alias="Stripe-Signature")) -> Dict[str, Any]:
    payload = await request.body()
    try:
        event = await stripe_client(request).handle_webhook(payload, stripe_signature)
    except Exception:
        logger.exception("Stripe webhook verification failed")
        raise HTTPException(400, "Invalid webhook signature")
    event_id = getattr(event, "event_id", None) or getattr(event, "id", None)
    if event_id and await db.payments.find_one({"stripe_event_id": event_id}):
        return {"received": True, "duplicate": True}
    if getattr(event, "payment_status", None) == "paid":
        metadata = getattr(event, "metadata", None) or {}
        await _mark_paid(event.session_id, metadata, None, getattr(event, "amount_total", None), event_id)
    return {"received": True}


@api.get("/me/enrollments")
async def enrollments(user: Dict[str, Any] = Depends(require_roles("student"))) -> List[Dict[str, Any]]:
    rows = public_many(await db.enrollments.find({"student_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50))
    for row in rows:
        course = await db.courses.find_one({"id": row["course_id"]}, {"_id": 0, "title": 1, "image_key": 1, "duration": 1, "institute_id": 1})
        row["course"] = public(course)
    return rows


# ---------- Reviews / Ratings ----------
@api.post("/reviews")
async def create_review(payload: ReviewCreate, user: Dict[str, Any] = Depends(require_roles("student"))) -> Dict[str, Any]:
    if payload.target_type not in ("courses", "institutes"):
        raise HTTPException(400, "Invalid target")
    # only enrolled students may rate
    if payload.target_type == "courses":
        e = await db.enrollments.find_one({"student_id": user["id"], "course_id": payload.target_id, "status": "active"})
        if not e:
            raise HTTPException(403, "Only enrolled students can review this course")
    else:
        course_ids = [c["id"] for c in await db.courses.find({"institute_id": payload.target_id}, {"_id": 0, "id": 1}).to_list(200)]
        e = await db.enrollments.find_one({"student_id": user["id"], "course_id": {"$in": course_ids}, "status": "active"})
        if not e:
            raise HTTPException(403, "Only enrolled students can review this institute")
    doc = {"id": str(uuid.uuid4()), "target_type": payload.target_type, "rating": payload.rating, "text": payload.text, "author_id": user["id"], "name": user.get("full_name") or "CORZAAR learner", "created_at": now()}
    if payload.target_type == "courses":
        doc["course_id"] = payload.target_id
    else:
        doc["institute_id"] = payload.target_id
    try:
        await db.reviews.insert_one(doc.copy())
    except Exception:
        await db.reviews.update_one({"target_type": payload.target_type, ("course_id" if payload.target_type == "courses" else "institute_id"): payload.target_id, "author_id": user["id"]}, {"$set": {"rating": payload.rating, "text": payload.text, "created_at": now()}}, upsert=True)
    await recalc_rating(payload.target_type, payload.target_id)
    return doc


# ---------- Notifications / Offers / Placements ----------
@api.get("/me/notifications")
async def notifications(user: Dict[str, Any] = Depends(current_user)) -> List[Dict[str, Any]]:
    rows = public_many(await db.notifications.find({"$or": [{"user_id": user["id"]}, {"user_id": "all"}]}, {"_id": 0}).sort("created_at", -1).to_list(20))
    return rows or [{"id": "welcome", "title": "Welcome to CORZAAR", "body": "Complete your profile to unlock better recommendations.", "kind": "info", "created_at": now(), "read": False}]


@api.get("/offers")
async def offers() -> List[Dict[str, Any]]:
    approved = public_many(await db.coupons.find({"status": "approved"}, {"_id": 0}).sort("created_at", -1).to_list(20))
    return approved or [{"id": "welcome-offer", "title": "Welcome offer", "subtitle": "Merchants can publish coupons here after admin approval.", "code": "SOON", "discount_percent": 0}]


@api.get("/placements")
async def placements(user: Dict[str, Any] = Depends(require_roles("student"))) -> List[Dict[str, Any]]:
    return [{"id": "placement-1", "company": "Pine Labs", "role": "Junior Product Designer", "location": "Bengaluru · Hybrid", "type": "Full-time", "eligible": True, "status": "Open"}, {"id": "placement-2", "company": "Brightside Labs", "role": "Data Analyst Intern", "location": "Remote", "type": "Internship", "eligible": True, "status": "Open"}]


# ---------- Refunds ----------
@api.post("/refunds")
async def request_refund(payload: RefundRequest, user: Dict[str, Any] = Depends(require_roles("student"))) -> Dict[str, Any]:
    enrollment = await db.enrollments.find_one({"id": payload.enrollment_id, "student_id": user["id"]}, {"_id": 0})
    if not enrollment:
        raise HTTPException(404, "Enrollment not found")
    if enrollment.get("payment_status") != "paid":
        raise HTTPException(400, "Only paid enrollments can be refunded")
    existing = await db.refunds.find_one({"enrollment_id": payload.enrollment_id}, {"_id": 0})
    if existing:
        return public(existing) or {}
    course = await db.courses.find_one({"id": enrollment["course_id"]}, {"_id": 0, "title": 1})
    refund = {"id": str(uuid.uuid4()), "enrollment_id": payload.enrollment_id, "student_id": user["id"], "student_name": user.get("full_name"), "course_id": enrollment["course_id"], "course_title": (course or {}).get("title"), "amount": enrollment.get("amount"), "reason": payload.reason, "status": "pending", "created_at": now()}
    await db.refunds.insert_one(refund.copy())
    await audit(user, "Refund requested", "Refunds", (course or {}).get("title", ""), refund["id"])
    return refund


@api.get("/me/refunds")
async def my_refunds(user: Dict[str, Any] = Depends(require_roles("student"))) -> List[Dict[str, Any]]:
    return public_many(await db.refunds.find({"student_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50))


# ---------- Merchant ----------
@api.post("/merchant/registrations")
async def merchant_registration(payload: MerchantRegistration) -> Dict[str, Any]:
    application = {"id": str(uuid.uuid4()), **payload.model_dump(), "status": "pending", "created_at": now()}
    await db.merchant_registrations.insert_one(application.copy())
    return {"id": application["id"], "status": "pending", "message": "Application submitted for admin review"}


@api.get("/merchant/dashboard")
async def merchant_dashboard(user: Dict[str, Any] = Depends(require_roles("merchant"))) -> Dict[str, Any]:
    my_courses = await db.courses.find({"merchant_id": user["id"]}, {"_id": 0, "id": 1, "fees": 1, "status": 1}).to_list(200)
    course_ids = [c["id"] for c in my_courses]
    published = [c for c in my_courses if c["status"] == "published"]
    paid_enrollments = await db.enrollments.find({"course_id": {"$in": course_ids}, "payment_status": "paid"}, {"_id": 0, "amount": 1}).to_list(1000)
    revenue = sum(float(e.get("amount") or 0) for e in paid_enrollments)
    institute = await db.institutes.find_one({"merchant_id": user["id"]}, {"_id": 0})
    return {
        "active_courses": len(published),
        "under_review": len([c for c in my_courses if c["status"] == "under_review"]),
        "active_batches": await db.batches.count_documents({"merchant_id": user["id"], "status": "active"}),
        "enrollments": len(paid_enrollments),
        "revenue": revenue,
        "institute": public(institute),
        "pending_coupons": await db.coupons.count_documents({"merchant_id": user["id"], "status": "pending"}),
        "announcements": ["Publish approved coupons to attract students.", "Batch details keep enrollments organized."],
    }


@api.get("/merchant/courses")
async def merchant_courses(user: Dict[str, Any] = Depends(require_roles("merchant"))) -> List[Dict[str, Any]]:
    return public_many(await db.courses.find({"merchant_id": user["id"]}, {"_id": 0}).sort("status", 1).to_list(100))


@api.post("/merchant/courses")
async def merchant_course(payload: CourseCreate, user: Dict[str, Any] = Depends(require_roles("merchant"))) -> Dict[str, Any]:
    institute = await db.institutes.find_one({"merchant_id": user["id"]}, {"_id": 0, "id": 1})
    if not institute:
        raise HTTPException(400, "Institute profile missing. Contact admin.")
    course = {"id": str(uuid.uuid4()), **payload.model_dump(), "merchant_id": user["id"], "institute_id": institute["id"], "status": "under_review", "rating": 0, "reviews_count": 0, "students": 0, "mode": "Live online", "image_key": "campus", "created_at": now()}
    await db.courses.insert_one(course.copy())
    await audit(user, "Course submitted", "Courses", course["title"], course["id"])
    return course


@api.get("/merchant/batches")
async def merchant_batches(user: Dict[str, Any] = Depends(require_roles("merchant"))) -> List[Dict[str, Any]]:
    return public_many(await db.batches.find({"merchant_id": user["id"]}, {"_id": 0}).sort("start_date", -1).to_list(100))


@api.post("/merchant/batches")
async def merchant_batch(payload: BatchCreate, user: Dict[str, Any] = Depends(require_roles("merchant"))) -> Dict[str, Any]:
    course = await db.courses.find_one({"id": payload.course_id, "merchant_id": user["id"]}, {"_id": 0, "title": 1})
    if not course:
        raise HTTPException(400, "Course not owned by this merchant")
    batch = {"id": str(uuid.uuid4()), **payload.model_dump(), "merchant_id": user["id"], "course_title": course["title"], "status": "active", "enrolled": 0, "created_at": now()}
    await db.batches.insert_one(batch.copy())
    await audit(user, "Batch created", "Batches", course["title"], batch["id"])
    return batch


@api.get("/merchant/batches/{batch_id}/attendance")
async def batch_attendance(batch_id: str, user: Dict[str, Any] = Depends(require_roles("merchant"))) -> Dict[str, Any]:
    batch = await db.batches.find_one({"id": batch_id, "merchant_id": user["id"]}, {"_id": 0})
    if not batch:
        raise HTTPException(404, "Batch not found")
    enrolled = public_many(await db.enrollments.find({"course_id": batch["course_id"], "status": "active"}, {"_id": 0}).to_list(200))
    students: List[Dict[str, Any]] = []
    for e in enrolled:
        s = await db.users.find_one({"id": e["student_id"]}, {"_id": 0, "id": 1, "full_name": 1, "mobile": 1})
        if s:
            marks = await db.attendance.find({"batch_id": batch_id, "student_id": s["id"]}, {"_id": 0}).to_list(200)
            students.append({"id": s["id"], "name": s.get("full_name") or "Learner", "mobile": s.get("mobile"), "sessions": len(marks), "present": sum(1 for m in marks if m.get("present"))})
    return {"batch": public(batch), "students": students}


@api.post("/merchant/batches/{batch_id}/attendance")
async def mark_attendance(batch_id: str, payload: AttendanceMark, user: Dict[str, Any] = Depends(require_roles("merchant"))) -> Dict[str, Any]:
    batch = await db.batches.find_one({"id": batch_id, "merchant_id": user["id"]}, {"_id": 0})
    if not batch:
        raise HTTPException(404, "Batch not found")
    entry = {"id": str(uuid.uuid4()), "batch_id": batch_id, "student_id": payload.student_id, "present": payload.present, "date": payload.date or now(), "marked_by": user["id"]}
    await db.attendance.insert_one(entry.copy())
    return entry


@api.get("/merchant/coupons")
async def merchant_coupons(user: Dict[str, Any] = Depends(require_roles("merchant"))) -> List[Dict[str, Any]]:
    return public_many(await db.coupons.find({"merchant_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100))


@api.post("/merchant/coupons")
async def create_coupon(payload: CouponCreate, user: Dict[str, Any] = Depends(require_roles("merchant"))) -> Dict[str, Any]:
    code = payload.code.strip().upper()
    if not code:
        raise HTTPException(400, "Coupon code required")
    if await db.coupons.find_one({"code": code}):
        raise HTTPException(400, "Coupon code already exists")
    coupon = {"id": str(uuid.uuid4()), "code": code, "description": payload.description, "discount_percent": payload.discount_percent, "course_id": payload.course_id, "merchant_id": user["id"], "status": "pending", "title": f"{payload.discount_percent}% off", "subtitle": payload.description or "Merchant coupon awaiting approval.", "created_at": now()}
    await db.coupons.insert_one(coupon.copy())
    await audit(user, "Coupon submitted", "Coupons", code, coupon["id"])
    return coupon


# ---------- Admin ----------
@api.get("/admin/dashboard")
async def admin_dashboard(user: Dict[str, Any] = Depends(require_roles("admin"))) -> Dict[str, Any]:
    revenue = 0.0
    for p in await db.payments.find({"status": "succeeded"}, {"_id": 0, "amount_total": 1, "amount": 1}).to_list(2000):
        if p.get("amount_total"):
            revenue += float(p["amount_total"]) / 100.0  # Stripe returns paise for INR
        else:
            revenue += float(p.get("amount") or 0)  # stored as rupees at checkout create
    return {
        "total_students": await db.users.count_documents({"role": "student"}),
        "active_institutes": await db.institutes.count_documents({"status": "approved"}),
        "active_courses": await db.courses.count_documents({"status": "published"}),
        "pending_courses": await db.courses.count_documents({"status": "under_review"}),
        "pending_coupons": await db.coupons.count_documents({"status": "pending"}),
        "pending_refunds": await db.refunds.count_documents({"status": "pending"}),
        "revenue": revenue,
        "new_registrations": await db.merchant_registrations.count_documents({"status": "pending"}),
        "alerts": ["Review new institute applications", "Review pending courses & coupons", "Monitor refund requests"],
    }


@api.get("/admin/institutes")
async def admin_institutes(user: Dict[str, Any] = Depends(require_roles("admin"))) -> List[Dict[str, Any]]:
    return public_many(await db.institutes.find({}, {"_id": 0}).sort("status", 1).to_list(100))


@api.post("/admin/institutes/{institute_id}/status")
async def institute_status(institute_id: str, status: str = Query(..., pattern="^(approved|rejected|suspended|pending)$"), user: Dict[str, Any] = Depends(require_roles("admin"))) -> Dict[str, Any]:
    result = await db.institutes.update_one({"id": institute_id}, {"$set": {"status": status}})
    if result.matched_count == 0:
        raise HTTPException(404, "Institute not found")
    await audit(user, f"Institute {status}", "Institutes", institute_id, institute_id)
    return {"id": institute_id, "status": status}


@api.get("/admin/courses")
async def admin_courses(user: Dict[str, Any] = Depends(require_roles("admin"))) -> List[Dict[str, Any]]:
    return public_many(await db.courses.find({"status": {"$in": ["under_review", "published", "rejected"]}}, {"_id": 0}).sort("status", 1).to_list(200))


@api.post("/admin/courses/{course_id}/status")
async def course_status(course_id: str, status: str = Query(..., pattern="^(published|rejected|under_review)$"), user: Dict[str, Any] = Depends(require_roles("admin"))) -> Dict[str, Any]:
    result = await db.courses.update_one({"id": course_id}, {"$set": {"status": status}})
    if result.matched_count == 0:
        raise HTTPException(404, "Course not found")
    await audit(user, f"Course {status}", "Courses", course_id, course_id)
    return {"id": course_id, "status": status}


@api.get("/admin/coupons")
async def admin_coupons(user: Dict[str, Any] = Depends(require_roles("admin"))) -> List[Dict[str, Any]]:
    rows = public_many(await db.coupons.find({}, {"_id": 0}).sort("status", 1).to_list(200))
    for row in rows:
        merchant = await db.users.find_one({"id": row.get("merchant_id")}, {"_id": 0, "full_name": 1, "mobile": 1})
        row["merchant"] = public(merchant)
    return rows


@api.post("/admin/coupons/{coupon_id}/status")
async def coupon_status(coupon_id: str, status: str = Query(..., pattern="^(approved|rejected|pending)$"), user: Dict[str, Any] = Depends(require_roles("admin"))) -> Dict[str, Any]:
    result = await db.coupons.update_one({"id": coupon_id}, {"$set": {"status": status}})
    if result.matched_count == 0:
        raise HTTPException(404, "Coupon not found")
    await audit(user, f"Coupon {status}", "Coupons", coupon_id, coupon_id)
    return {"id": coupon_id, "status": status}


@api.get("/admin/refunds")
async def admin_refunds(user: Dict[str, Any] = Depends(require_roles("admin"))) -> List[Dict[str, Any]]:
    return public_many(await db.refunds.find({}, {"_id": 0}).sort("created_at", -1).to_list(200))


@api.post("/admin/refunds/{refund_id}/action")
async def refund_action(refund_id: str, status: str = Query(..., pattern="^(approved|rejected|processed)$"), user: Dict[str, Any] = Depends(require_roles("admin"))) -> Dict[str, Any]:
    refund = await db.refunds.find_one({"id": refund_id}, {"_id": 0})
    if not refund:
        raise HTTPException(404, "Refund not found")
    await db.refunds.update_one({"id": refund_id}, {"$set": {"status": status, "resolved_at": now(), "resolved_by": user["id"]}})
    if status in ("approved", "processed"):
        await db.enrollments.update_one({"id": refund["enrollment_id"]}, {"$set": {"status": "refunded", "payment_status": "refunded"}})
    await audit(user, f"Refund {status}", "Refunds", refund.get("course_title", ""), refund_id)
    return {"id": refund_id, "status": status}


@api.get("/admin/audit-logs")
async def admin_audit_logs(user: Dict[str, Any] = Depends(require_roles("admin"))) -> List[Dict[str, Any]]:
    rows = public_many(await db.activity_logs.find({}, {"_id": 0}).sort("created_at", -1).to_list(100))
    return rows or [{"id": "seed-log", "action": "System ready", "module": "Platform", "role": "Admin", "created_at": now()}]


@api.get("/admin/activity")
async def admin_activity(user: Dict[str, Any] = Depends(require_roles("admin"))) -> List[Dict[str, Any]]:
    return await admin_audit_logs(user)


app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("shutdown")
async def shutdown_db_client() -> None:
    client.close()
