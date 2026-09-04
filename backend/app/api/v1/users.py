from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException
from app.core.database import db
from app.core.security import now, public, public_many
from app.dependencies.auth import current_user
from app.models.auth import ProfileUpdate
from app.models.enrollment import CartChange
from app.services.batch_service import get_session_reminders

router = APIRouter(prefix="/me", tags=["users"])


@router.get("")
async def me(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    """Retrieve authenticated user's profile."""
    return public(user) or {}


@router.put("/profile")
async def update_profile(payload: ProfileUpdate, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    """Update learner profile details and mark profile as complete."""
    updates = payload.model_dump()
    updates["profile_complete"] = True
    await db.users.update_one({"id": user["id"]}, {"$set": updates})
    updated = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    return public(updated) or {}


async def _user_list(user: Dict[str, Any], field: str) -> List[str]:
    record = await db.user_lists.find_one({"user_id": user["id"]}, {"_id": 0})
    return (record or {}).get(field, [])


@router.get("/lists")
async def lists(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    """Get student's saved cart and wishlist/favorites."""
    return {
        "cart": await _user_list(user, "cart"),
        "favorites": await _user_list(user, "favorites"),
    }


@router.post("/cart")
async def add_cart(payload: CartChange, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    """Add a course to cart."""
    course = await db.courses.find_one({"id": payload.course_id}, {"_id": 0})
    if not course:
        raise HTTPException(status_code=404, detail="Course unavailable")
    await db.user_lists.update_one({"user_id": user["id"]}, {"$addToSet": {"cart": payload.course_id}}, upsert=True)
    return await lists(user)


@router.delete("/cart/{course_id}")
async def remove_cart(course_id: str, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    """Remove a course from cart."""
    await db.user_lists.update_one({"user_id": user["id"]}, {"$pull": {"cart": course_id}})
    return await lists(user)


@router.post("/favorites")
async def add_favorite(payload: CartChange, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    """Add course to favorites / saved list."""
    await db.user_lists.update_one({"user_id": user["id"]}, {"$addToSet": {"favorites": payload.course_id}}, upsert=True)
    return await lists(user)


@router.delete("/favorites/{course_id}")
async def remove_favorite(course_id: str, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    """Remove course from favorites."""
    await db.user_lists.update_one({"user_id": user["id"]}, {"$pull": {"favorites": course_id}})
    return await lists(user)


@router.get("/notifications")
async def notifications(user: Dict[str, Any] = Depends(current_user)) -> List[Dict[str, Any]]:
    """Retrieve notifications combined with live session reminders."""
    rows = public_many(await db.notifications.find({"$or": [{"user_id": user["id"]}, {"user_id": "all"}]}, {"_id": 0}).sort("created_at", -1).to_list(20))
    reminders = await get_session_reminders(user["id"]) if user.get("role") == "student" else []
    combined = reminders + rows
    return combined or [{"id": "welcome", "title": "Welcome to CORZAAR", "body": "Complete your profile to unlock better recommendations.", "kind": "info", "created_at": now(), "read": False}]
