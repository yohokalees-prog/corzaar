import logging
from app.core.database import db, init_db_indexes
from app.core.security import hash_password

logger = logging.getLogger("corzaar.seed")


async def seed_demo_data() -> None:
    """Seed initial demo institutes, courses, and admin account if not already present."""
    await init_db_indexes()

    if await db.institutes.count_documents({}) == 0:
        await db.institutes.insert_many([
            {
                "id": "inst-apex",
                "name": "Apex Institute of Technology",
                "city": "Bengaluru",
                "rating": 4.8,
                "reviews_count": 0,
                "accreditation": "NAAC A+",
                "students": "12k+",
                "description": "Industry-led programs for the builders of tomorrow.",
                "image_key": "campus",
                "status": "approved",
                "merchant_id": None,
            },
            {
                "id": "inst-global",
                "name": "Global Business Academy",
                "city": "Mumbai",
                "rating": 4.7,
                "reviews_count": 0,
                "accreditation": "AICTE approved",
                "students": "8k+",
                "description": "Practical business education with a global outlook.",
                "image_key": "business",
                "status": "approved",
                "merchant_id": None,
            },
            {
                "id": "inst-design",
                "name": "Northstar Design School",
                "city": "Pune",
                "rating": 4.9,
                "reviews_count": 0,
                "accreditation": "UGC recognized",
                "students": "4k+",
                "description": "Make meaningful work with a sharp creative practice.",
                "image_key": "design",
                "status": "approved",
                "merchant_id": None,
            },
        ])
        logger.info("Demo institutes seeded.")

    if await db.courses.count_documents({}) == 0:
        await db.courses.insert_many([
            {
                "id": "course-product",
                "title": "Product Design Foundations",
                "institute_id": "inst-design",
                "category": "Design",
                "duration": "10 weeks",
                "fees": 14999,
                "rating": 4.9,
                "reviews_count": 0,
                "students": 1240,
                "mode": "Live online",
                "description": "Turn real user problems into clear, compelling product experiences.",
                "curriculum": ["Design research", "Interaction design", "Portfolio studio"],
                "status": "published",
                "is_featured": True,
                "image_key": "design",
                "merchant_id": None,
            },
            {
                "id": "course-data",
                "title": "Data Analytics with Python",
                "institute_id": "inst-apex",
                "category": "Technology",
                "duration": "12 weeks",
                "fees": 18999,
                "rating": 4.8,
                "reviews_count": 0,
                "students": 2100,
                "mode": "Hybrid",
                "description": "Build confidence with data, dashboards, and decision-making.",
                "curriculum": ["Python essentials", "SQL and dashboards", "Capstone project"],
                "status": "published",
                "is_featured": True,
                "image_key": "campus",
                "merchant_id": None,
            },
            {
                "id": "course-marketing",
                "title": "Digital Marketing Sprint",
                "institute_id": "inst-global",
                "category": "Business",
                "duration": "6 weeks",
                "fees": 0,
                "rating": 4.7,
                "reviews_count": 0,
                "students": 3850,
                "mode": "Self-paced",
                "description": "A free practical sprint covering growth, content, and campaign strategy.",
                "curriculum": ["Customer journeys", "Content systems", "Growth experiments"],
                "status": "published",
                "is_featured": True,
                "image_key": "business",
                "merchant_id": None,
            },
            {
                "id": "course-ai",
                "title": "Applied AI for Teams",
                "institute_id": "inst-apex",
                "category": "Technology",
                "duration": "8 weeks",
                "fees": 22999,
                "rating": 4.8,
                "reviews_count": 0,
                "students": 860,
                "mode": "Live online",
                "description": "Understand where AI creates leverage and how to ship responsibly.",
                "curriculum": ["AI foundations", "Workflow design", "Responsible deployment"],
                "status": "published",
                "is_featured": False,
                "image_key": "campus",
                "merchant_id": None,
            },
        ])
        logger.info("Demo courses seeded.")

    if not await db.users.find_one({"email": "admin@corzaar.com"}):
        await db.users.insert_one({
            "id": "admin-001",
            "email": "admin@corzaar.com",
            "password_hash": hash_password("Admin@123"),
            "role": "admin",
            "full_name": "CORZAAR Admin",
            "status": "active",
        })
        logger.info("Default admin user created.")
