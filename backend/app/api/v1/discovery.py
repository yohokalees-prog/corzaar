from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from app.core.config import settings
from app.core.database import db
from app.core.security import public, public_many
from app.dependencies.auth import require_roles
from app.services.course_service import duration_matches

router = APIRouter(tags=["discovery"])


@router.get("/home")
async def home() -> Dict[str, Any]:
    """Retrieve home screen discovery payload including featured courses, institutes, and dynamic categories."""
    courses = public_many(await db.courses.find({"status": "published"}, {"_id": 0}).sort("rating", -1).to_list(20))
    institutes = public_many(await db.institutes.find({"status": "approved"}, {"_id": 0}).sort("rating", -1).to_list(10))

    live_cats = sorted({c.get("category") for c in courses if c.get("category")})
    icon_map = {c["key"]: c["icon"] for c in settings.DEFAULT_CATEGORIES}
    discovery_cats = [{"key": k, "icon": icon_map.get(k, "school-outline")} for k in (live_cats or [c["key"] for c in settings.DEFAULT_CATEGORIES])]
    live_locs = sorted({(i.get("city") or "").strip() for i in institutes if (i.get("city") or "").strip()})

    return {
        "hero": {
            "eyebrow": "LEARN WITH PURPOSE",
            "title": "Your next chapter starts here.",
            "subtitle": "Discover trusted institutes, practical courses, and a path that feels like yours.",
            "offer": "Scholarships up to 40% this month",
        },
        "courses": courses,
        "institutes": institutes,
        "categories": ["All"] + [c["key"] for c in discovery_cats],
        "discovery_categories": discovery_cats,
        "popular_locations": (live_locs or settings.POPULAR_LOCATIONS)[:8],
        "duration_buckets": [
            {"key": "under_1m", "label": "Under 1 month"},
            {"key": "1_3m", "label": "1–3 months"},
            {"key": "3_6m", "label": "3–6 months"},
            {"key": "6_12m", "label": "6–12 months"},
            {"key": "over_1y", "label": "1+ year"},
        ],
    }


@router.get("/courses")
async def list_courses(
    q: str = "",
    category: str = "All",
    price_max: Optional[float] = None,
    price_min: Optional[float] = None,
    min_rating: Optional[float] = None,
    duration: Optional[str] = None,
    mode: Optional[str] = None,
    location: Optional[str] = None,
    has_certificate: Optional[bool] = None,
    free_only: Optional[bool] = None,
    sort: str = "recommended",
) -> List[Dict[str, Any]]:
    """Multi-dimensional course search, filtering, and sorting."""
    query: Dict[str, Any] = {"status": "published"}
    if q:
        query["$or"] = [{"title": {"$regex": q, "$options": "i"}}, {"description": {"$regex": q, "$options": "i"}}]
    if category and category != "All":
        query["category"] = category

    price_expr: Dict[str, Any] = {}
    if price_max is not None:
        price_expr["$lte"] = price_max
    if price_min is not None:
        price_expr["$gte"] = price_min
    if free_only:
        price_expr = {"$lte": 0}
    if price_expr:
        query["fees"] = price_expr

    if min_rating is not None:
        query["rating"] = {"$gte": float(min_rating)}
    if mode:
        query["mode"] = {"$regex": mode, "$options": "i"}
    if has_certificate:
        query["certificate_config.enabled"] = True

    if location:
        inst_ids = [i["id"] for i in await db.institutes.find({"city": {"$regex": location, "$options": "i"}, "status": "approved"}, {"_id": 0, "id": 1}).to_list(100)]
        if inst_ids:
            query["institute_id"] = {"$in": inst_ids}
        else:
            return []

    sort_key = ("rating", -1)
    if sort == "newest":
        sort_key = ("created_at", -1)
    elif sort == "price_asc":
        sort_key = ("fees", 1)
    elif sort == "price_desc":
        sort_key = ("fees", -1)
    elif sort == "students":
        sort_key = ("students", -1)

    rows = public_many(await db.courses.find(query, {"_id": 0}).sort(*sort_key).to_list(100))
    if duration and duration != "all":
        rows = [r for r in rows if duration_matches(r.get("duration", ""), duration)]
    return rows


@router.get("/courses/{course_id}")
async def course_detail(course_id: str) -> Dict[str, Any]:
    """Retrieve course profile including institute details, related courses, reviews, and active batches."""
    course = public(await db.courses.find_one({"id": course_id}, {"_id": 0}))
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    institute = public(await db.institutes.find_one({"id": course["institute_id"]}, {"_id": 0}))
    related = public_many(await db.courses.find({"category": course["category"], "id": {"$ne": course_id}, "status": "published"}, {"_id": 0}).to_list(4))
    reviews = public_many(await db.reviews.find({"target_type": "courses", "course_id": course_id}, {"_id": 0}).sort("created_at", -1).to_list(20))
    batches = public_many(await db.batches.find({"course_id": course_id, "status": "active"}, {"_id": 0}).to_list(10))
    return {"course": course, "institute": institute, "related": related, "reviews": reviews, "batches": batches}


@router.get("/institutes/{institute_id}")
async def institute_detail(institute_id: str) -> Dict[str, Any]:
    """Retrieve institute profile including courses and reviews."""
    institute = public(await db.institutes.find_one({"id": institute_id}, {"_id": 0}))
    if not institute:
        raise HTTPException(status_code=404, detail="Institute not found")
    institute["courses"] = public_many(await db.courses.find({"institute_id": institute_id, "status": "published"}, {"_id": 0}).to_list(20))
    institute["testimonials"] = public_many(await db.reviews.find({"target_type": "institutes", "institute_id": institute_id}, {"_id": 0}).sort("created_at", -1).to_list(10))
    return institute


@router.get("/offers")
async def offers() -> List[Dict[str, Any]]:
    """List approved coupon offers available to students."""
    approved = public_many(await db.coupons.find({"status": "approved"}, {"_id": 0}).sort("created_at", -1).to_list(20))
    return approved or [{"id": "welcome-offer", "title": "Welcome offer", "subtitle": "Merchants can publish coupons here after admin approval.", "code": "SOON", "discount_percent": 0}]


@router.get("/placements")
async def placements(user: Dict[str, Any] = Depends(require_roles("student"))) -> List[Dict[str, Any]]:
    """List career and placement opportunities."""
    return [
        {"id": "placement-1", "company": "Pine Labs", "role": "Junior Product Designer", "location": "Bengaluru · Hybrid", "type": "Full-time", "eligible": True, "status": "Open"},
        {"id": "placement-2", "company": "Brightside Labs", "role": "Data Analyst Intern", "location": "Remote", "type": "Internship", "eligible": True, "status": "Open"},
    ]
