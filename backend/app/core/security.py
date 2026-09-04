from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import hashlib
import secrets
import jwt
from app.core.config import settings


def now() -> str:
    """Return current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def public(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Sanitize MongoDB document by removing the internal `_id` field."""
    if not doc:
        return None
    return {key: value for key, value in doc.items() if key != "_id"}


def public_many(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sanitize a list of MongoDB documents."""
    return [item for item in (public(doc) for doc in docs) if item]


def token_for(user: Dict[str, Any]) -> str:
    """Generate a JWT token for a user with expiry."""
    payload = {
        "sub": user["id"],
        "role": user["role"],
        "exp": datetime.now(timezone.utc).timestamp() + settings.ACCESS_TOKEN_EXPIRE_SECONDS,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT token."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


def hash_password(password: str) -> str:
    """Hash password using SHA-256 (matching existing system)."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against hashed password."""
    return hash_password(plain_password) == hashed_password


def gen_referral(user_id: str) -> str:
    """Generate a unique referral code for a student."""
    return f"REF{user_id[:4].upper()}{secrets.token_hex(2).upper()}"
