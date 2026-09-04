import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.database import close_db
from app.services.seed_service import seed_demo_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("corzaar")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context for startup and graceful shutdown."""
    logger.info("Initializing CORZAAR IMS application...")
    try:
        await seed_demo_data()
        logger.info("Database and demo data initialized successfully.")
    except Exception as exc:
        logger.warning(f"Could not connect to MongoDB on startup ({exc}). The app will retry when requested.")
    yield
    logger.info("Shutting down CORZAAR IMS application...")
    await close_db()


def create_app() -> FastAPI:
    """FastAPI application factory."""
    application = FastAPI(
        title="CORZAAR IMS API",
        version="1.1.0",
        description="Enterprise Institute & Course Management System API",
        lifespan=lifespan,
    )

    # CORS configuration
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_origin_regex=".*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API routes
    application.include_router(api_router)

    @application.get("/health")
    async def root_health():
        return {"status": "ok"}

    return application


app = create_app()
