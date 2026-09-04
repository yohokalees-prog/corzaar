import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings

logger = logging.getLogger("corzaar.db")

client: AsyncIOMotorClient = AsyncIOMotorClient(settings.MONGO_URL)
db: AsyncIOMotorDatabase = client[settings.DB_NAME]


def get_db() -> AsyncIOMotorDatabase:
    return db


async def init_db_indexes() -> None:
    """Create essential MongoDB indexes for performance and constraints."""
    try:
        await db.payments.create_index("stripe_session_id", unique=True, sparse=True)
        await db.payments.create_index("stripe_event_id", unique=True, sparse=True)
        await db.reviews.create_index([("target_type", 1), ("target_id", 1), ("author_id", 1)], unique=True)
        await db.users.create_index("mobile", sparse=True)
        await db.users.create_index("email", sparse=True)
        await db.certificates.create_index("certificate_id", unique=True, sparse=True)
        await db.certificates.create_index("enrollment_id")
        await db.enrollments.create_index([("student_id", 1), ("course_id", 1)])
        logger.info("Database indexes initialized successfully.")
    except Exception as e:
        logger.warning(f"Index initialization notice: {e}")


async def close_db() -> None:
    """Close MongoDB connection pool."""
    client.close()
    logger.info("Database connection closed.")
