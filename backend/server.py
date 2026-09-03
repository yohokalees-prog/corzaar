from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import logging
import os
import secrets
import uuid

import jwt
from bson import ObjectId
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get("DB_NAME", "corzaar")]
SECRET_KEY = os.environ.get("JWT_SECRET", "corzaar-development-secret-key-please-configure-64chars")
ALGORITHM = "HS256"

app = FastAPI(title="CORZAAR IMS API", version="1.0.0")
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


class PaymentConfirm(BaseModel):
    enrollment_id: str
    success: bool = True


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


@app.on_event("startup")
async def seed_demo_data() -> None:
    if await db.institutes.count_documents({}) == 0:
        institutes = [
            {"id": "inst-apex", "name": "Apex Institute of Technology", "city": "Bengaluru", "rating": 4.8, "accreditation": "NAAC A+", "students": "12k+", "description": "Industry-led programs for the builders of tomorrow.", "image_key": "campus", "status": "approved"},
            {"id": "inst-global", "name": "Global Business Academy", "city": "Mumbai", "rating": 4.7, "accreditation": "AICTE approved", "students": "8k+", "description": "Practical business education with a global outlook.", "image_key": "business", "status": "approved"},
            {"id": "inst-design", "name": "Northstar Design School", "city": "Pune", "rating": 4.9, "accreditation": "UGC recognized", "students": "4k+", "description": "Make meaningful work with a sharp creative practice.", "image_key": "design", "status": "approved"},
        ]
        await db.institutes.insert_many(institutes)
    if await db.courses.count_documents({}) == 0:
        courses = [
            {"id": "course-product", "title": "Product Design Foundations", "institute_id": "inst-design", "category": "Design", "duration": "10 weeks", "fees": 14999, "rating": 4.9, "students": 1240, "mode": "Live online", "description": "Turn real user problems into clear, compelling product experiences.", "curriculum": ["Design research", "Interaction design", "Portfolio studio"], "status": "published", "is_featured": True, "image_key": "design"},
            {"id": "course-data", "title": "Data Analytics with Python", "institute_id": "inst-apex", "category": "Technology", "duration": "12 weeks", "fees": 18999, "rating": 4.8, "students": 2100, "mode": "Hybrid", "description": "Build confidence with data, dashboards, and decision-making.", "curriculum": ["Python essentials", "SQL and dashboards", "Capstone project"], "status": "published", "is_featured": True, "image_key": "campus"},
            {"id": "course-marketing", "title": "Digital Marketing Sprint", "institute_id": "inst-global", "category": "Business", "duration": "6 weeks", "fees": 0, "rating": 4.7, "students": 3850, "mode": "Self-paced", "description": "A free practical sprint covering growth, content, and campaign strategy.", "curriculum": ["Customer journeys", "Content systems", "Growth experiments"], "status": "published", "is_featured": True, "image_key": "business"},
            {"id": "course-ai", "title": "Applied AI for Teams", "institute_id": "inst-apex", "category": "Technology", "duration": "8 weeks", "fees": 22999, "rating": 4.8, "students": 860, "mode": "Live online", "description": "Understand where AI creates leverage and how to ship responsibly.", "curriculum": ["AI foundations", "Workflow design", "Responsible deployment"], "status": "published", "is_featured": False, "image_key": "campus"},
        ]
        await db.courses.insert_many(courses)
    if not await db.users.find_one({"email": "admin@corzaar.com"}):
        await db.users.insert_one({"id": "admin-001", "email": "admin@corzaar.com", "password_hash": hashlib.sha256(b"Admin@123").hexdigest(), "role": "admin", "full_name": "CORZAAR Admin", "status": "active"})


@api.get("/")
async def root() -> Dict[str, str]:
    return {"message": "CORZAAR IMS API", "status": "ok"}


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


@api.get("/home")
async def home() -> Dict[str, Any]:
    courses = public_many(await db.courses.find({"status": "published"}, {"_id": 0}).sort("rating", -1).to_list(20))
    institutes = public_many(await db.institutes.find({"status": "approved"}, {"_id": 0}).sort("rating", -1).to_list(10))
    return {"hero": {"eyebrow": "LEARN WITH PURPOSE", "title": "Your next chapter starts here.", "subtitle": "Discover trusted institutes, practical courses, and a path that feels like yours.", "offer": "Scholarships up to 40% this month"}, "courses": courses, "institutes": institutes, "categories": ["All", "Design", "Technology", "Business", "Marketing"]}


