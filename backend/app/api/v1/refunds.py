import uuid
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException
from app.core.database import db
from app.core.security import now, public, public_many
from app.dependencies.auth import require_roles
from app.models.review import RefundRequest
from app.services.audit_service import audit

router = APIRouter(tags=["refunds"])


@router.post("/refunds")
async def request_refund(
    payload: RefundRequest,
    user: Dict[str, Any] = Depends(require_roles("student")),
) -> Dict[str, Any]:
    """Submit a refund request for an existing paid enrollment."""
    enrollment = await db.enrollments.find_one({"id": payload.enrollment_id, "student_id": user["id"]}, {"_id": 0})
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    if enrollment.get("payment_status") != "paid":
        raise HTTPException(status_code=400, detail="Only paid enrollments can be refunded")

    existing = await db.refunds.find_one({"enrollment_id": payload.enrollment_id}, {"_id": 0})
    if existing:
        return public(existing) or {}

    course = await db.courses.find_one({"id": enrollment["course_id"]}, {"_id": 0, "title": 1})
    refund = {
        "id": str(uuid.uuid4()),
        "enrollment_id": payload.enrollment_id,
        "student_id": user["id"],
        "student_name": user.get("full_name"),
        "course_id": enrollment["course_id"],
        "course_title": (course or {}).get("title"),
        "amount": enrollment.get("amount"),
        "reason": payload.reason,
        "status": "pending",
        "created_at": now(),
    }
    await db.refunds.insert_one(refund.copy())
    await audit(user, "Refund requested", "Refunds", (course or {}).get("title", ""), refund["id"])
    return refund


@router.get("/me/refunds")
async def my_refunds(user: Dict[str, Any] = Depends(require_roles("student"))) -> List[Dict[str, Any]]:
    """Retrieve all refund requests submitted by the student."""
    return public_many(await db.refunds.find({"student_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50))
