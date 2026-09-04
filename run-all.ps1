Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "   Starting CORZAAR IMS (Backend & Frontend)" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

# 1. MongoDB Service
Write-Host "[1/3] Checking MongoDB service..." -ForegroundColor Yellow
$mongo = Get-Service -Name "*MongoDB*" -ErrorAction SilentlyContinue
if ($mongo -and $mongo.Status -ne "Running") {
    Start-Service -Name $mongo.Name
    Write-Host "MongoDB service started." -ForegroundColor Green
} else {
    Write-Host "MongoDB is running." -ForegroundColor Green
}

# 2. Backend
Write-Host "[2/3] Starting Backend server on http://localhost:8000..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\backend'; .\venv\Scripts\python.exe run.py"

# 3. Frontend
Write-Host "[3/3] Starting Frontend Expo on http://localhost:8081..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\frontend'; npx expo start --web"

Write-Host ""
Write-Host "===================================================" -ForegroundColor Green
Write-Host " Backend (Web/Local):  http://localhost:8000/api" -ForegroundColor Green
Write-Host " Backend (Mobile/LAN): http://192.168.1.11:8000/api" -ForegroundColor Green
Write-Host " Frontend Web:         http://localhost:8081" -ForegroundColor Green
Write-Host " Frontend Mobile:      Scan QR Code in Expo Go" -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Green
