#!/usr/bin/env python3
"""
Convenience launcher for the CORZAAR IMS Backend Server.
Usage: python run.py
"""
import socket
import uvicorn
from app.core.config import settings

def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    local_ip = get_local_ip()
    print("=" * 60)
    print("  CORZAAR IMS Backend Server")
    print(f"  Web / Local:  http://localhost:{settings.PORT}")
    print(f"  Mobile / LAN: http://{local_ip}:{settings.PORT}")
    print("=" * 60)
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
