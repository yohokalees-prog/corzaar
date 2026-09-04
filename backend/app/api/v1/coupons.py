from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from app.core.database import db
from app.dependencies.auth import require_roles
from app.models.coupon import CouponValidate

router = APIRouter(prefix="/coupons", tags=["coupons"])


@router.post("/validate")
async def validate_coupon(
    payload: CouponValidate,
    user: Dict[str, Any] = Depends(require_roles("student")),
) -> Dict[str, Any]:
    """Validate a coupon code against a specific course and calculate discount."""
    course = await db.courses.find_one({"id": payload.course_id}, {"_id": 0})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    coupon = await db.coupons.find_one({"code": payload.code.upper(), "status": "approved"}, {"_id": 0})
    if not coupon:
        raise HTTPException(status_code=400, detail="Coupon is invalid or not yet approved")

    if coupon.get("course_id") and coupon["course_id"] != payload.course_id:
        raise HTTPException(status_code=400, detail="Coupon is not valid for this course")

    if coupon.get("merchant_id") and coupon["merchant_id"] != course.get("merchant_id"):
        raise HTTPException(status_code=400, detail="Coupon is not valid for this course")

    fees = float(course.get("fees") or 0)
    discount = round(fees * (coupon["discount_percent"] / 100), 2)
    return {
        "code": coupon["code"],
        "discount_percent": coupon["discount_percent"],
        "discount": discount,
        "final": max(0.0, fees - discount),
    }
