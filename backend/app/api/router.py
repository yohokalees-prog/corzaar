from typing import Dict
from fastapi import APIRouter
from app.api.v1 import (
    admin,
    auth,
    certificates,
    coupons,
    discovery,
    enrollments,
    merchant,
    payments,
    refunds,
    reviews,
    users,
    wallet,
)

api_router = APIRouter(prefix="/api")


@api_router.get("/")
@api_router.get("/health")
async def api_root() -> Dict[str, str]:
    """Health check and API root."""
    return {"message": "CORZAAR IMS API", "status": "ok"}


# Mount all modular sub-routers
api_router.include_router(auth.router)
api_router.include_router(discovery.router)
api_router.include_router(users.router)
api_router.include_router(enrollments.router)
api_router.include_router(certificates.router)
api_router.include_router(payments.router)
api_router.include_router(reviews.router)
api_router.include_router(coupons.router)
api_router.include_router(refunds.router)
api_router.include_router(wallet.router)
api_router.include_router(merchant.router)
api_router.include_router(admin.router)
