import math
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.core.database import db
from app.core.security import now, public, public_many
from app.dependencies.auth import require_roles
from app.models.batch import AttendanceMark, BatchCreate, SessionAttendance, SessionCreate
from app.models.certificate import CertConfigUpdate, CertTemplateCreate
from app.models.coupon import CouponCreate
from app.models.course import CourseCreate
from app.models.merchant import MerchantRegistration
from app.services.audit_service import audit
from app.services.batch_service import generate_sessions
from app.services.merchant_service import merchant_earnings

router = APIRouter(prefix="/merchant", tags=["merchant"])


@router.post("/registrations")
async def merchant_registration(payload: MerchantRegistration) -> Dict[str, Any]:
    """Submit institute / merchant onboarding application for administrative review."""
    application = {"id": str(uuid.uuid4()), **payload.model_dump(), "status": "pending", "created_at": now()}
    await db.merchant_registrations.insert_one(application.copy())
    return {"id": application["id"], "status": "pending", "message": "Application submitted for admin review"}


@router.get("/dashboard")
async def merchant_dashboard(user: Dict[str, Any] = Depends(require_roles("merchant"))) -> Dict[str, Any]:
    """Retrieve merchant institute dashboard metrics, active courses, batches, and revenue."""
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


@router.get("/courses")
async def merchant_courses(user: Dict[str, Any] = Depends(require_roles("merchant"))) -> List[Dict[str, Any]]:
    """List all courses created by the merchant."""
    return public_many(await db.courses.find({"merchant_id": user["id"]}, {"_id": 0}).sort("status", 1).to_list(100))


@router.post("/courses")
async def create_merchant_course(
    payload: CourseCreate,
    user: Dict[str, Any] = Depends(require_roles("merchant")),
) -> Dict[str, Any]:
    """Submit a new course for administrative approval."""
    institute = await db.institutes.find_one({"merchant_id": user["id"]}, {"_id": 0, "id": 1})
    if not institute:
        raise HTTPException(status_code=400, detail="Institute profile missing. Contact admin.")

    course = {
        "id": str(uuid.uuid4()),
        **payload.model_dump(),
        "merchant_id": user["id"],
        "institute_id": institute["id"],
        "status": "under_review",
        "rating": 0,
        "reviews_count": 0,
        "students": 0,
        "mode": "Live online",
        "image_key": "campus",
        "created_at": now(),
    }
    await db.courses.insert_one(course.copy())
    await audit(user, "Course submitted", "Courses", course["title"], course["id"])
    return course


@router.get("/batches")
async def merchant_batches(user: Dict[str, Any] = Depends(require_roles("merchant"))) -> List[Dict[str, Any]]:
    """List batches managed by this merchant."""
    return public_many(await db.batches.find({"merchant_id": user["id"]}, {"_id": 0}).sort("start_date", -1).to_list(100))


@router.post("/batches")
async def create_merchant_batch(
    payload: BatchCreate,
    user: Dict[str, Any] = Depends(require_roles("merchant")),
) -> Dict[str, Any]:
    """Create a new batch with auto-generated scheduled sessions."""
    course = await db.courses.find_one({"id": payload.course_id, "merchant_id": user["id"]}, {"_id": 0, "title": 1})
    if not course:
        raise HTTPException(status_code=400, detail="Course not owned by this merchant")

    sessions = generate_sessions(payload.start_date, payload.end_date, payload.schedule)
    batch = {
        "id": str(uuid.uuid4()),
        **payload.model_dump(),
        "merchant_id": user["id"],
        "course_title": course["title"],
        "status": "active",
        "enrolled": 0,
        "sessions": sessions,
        "created_at": now(),
    }
    await db.batches.insert_one(batch.copy())
    await audit(user, "Batch created", "Batches", course["title"], batch["id"])
    return batch


