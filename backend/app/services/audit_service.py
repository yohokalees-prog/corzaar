import uuid
from typing import Any, Dict
from app.core.database import db
from app.core.security import now


async def audit(user: Dict[str, Any], action: str, module: str, detail: str = "", target_id: str = "") -> None:
    """Log user activity to activity_logs collection for compliance and auditing."""
    await db.activity_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": action,
        "module": module,
        "role": user.get("role", ""),
        "actor_id": user.get("id"),
        "actor_name": user.get("full_name") or user.get("email") or user.get("mobile"),
        "detail": detail,
        "target_id": target_id,
        "created_at": now(),
    })