@api.get("/courses")
async def courses(q: str = "", category: str = "All", price_max: Optional[float] = None) -> List[Dict[str, Any]]:
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
    related = public_many(await db.courses.find({"category": course["category"], "id": {"$ne": course_id}}, {"_id": 0}).to_list(4))
    return {"course": course, "institute": institute, "related": related, "reviews": [{"name": "Ananya Mehta", "rating": 5, "text": "A clear, thoughtful learning experience."}, {"name": "Rohan Shah", "rating": 5, "text": "The capstone made my portfolio stronger."}]}


@api.get("/institutes/{institute_id}")
async def institute_detail(institute_id: str) -> Dict[str, Any]:
    institute = public(await db.institutes.find_one({"id": institute_id}, {"_id": 0}))
    if not institute:
        raise HTTPException(404, "Institute not found")
    institute["courses"] = public_many(await db.courses.find({"institute_id": institute_id}, {"_id": 0}).to_list(20))
    institute["testimonials"] = [{"name": "Kavya Iyer", "text": "Supportive mentors and a very practical curriculum."}]
    institute["gallery"] = ["campus", "classroom", "workshop"]
    return institute


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


@api.post("/enrollments")
async def enroll(payload: EnrollmentCreate, user: Dict[str, Any] = Depends(require_roles("student"))) -> Dict[str, Any]:
    course = await db.courses.find_one({"id": payload.course_id}, {"_id": 0})
    if not course:
        raise HTTPException(404, "Course not found")
    existing = await db.enrollments.find_one({"student_id": user["id"], "course_id": payload.course_id}, {"_id": 0})
    if existing:
        return public(existing) or {}
    status = "active" if course.get("fees", 0) == 0 else "pending_payment"
    enrollment = {"id": str(uuid.uuid4()), "student_id": user["id"], "course_id": payload.course_id, "batch_id": payload.batch_id, "status": status, "progress": 0, "created_at": now()}
    await db.enrollments.insert_one(enrollment.copy())
    return enrollment


@api.post("/payments/confirm")
async def confirm_payment(payload: PaymentConfirm, user: Dict[str, Any] = Depends(require_roles("student"))) -> Dict[str, Any]:
    enrollment = await db.enrollments.find_one({"id": payload.enrollment_id, "student_id": user["id"]}, {"_id": 0})
    if not enrollment:
        raise HTTPException(404, "Enrollment not found")
    status = "active" if payload.success else "payment_failed"
    await db.enrollments.update_one({"id": payload.enrollment_id}, {"$set": {"status": status, "payment_status": "paid" if payload.success else "failed"}})
    return {"enrollment_id": payload.enrollment_id, "status": status, "receipt": f"CZ-{payload.enrollment_id[:8].upper()}" if payload.success else None}


@api.get("/me/enrollments")
async def enrollments(user: Dict[str, Any] = Depends(require_roles("student"))) -> List[Dict[str, Any]]:
    rows = public_many(await db.enrollments.find({"student_id": user["id"]}, {"_id": 0}).to_list(50))
    for row in rows:
        course = await db.courses.find_one({"id": row["course_id"]}, {"_id": 0, "title": 1, "image_key": 1, "duration": 1})
        row["course"] = public(course)
    return rows


@api.get("/me/notifications")
async def notifications(user: Dict[str, Any] = Depends(current_user)) -> List[Dict[str, Any]]:
    rows = public_many(await db.notifications.find({"$or": [{"user_id": user["id"]}, {"user_id": "all"}]}, {"_id": 0}).sort("created_at", -1).to_list(20))
    return rows or [{"id": "welcome", "title": "Welcome to CORZAAR", "body": "Complete your profile to unlock better recommendations.", "kind": "info", "created_at": now(), "read": False}]


