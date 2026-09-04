import io
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from app.core.config import settings
from app.core.database import db
from app.core.security import now, public, public_many
from app.dependencies.auth import cert_auth, require_roles
from app.models.coupon import CouponValidate
from app.models.enrollment import EnrollmentCreate, ProgressUpdate
from app.services.audit_service import audit
from app.services.certificate_service import (
    cert_html,
    issue_or_pend_certificate,
    load_template,
    render_certificate_pdf,
    verify_base_url,
)
from app.services.referral_service import grant_referral_bonus

router = APIRouter(tags=["enrollments"])


@router.post("/enrollments")
async def enroll(payload: EnrollmentCreate, user: Dict[str, Any] = Depends(require_roles("student"))) -> Dict[str, Any]:
    """Enroll student in a course with support for coupons, referral discounts, and wallet deductions."""
    course = await db.courses.find_one({"id": payload.course_id}, {"_id": 0})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    existing = await db.enrollments.find_one(
        {"student_id": user["id"], "course_id": payload.course_id, "status": {"$in": ["active", "pending_payment"]}},
        {"_id": 0},
    )
    if existing:
        return public(existing) or {}

    fees = float(course.get("fees") or 0)
    discount = 0.0
    coupon_code = None
    referral_used = None

    if payload.coupon_code and fees > 0:
        coupon = await db.coupons.find_one({"code": payload.coupon_code.upper(), "status": "approved"}, {"_id": 0})
        if coupon:
            if not coupon.get("course_id") or coupon["course_id"] == payload.course_id:
                if not coupon.get("merchant_id") or coupon["merchant_id"] == course.get("merchant_id"):
                    discount = round(fees * (coupon["discount_percent"] / 100), 2)
                    coupon_code = coupon["code"]

    if payload.referral_code and not coupon_code:
        referrer = await db.users.find_one({"referral_code": payload.referral_code.upper(), "role": "student"}, {"_id": 0})
        if referrer and referrer["id"] != user["id"]:
            if fees > 0:
                discount = round(fees * settings.REFERRAL_DISCOUNT_PERCENT / 100, 2)
            referral_used = payload.referral_code.upper()

    wallet_used = 0.0
    if payload.use_wallet:
        after_discount = max(0.0, fees - discount)
        wallet_used = min(float(user.get("wallet_balance") or 0), after_discount)

    final = max(0.0, fees - discount - wallet_used)
    status = "active" if final == 0 else "pending_payment"

    enrollment = {
        "id": str(uuid.uuid4()),
        "student_id": user["id"],
        "course_id": payload.course_id,
        "batch_id": payload.batch_id,
        "status": status,
        "progress": 0,
        "completed_items": [],
        "amount": final,
        "original_amount": fees,
        "discount": discount,
        "wallet_used": wallet_used,
        "coupon_code": coupon_code,
        "referral_code": referral_used,
        "payment_status": "paid" if final == 0 else "pending",
        "created_at": now(),
    }
    await db.enrollments.insert_one(enrollment.copy())

    if wallet_used:
        await db.users.update_one({"id": user["id"]}, {"$inc": {"wallet_balance": -wallet_used}})

    if final == 0:
        await audit(user, "Free enrollment", "Enrollments", course["title"], enrollment["id"])
        await grant_referral_bonus(enrollment)

    return enrollment