@router.post("/batches/{batch_id}/sessions")
async def add_session(
    batch_id: str,
    payload: SessionCreate,
    user: Dict[str, Any] = Depends(require_roles("merchant")),
) -> Dict[str, Any]:
    """Add a session to a batch."""
    batch = await db.batches.find_one({"id": batch_id, "merchant_id": user["id"]}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    session = {"id": str(uuid.uuid4()), "date": payload.date, "topic": payload.topic or ""}
    await db.batches.update_one({"id": batch_id}, {"$push": {"sessions": session}})
    return session


@router.delete("/batches/{batch_id}/sessions/{session_id}")
async def remove_session(
    batch_id: str,
    session_id: str,
    user: Dict[str, Any] = Depends(require_roles("merchant")),
) -> Dict[str, Any]:
    """Remove a session from a batch."""
    result = await db.batches.update_one({"id": batch_id, "merchant_id": user["id"]}, {"$pull": {"sessions": {"id": session_id}}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Batch not found")
    await db.attendance.delete_many({"session_id": session_id})
    return {"removed": session_id}


@router.get("/batches/{batch_id}/attendance")
async def batch_attendance(
    batch_id: str,
    user: Dict[str, Any] = Depends(require_roles("merchant")),
) -> Dict[str, Any]:
    """Get attendance roster across sessions for enrolled students in this batch."""
    batch = await db.batches.find_one({"id": batch_id, "merchant_id": user["id"]}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    enrolled = public_many(await db.enrollments.find({"course_id": batch["course_id"], "status": "active"}, {"_id": 0}).to_list(200))
    students: List[Dict[str, Any]] = []
    for e in enrolled:
        s = await db.users.find_one({"id": e["student_id"]}, {"_id": 0, "id": 1, "full_name": 1, "mobile": 1})
        if s:
            marks = await db.attendance.find({"batch_id": batch_id, "student_id": s["id"]}, {"_id": 0}).to_list(500)
            students.append({
                "id": s["id"],
                "name": s.get("full_name") or "Learner",
                "mobile": s.get("mobile"),
                "sessions": len(marks),
                "present": sum(1 for m in marks if m.get("present")),
                "marks": {m.get("session_id"): m.get("present") for m in marks},
            })
    return {"batch": public(batch), "students": students}


@router.post("/batches/{batch_id}/sessions/{session_id}/attendance")
async def mark_session_attendance(
    batch_id: str,
    session_id: str,
    payload: SessionAttendance,
    user: Dict[str, Any] = Depends(require_roles("merchant")),
) -> Dict[str, Any]:
    """Record student presence or absence for a specific batch session."""
    batch = await db.batches.find_one({"id": batch_id, "merchant_id": user["id"]}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if not any(sess.get("id") == session_id for sess in batch.get("sessions", [])):
        raise HTTPException(status_code=404, detail="Session not found")

    await db.attendance.update_one(
        {"batch_id": batch_id, "session_id": session_id, "student_id": payload.student_id},
        {"$set": {
            "batch_id": batch_id,
            "session_id": session_id,
            "student_id": payload.student_id,
            "present": payload.present,
            "marked_by": user["id"],
            "marked_at": now(),
        }},
        upsert=True,
    )
    return {"batch_id": batch_id, "session_id": session_id, "student_id": payload.student_id, "present": payload.present}


@router.post("/batches/{batch_id}/attendance")
async def mark_attendance_legacy(
    batch_id: str,
    payload: AttendanceMark,
    user: Dict[str, Any] = Depends(require_roles("merchant")),
) -> Dict[str, Any]:
    """Legacy attendance endpoint."""
    batch = await db.batches.find_one({"id": batch_id, "merchant_id": user["id"]}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    entry = {
        "id": str(uuid.uuid4()),
        "batch_id": batch_id,
        "session_id": "legacy",
        "student_id": payload.student_id,
        "present": payload.present,
        "date": payload.date or now(),
        "marked_by": user["id"],
    }
    await db.attendance.insert_one(entry.copy())
    return entry


@router.get("/coupons")
async def merchant_coupons(user: Dict[str, Any] = Depends(require_roles("merchant"))) -> List[Dict[str, Any]]:
    """List coupons owned by this merchant."""
    return public_many(await db.coupons.find({"merchant_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100))


@router.post("/coupons")
async def create_coupon(
    payload: CouponCreate,
    user: Dict[str, Any] = Depends(require_roles("merchant")),
) -> Dict[str, Any]:
    """Create a new merchant discount coupon (pending admin approval)."""
    code = payload.code.strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="Coupon code required")
    if await db.coupons.find_one({"code": code}):
        raise HTTPException(status_code=400, detail="Coupon code already exists")

    coupon = {
        "id": str(uuid.uuid4()),
        "code": code,
        "description": payload.description,
        "discount_percent": payload.discount_percent,
        "course_id": payload.course_id,
        "merchant_id": user["id"],
        "status": "pending",
        "title": f"{payload.discount_percent}% off",
        "subtitle": payload.description or "Merchant coupon awaiting approval.",
        "created_at": now(),
    }
    await db.coupons.insert_one(coupon.copy())
    await audit(user, "Coupon submitted", "Coupons", code, coupon["id"])
    return coupon


@router.get("/payouts")
async def get_merchant_payouts(user: Dict[str, Any] = Depends(require_roles("merchant"))) -> Dict[str, Any]:
    """Get payout history and earnings balances for merchant."""
    earnings = await merchant_earnings(user["id"])
    history = public_many(await db.payouts.find({"merchant_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100))
    return {**earnings, "history": history}


@router.get("/insights")
async def merchant_insights(user: Dict[str, Any] = Depends(require_roles("merchant"))) -> Dict[str, Any]:
    """Analytics on rating trends, top courses, and curriculum drop-off rates."""
    my_courses = await db.courses.find({"merchant_id": user["id"]}, {"_id": 0}).to_list(200)
    course_ids = [c["id"] for c in my_courses]
    all_reviews = await db.reviews.find({"target_type": "courses", "course_id": {"$in": course_ids}}, {"_id": 0}).sort("created_at", 1).to_list(2000)

    buckets: Dict[str, List[int]] = defaultdict(list)
    for r in all_reviews:
        try:
            when = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")).date()
            week_start = (when - __import__("datetime").timedelta(days=when.weekday())).isoformat()
            buckets[week_start].append(int(r.get("rating") or 0))
        except (KeyError, ValueError):
            continue
    trend = [{"week": wk, "average": round(sum(vals) / len(vals), 2), "count": len(vals)} for wk, vals in sorted(buckets.items())]

    ranked = sorted(my_courses, key=lambda c: (float(c.get("rating") or 0)) * math.log1p(int(c.get("reviews_count") or 0)), reverse=True)
    top = [{"id": c["id"], "title": c["title"], "rating": c.get("rating", 0), "reviews_count": c.get("reviews_count", 0), "students": c.get("students", 0)} for c in ranked[:5]]

    dropoff: List[Dict[str, Any]] = []
    for c in my_courses:
        if not c.get("curriculum"):
            continue
        enrolls = await db.enrollments.find({"course_id": c["id"], "status": "active"}, {"_id": 0, "completed_items": 1}).to_list(1000)
        if not enrolls:
            continue
        total = len(enrolls)
        per_item = []
        for item in c["curriculum"]:
            completed = sum(1 for e in enrolls if item in (e.get("completed_items") or []))
            per_item.append({"item": item, "completed": completed, "pct": round(completed * 100 / total, 1)})
        dropoff.append({"id": c["id"], "title": c["title"], "enrolled": total, "items": per_item})

    return {"rating_trend": trend, "top_courses": top, "curriculum_dropoff": dropoff}


@router.get("/certificate-templates")
async def merchant_cert_templates(user: Dict[str, Any] = Depends(require_roles("merchant"))) -> List[Dict[str, Any]]:
    """List certificate templates created by this merchant."""
    return public_many(await db.certificate_templates.find({"merchant_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50))


@router.post("/certificate-templates")
async def create_cert_template(
    payload: CertTemplateCreate,
    user: Dict[str, Any] = Depends(require_roles("merchant")),
) -> Dict[str, Any]:
    """Create a new customized certificate template."""
    style = payload.style.lower()
    if style not in settings.CERT_TEMPLATE_STYLES:
        raise HTTPException(status_code=400, detail=f"Style must be one of {settings.CERT_TEMPLATE_STYLES}")
    if payload.image_base64 and len(payload.image_base64) > 800_000:
        raise HTTPException(status_code=400, detail="Template image too large (keep under 600KB)")

    tpl = {
        "id": str(uuid.uuid4()),
        "merchant_id": user["id"],
        "name": payload.name,
        "style": style,
        "accent_color": payload.accent_color,
        "signatory": payload.signatory,
        "image_base64": payload.image_base64,
        "status": "active",
        "created_at": now(),
        "updated_at": now(),
    }
    await db.certificate_templates.insert_one(tpl.copy())
    await audit(user, "Certificate template created", "Certificates", payload.name, tpl["id"])
    return tpl


@router.delete("/certificate-templates/{template_id}")
async def delete_cert_template(
    template_id: str,
    user: Dict[str, Any] = Depends(require_roles("merchant")),
) -> Dict[str, Any]:
    """Delete a certificate template and unlink it from courses."""
    result = await db.certificate_templates.delete_one({"id": template_id, "merchant_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    await db.courses.update_many({"certificate_config.template_id": template_id}, {"$set": {"certificate_config.template_id": None}})
    await audit(user, "Certificate template deleted", "Certificates", "", template_id)
    return {"removed": template_id}


@router.put("/courses/{course_id}/certificate")
async def set_course_cert_config(
    course_id: str,
    payload: CertConfigUpdate,
    user: Dict[str, Any] = Depends(require_roles("merchant")),
) -> Dict[str, Any]:
    """Update certificate configuration (auto/manual, completion %, template) for a course."""
    course = await db.courses.find_one({"id": course_id, "merchant_id": user["id"]}, {"_id": 0})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    method = payload.issue_method.lower()
    if method not in ("automatic", "manual"):
        raise HTTPException(status_code=400, detail="issue_method must be automatic or manual")

    if payload.template_id:
        tpl = await db.certificate_templates.find_one({"id": payload.template_id, "merchant_id": user["id"]}, {"_id": 0})
        if not tpl:
            raise HTTPException(status_code=400, detail="Template not owned by merchant")

    cfg = {
        "enabled": payload.enabled,
        "template_id": payload.template_id,
        "certificate_name": payload.certificate_name or "Certificate of Completion",
        "completion_percent": payload.completion_percent,
        "issue_method": method,
    }
    await db.courses.update_one({"id": course_id}, {"$set": {"certificate_config": cfg}})
    await audit(user, "Certificate config updated", "Certificates", course.get("title", ""), course_id)
    return {"course_id": course_id, "certificate_config": cfg}


@router.get("/certificates")
async def merchant_certificates(user: Dict[str, Any] = Depends(require_roles("merchant"))) -> Dict[str, Any]:
    """List certificates issued and awaiting approval for this merchant's courses."""
    rows = public_many(await db.certificates.find({"merchant_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(300))
    counts = {"issued": 0, "pending_approval": 0, "revoked": 0}
    for r in rows:
        st = r.get("status", "issued")
        counts[st] = counts.get(st, 0) + 1
    return {"certificates": rows, "counts": counts}


@router.post("/certificates/{cert_id}/approve")
async def merchant_approve_cert(
    cert_id: str,
    user: Dict[str, Any] = Depends(require_roles("merchant")),
) -> Dict[str, Any]:
    """Approve a pending completion certificate."""
    cert = await db.certificates.find_one({"id": cert_id, "merchant_id": user["id"]}, {"_id": 0})
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if cert["status"] != "pending_approval":
        raise HTTPException(status_code=400, detail="Certificate not pending approval")

    await db.certificates.update_one({"id": cert_id}, {"$set": {"status": "issued", "issue_date": now(), "approved_by": user["id"]}})
    await db.enrollments.update_one({"id": cert["enrollment_id"]}, {"$set": {"certificate_id": cert["certificate_id"], "completed_at": cert.get("completion_date")}})
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": cert["student_id"],
        "title": "Certificate issued",
        "body": f"Your certificate for {cert.get('course_title', 'the course')} is ready.",
        "kind": "cert",
        "created_at": now(),
        "read": False,
    })
    await audit(user, "Certificate approved", "Certificates", cert.get("course_title", ""), cert_id)
    return {"id": cert_id, "status": "issued"}


@router.post("/certificates/{cert_id}/reject")
async def merchant_reject_cert(
    cert_id: str,
    user: Dict[str, Any] = Depends(require_roles("merchant")),
) -> Dict[str, Any]:
    """Reject a pending completion certificate request."""
    cert = await db.certificates.find_one({"id": cert_id, "merchant_id": user["id"]}, {"_id": 0})
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")

    await db.certificates.update_one({"id": cert_id}, {"$set": {"status": "revoked", "revoked_by": user["id"], "revoked_at": now(), "revoke_reason": "Rejected during approval"}})
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": cert["student_id"],
        "title": "Certificate rejected",
        "body": f"Your certificate request for {cert.get('course_title', 'the course')} was not approved.",
        "kind": "cert",
        "created_at": now(),
        "read": False,
    })
    await audit(user, "Certificate rejected", "Certificates", cert.get("course_title", ""), cert_id)
    return {"id": cert_id, "status": "revoked"}
