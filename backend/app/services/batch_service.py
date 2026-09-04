import uuid
from datetime import datetime, date, timedelta
from typing import Any, Dict, List
from app.core.database import db
from app.core.security import now


def generate_sessions(start_date: str, end_date: str, schedule: str) -> List[Dict[str, Any]]:
    """Auto-generate session dates from start->end based on weekly schedule string."""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return []
    if end < start:
        return []

    weekdays = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
    lower = schedule.lower()
    matched = [num for name, num in weekdays.items() if name in lower]
    if not matched:
        matched = [0, 2, 4]  # default Mon/Wed/Fri

    sessions = []
    cur = start
    while cur <= end and len(sessions) < 60:
        if cur.weekday() in matched:
            sessions.append({"id": str(uuid.uuid4()), "date": cur.isoformat(), "topic": ""})
        cur += timedelta(days=1)
    return sessions


async def get_session_reminders(user_id: str) -> List[Dict[str, Any]]:
    """Return dynamic reminders for sessions occurring today or tomorrow for enrolled students."""
    today = date.today()
    tomorrow = today + timedelta(days=1)
    enrolls = await db.enrollments.find({"student_id": user_id, "status": "active"}, {"_id": 0, "course_id": 1}).to_list(200)
    course_ids = [e["course_id"] for e in enrolls]
    if not course_ids:
        return []

    batches = await db.batches.find({"course_id": {"$in": course_ids}, "status": "active"}, {"_id": 0}).to_list(200)
    reminders: List[Dict[str, Any]] = []
    for b in batches:
        for sess in b.get("sessions") or []:
            sess_date = sess.get("date", "")
            if sess_date == today.isoformat():
                reminders.append({
                    "id": f"rem-{sess.get('id')}-today",
                    "title": "Class today",
                    "body": f"{b.get('course_title', 'Your course')} · {sess_date}" + (f" · {b.get('meet_link')}" if b.get("meet_link") else ""),
                    "kind": "reminder",
                    "created_at": now(),
                    "read": False,
                    "link": b.get("meet_link"),
                })
            elif sess_date == tomorrow.isoformat():
                reminders.append({
                    "id": f"rem-{sess.get('id')}-tomorrow",
                    "title": "Class tomorrow",
                    "body": f"{b.get('course_title', 'Your course')} · {sess_date}",
                    "kind": "reminder",
                    "created_at": now(),
                    "read": False,
                    "link": b.get("meet_link"),
                })
    return reminders
