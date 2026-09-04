from typing import Any, Dict, Optional
import jwt
from fastapi import Depends, Header, HTTPException
from app.core.config import settings
from app.core.database import db
from app.core.security import decode_token


async def current_user(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    """Extract and validate the authenticated user from the Authorization Bearer header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    token_str = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token_str)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session") from exc

    user = await db.users.find_one({"id": payload.get("sub")}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_roles(*roles: str):
    """Dependency generator that verifies the user possesses one of the allowed roles."""
    async def dependency(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Access denied for this role")
        return user
    return dependency


async def cert_auth(
    authorization: Optional[str] = Header(default=None),
    auth: Optional[str] = None,
) -> Dict[str, Any]:
    """Special authenticator for certificate downloads supporting both header and query param."""
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
    elif auth:
        token = auth

    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = decode_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid session") from exc

    user = await db.users.find_one({"id": payload.get("sub"), "role": "student"}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
