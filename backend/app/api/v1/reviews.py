import uuid
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from app.core.database import db
from app.core.security import now
from app.dependencies.auth import require_roles
from app.models.review import ReviewCreate
from app.services.course_service import recalc_rating

router = APIRouter(tags=["reviews"])


@router.post("/reviews")
async def create_review(
    payload: ReviewCreate,
    user: Dict[str, Any] = Depends(require_roles("student")),
) -> Dict[str, Any]:
    """Submit a rating and review for a course or institute (requires active enrollment)."""
    if payload.target_type not in ("courses", "institutes"):
        raise HTTPException(status_code=400, detail="Invalid target")

    if payload.target_type == "courses":
        e = await db.enrollments.find_one({"student_id": user["id"], "course_id": payload.target_id, "status": "active"})
        if not e:
            raise HTTPException(status_code=403, detail="Only enrolled students can review this course")
    else:
        course_ids = [c["id"] for c in await db.courses.find({"institute_id": payload.target_id}, {"_id": 0, "id": 1}).to_list(200)]
        e = await db.enrollments.find_one({"student_id": user["id"], "course_id": {"$in": course_ids}, "status": "active"})
        if not e:
            raise HTTPException(status_code=403, detail="Only enrolled students can review this institute")

    doc = {
        "id": str(uuid.uuid4()),
        "target_type": payload.target_type,
        "rating": payload.rating,
        "text": payload.text,
        "author_id": user["id"],
        "name": user.get("full_name") or "CORZAAR learner",
        "created_at": now(),
    }
    if payload.target_type == "courses":
        doc["course_id"] = payload.target_id
    else:
        doc["institute_id"] = payload.target_id

    try:
        await db.reviews.insert_one(doc.copy())
    except Exception:
        target_field = "course_id" if payload.target_type == "courses" else "institute_id"
        await db.reviews.update_one(
            {"target_type": payload.target_type, target_field: payload.target_id, "author_id": user["id"]},
            {"$set": {"rating": payload.rating, "text": payload.text, "created_at": now()}},
            upsert=True,
        )

    await recalc_rating(payload.target_type, payload.target_id)
    return doc