@api.get("/offers")
async def offers() -> List[Dict[str, Any]]:
    return [{"id": "offer-40", "title": "Scholarship season", "subtitle": "Save up to 40% on selected programs", "code": "LEARN40", "color": "green"}, {"id": "offer-free", "title": "Start free", "subtitle": "Explore practical courses at no cost", "code": "FREE", "color": "orange"}]


@api.get("/placements")
async def placements(user: Dict[str, Any] = Depends(require_roles("student"))) -> List[Dict[str, Any]]:
    return [{"id": "placement-1", "company": "Pine Labs", "role": "Junior Product Designer", "location": "Bengaluru · Hybrid", "type": "Full-time", "eligible": True, "status": "Open"}, {"id": "placement-2", "company": "Brightside Labs", "role": "Data Analyst Intern", "location": "Remote", "type": "Internship", "eligible": True, "status": "Open"}]


@api.post("/merchant/registrations")
async def merchant_registration(payload: MerchantRegistration) -> Dict[str, Any]:
    application = {"id": str(uuid.uuid4()), **payload.model_dump(), "status": "pending", "created_at": now()}
    await db.merchant_registrations.insert_one(application.copy())
    return {"id": application["id"], "status": "pending", "message": "Application submitted for admin review"}


@api.get("/merchant/dashboard")
async def merchant_dashboard(user: Dict[str, Any] = Depends(require_roles("merchant"))) -> Dict[str, Any]:
    return {"active_courses": await db.courses.count_documents({"status": "published", "merchant_id": user["id"]}), "active_batches": 0, "enrollments": await db.enrollments.count_documents({}), "revenue": 0, "pending_approvals": await db.merchant_registrations.count_documents({"status": "pending"}), "announcements": ["Keep your course information current for better discovery."]}


@api.post("/merchant/courses")
async def merchant_course(payload: CourseCreate, user: Dict[str, Any] = Depends(require_roles("merchant"))) -> Dict[str, Any]:
    course = {"id": str(uuid.uuid4()), **payload.model_dump(), "merchant_id": user["id"], "status": "under_review", "rating": 0, "students": 0, "image_key": "campus"}
    await db.courses.insert_one(course.copy())
    return course


@api.post("/merchant/batches")
async def merchant_batch(payload: BatchCreate, user: Dict[str, Any] = Depends(require_roles("merchant"))) -> Dict[str, Any]:
    batch = {"id": str(uuid.uuid4()), **payload.model_dump(), "merchant_id": user["id"], "status": "active", "enrolled": 0}
    await db.batches.insert_one(batch.copy())
    return batch


@api.get("/admin/dashboard")
async def admin_dashboard(user: Dict[str, Any] = Depends(require_roles("admin"))) -> Dict[str, Any]:
    return {"total_students": await db.users.count_documents({"role": "student"}), "active_institutes": await db.institutes.count_documents({"status": "approved"}), "active_courses": await db.courses.count_documents({"status": "published"}), "revenue": 0, "new_registrations": await db.merchant_registrations.count_documents({"status": "pending"}), "alerts": ["Review new institute applications", "2 payment records need attention"]}


@api.get("/admin/institutes")
async def admin_institutes(user: Dict[str, Any] = Depends(require_roles("admin"))) -> List[Dict[str, Any]]:
    return public_many(await db.institutes.find({}, {"_id": 0}).sort("status", 1).to_list(100))


@api.post("/admin/institutes/{institute_id}/status")
async def institute_status(institute_id: str, status: str = Query(..., pattern="^(approved|rejected|suspended|pending)$"), user: Dict[str, Any] = Depends(require_roles("admin"))) -> Dict[str, Any]:
    result = await db.institutes.update_one({"id": institute_id}, {"$set": {"status": status}})
    if result.matched_count == 0:
        raise HTTPException(404, "Institute not found")
    return {"id": institute_id, "status": status}


@api.get("/admin/activity")
async def admin_activity(user: Dict[str, Any] = Depends(require_roles("admin"))) -> List[Dict[str, Any]]:
    rows = public_many(await db.activity_logs.find({}, {"_id": 0}).sort("created_at", -1).to_list(50))
    return rows or [{"id": "seed-log", "action": "System ready", "module": "Platform", "role": "Admin", "created_at": now()}]


app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("shutdown")
async def shutdown_db_client() -> None:
    client.close()