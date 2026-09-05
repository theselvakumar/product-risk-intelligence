# DRISHTI: Run Backend Development Server
Write-Host "Starting DRISHTI FastAPI Backend on http://localhost:8000..." -ForegroundColor Green
$backendDir = Join-Path $PSScriptRoot "..\backend"
Set-Location $backendDir

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
