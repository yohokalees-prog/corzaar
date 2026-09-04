"""
CORZAAR IMS Backend Entrypoint.
Backward-compatible wrapper importing the enterprise modular FastAPI application from app.main.
"""
import uvicorn
from app.core.config import settings
from app.main import app, create_app

__all__ = ["app", "create_app"]

if __name__ == "__main__":
    uvicorn.run("server:app", host=settings.HOST, port=settings.PORT, reload=True)