@router.get("/me/enrollments")
async def my_enrollments(user: Dict[str, Any] = Depends(require_roles("student"))) -> List[Dict[str, Any]]:
    """List all enrolled courses with course details."""
    rows = public_many(await db.enrollments.find({"student_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50))
    for row in rows:
        course = await db.courses.find_one(
            {"id": row["course_id"]},
            {"_id": 0, "title": 1, "image_key": 1, "duration": 1, "institute_id": 1, "curriculum": 1},
        )
        row["course"] = public(course)
    return rows


@router.post("/me/enrollments/{enrollment_id}/progress")
async def update_progress(
    enrollment_id: str,
    payload: ProgressUpdate,
    user: Dict[str, Any] = Depends(require_roles("student")),
) -> Dict[str, Any]:
    """Update completed curriculum checklist and issue certificate upon reaching requirement."""
    enrollment = await db.enrollments.find_one({"id": enrollment_id, "student_id": user["id"]}, {"_id": 0})
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    course = await db.courses.find_one({"id": enrollment["course_id"]}, {"_id": 0})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    curriculum = course.get("curriculum") or []
    completed = [c for c in payload.completed if c in curriculum]
    progress = int(round(len(completed) / max(1, len(curriculum)) * 100))
    updates = {"completed_items": completed, "progress": progress}

    cfg = course.get("certificate_config") or {}
    required = int(cfg.get("completion_percent") or 100)

    if curriculum and progress >= required and cfg.get("enabled", True):
        await db.enrollments.update_one({"id": enrollment_id}, {"$set": updates})
        cert = await issue_or_pend_certificate(user, {**enrollment, **updates}, course)
        if cert and cert.get("status") == "issued":
            updates["certificate_id"] = cert["certificate_id"]
            updates["completed_at"] = cert["completion_date"]

    await db.enrollments.update_one({"id": enrollment_id}, {"$set": updates})
    fresh = await db.enrollments.find_one({"id": enrollment_id}, {"_id": 0})
    return public(fresh) or {}


@router.get("/me/enrollments/{enrollment_id}/certificate", response_class=HTMLResponse)
async def get_certificate_html(
    enrollment_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    auth: Optional[str] = None,
) -> str:
    """View certificate as a browser-rendered HTML document."""
    user = await cert_auth(authorization, auth)
    cert = await db.certificates.find_one({"enrollment_id": enrollment_id, "student_id": user["id"]}, {"_id": 0})
    enrollment = await db.enrollments.find_one({"id": enrollment_id, "student_id": user["id"]}, {"_id": 0})
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    if not cert and enrollment.get("certificate_id"):
        cert = {
            "certificate_id": enrollment["certificate_id"],
            "status": "issued",
            "template_id": None,
            "certificate_name": "Certificate of Completion",
            "issue_date": enrollment.get("completed_at"),
            "completion_date": enrollment.get("completed_at"),
        }
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not available yet")

    course = await db.courses.find_one({"id": enrollment["course_id"]}, {"_id": 0}) or {}
    institute = await db.institutes.find_one({"id": course.get("institute_id")}, {"_id": 0}) or {}
    template = await load_template(cert.get("template_id"))
    name = user.get("full_name") or "CORZAAR learner"
    issued_at = ((cert.get("issue_date") or cert.get("completion_date") or "")[:10]) or datetime.now(timezone.utc).date().isoformat()
    verify_url = f"{verify_base_url(request)}/api/certificates/verify/{cert['certificate_id']}"

    return cert_html(
        name=name,
        course_title=course.get("title", "the CORZAAR course"),
        institute_name=institute.get("name", "CORZAAR"),
        cert_id=cert["certificate_id"],
        issued_at=issued_at,
        style=template.get("style", "classic"),
        accent=template.get("accent_color", "#1E3A5F"),
        signatory=template.get("signatory", ""),
        verify_url=verify_url,
        status=cert.get("status", "issued"),
    )


@router.get("/me/enrollments/{enrollment_id}/certificate.pdf")
async def get_certificate_pdf(
    enrollment_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    auth: Optional[str] = None,
) -> StreamingResponse:
    """Download official certificate as a PDF."""
    user = await cert_auth(authorization, auth)
    enrollment = await db.enrollments.find_one({"id": enrollment_id, "student_id": user["id"]}, {"_id": 0})
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    cert = await db.certificates.find_one({"enrollment_id": enrollment_id, "student_id": user["id"]}, {"_id": 0})
    if not cert and enrollment.get("certificate_id"):
        cert = {
            "certificate_id": enrollment["certificate_id"],
            "status": "issued",
            "template_id": None,
            "completion_date": enrollment.get("completed_at"),
            "issue_date": enrollment.get("completed_at"),
        }
    if not cert or cert.get("status") != "issued":
        raise HTTPException(status_code=404, detail="Certificate not available yet")

    course = await db.courses.find_one({"id": enrollment["course_id"]}, {"_id": 0}) or {}
    institute = await db.institutes.find_one({"id": course.get("institute_id")}, {"_id": 0}) or {}
    tpl = await load_template(cert.get("template_id"))
    issued_at = ((cert.get("issue_date") or cert.get("completion_date") or "")[:10]) or datetime.now(timezone.utc).date().isoformat()
    verify_url = f"{verify_base_url(request)}/api/certificates/verify/{cert['certificate_id']}/view"

    pdf = render_certificate_pdf(
        name=user.get("full_name") or "CORZAAR learner",
        course_title=course.get("title", "CORZAAR course"),
        institute_name=institute.get("name", "CORZAAR"),
        cert_id=cert["certificate_id"],
        issued_at=issued_at,
        style=tpl.get("style", "classic"),
        accent=tpl.get("accent_color", "#1E3A5F"),
        signatory=tpl.get("signatory", ""),
        verify_url=verify_url,
    )
    filename = f"CORZAAR-{cert['certificate_id']}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/me/enrollments/{enrollment_id}/share")
async def certificate_share(
    enrollment_id: str,
    request: Request,
    user: Dict[str, Any] = Depends(require_roles("student")),
) -> Dict[str, str]:
    """Generate pre-filled social sharing links for LinkedIn, Twitter/X, and WhatsApp."""
    enrollment = await db.enrollments.find_one({"id": enrollment_id, "student_id": user["id"]}, {"_id": 0})
    if not enrollment or not enrollment.get("certificate_id"):
        raise HTTPException(status_code=404, detail="Certificate not available yet")

    course = await db.courses.find_one({"id": enrollment["course_id"]}, {"_id": 0}) or {}
    base = verify_base_url(request)
    cert_url = f"{base}/api/me/enrollments/{enrollment_id}/certificate"
    verify_url = f"{base}/api/certificates/verify/{enrollment['certificate_id']}/view"

    title = f"I completed {course.get('title', 'a CORZAAR course')}"
    linkedin = f"https://www.linkedin.com/sharing/share-offsite/?url={quote_plus(verify_url)}"
    twitter = f"https://twitter.com/intent/tweet?text={quote_plus(title + ' on CORZAAR')}&url={quote_plus(verify_url)}"
    whatsapp = f"https://wa.me/?text={quote_plus(title + ' — ' + verify_url)}"

    return {
        "certificate_url": cert_url,
        "pdf_url": f"{cert_url}.pdf",
        "verify_url": verify_url,
        "linkedin": linkedin,
        "twitter": twitter,
        "whatsapp": whatsapp,
        "title": title,
    }
