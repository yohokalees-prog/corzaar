@echo off
echo ===================================================
echo   Starting CORZAAR IMS (Backend & Frontend)
echo ===================================================

echo [1/3] Checking MongoDB service...
sc query MongoDB | find "RUNNING" >nul
if errorlevel 1 (
    echo Starting MongoDB service...
    net start MongoDB
) else (
    echo MongoDB is running.
)

echo [2/3] Launching Backend Server on port 8000...
start "CORZAAR Backend" cmd /k "cd backend && venv\Scripts\python.exe run.py"

echo [3/3] Launching Frontend Expo (Web & App) on port 8081...
start "CORZAAR Frontend" cmd /k "cd frontend && npx expo start --web"

echo.
echo ===================================================
echo   Backend (Web/Local):  http://localhost:8000/api
echo   Backend (Mobile/LAN): http://192.168.1.11:8000/api
echo   Frontend Web:         http://localhost:8081
echo   Frontend Mobile:      Scan QR Code in Expo Go
echo ===================================================
