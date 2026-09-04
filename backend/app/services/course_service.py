import re
from typing import Optional
from app.core.database import db


async def recalc_rating(collection: str, target_id: str) -> None:
    """Recalculate average rating and review counts for a course or institute."""
    field = "course_id" if collection == "courses" else "institute_id"
    reviews = await db.reviews.find({"target_type": collection, field: target_id}).to_list(500)
    if not reviews:
        return
    avg = round(sum(r["rating"] for r in reviews) / len(reviews), 1)
    await db[collection].update_one(
        {"id": target_id},
        {"$set": {"rating": avg, "reviews_count": len(reviews)}},
    )


def duration_weeks(text: str) -> Optional[int]:
    """Parse '10 weeks' / '3 months' / '1 year' / '14 days' -> total weeks."""
    if not text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*(week|month|year|day)", str(text).lower())
    if not match:
        return None
    n = float(match.group(1))
    unit = match.group(2)
    if unit == "week":
        return int(n)
    if unit == "month":
        return int(n * 4)
    if unit == "year":
        return int(n * 52)
    if unit == "day":
        return max(1, int(n / 7))
    return None


def duration_matches(text: str, bucket: str) -> bool:
    """Filter course duration according to duration bucket."""
    weeks = duration_weeks(text)
    if weeks is None:
        return True  # don't exclude when we can't parse
    if bucket == "under_1m":
        return weeks < 4
    if bucket == "1_3m":
        return 4 <= weeks <= 12
    if bucket == "3_6m":
        return 12 < weeks <= 26
    if bucket == "6_12m":
        return 26 < weeks <= 52
    if bucket == "over_1y":
        return weeks > 52
    return True
