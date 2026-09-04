from pathlib import Path
import os
from dotenv import load_dotenv

# Base backend directory
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BACKEND_DIR / ".env"
load_dotenv(ENV_PATH)

class Settings:
    # Server
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")

    # Database
    MONGO_URL: str = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    DB_NAME: str = os.getenv("DB_NAME", "corzaar")

    # Security
    JWT_SECRET: str = os.getenv("JWT_SECRET", "corzaar-development-secret-key-please-configure-64chars")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_SECONDS: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_SECONDS", str(30 * 86400)))

    # Stripe Payments
    STRIPE_API_KEY: str = os.getenv("STRIPE_API_KEY") or os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    APP_PAYMENT_RETURN_URL: str = os.getenv("APP_PAYMENT_RETURN_URL", "")

    # Business Rules
    REFERRAL_REWARD: float = 200.0  # INR credited to referrer wallet
    REFERRAL_DISCOUNT_PERCENT: int = 10
    MIN_CASHOUT: float = 500.0  # INR minimum cashout
    CERT_TEMPLATE_STYLES: list = ["classic", "modern", "bold"]
    
    # Discovery defaults
    POPULAR_LOCATIONS: list = ["Chennai", "Bengaluru", "Mumbai", "Hyderabad", "Delhi", "Pune"]
    DEFAULT_CATEGORIES: list = [
        {"key": "Design", "icon": "color-palette-outline"},
        {"key": "Technology", "icon": "code-slash-outline"},
        {"key": "AI / Machine Learning", "icon": "hardware-chip-outline"},
        {"key": "Data Science", "icon": "analytics-outline"},
        {"key": "Business", "icon": "briefcase-outline"},
        {"key": "Marketing", "icon": "megaphone-outline"},
        {"key": "Finance", "icon": "cash-outline"},
        {"key": "Language", "icon": "language-outline"},
        {"key": "Healthcare", "icon": "medkit-outline"},
        {"key": "Engineering", "icon": "construct-outline"},
    ]

settings = Settings()
