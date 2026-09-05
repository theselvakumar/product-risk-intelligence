# DRISHTI: Run Frontend Development Server
Write-Host "Starting DRISHTI Next.js Frontend on http://localhost:3000..." -ForegroundColor Cyan
$frontendDir = Join-Path $PSScriptRoot "..\frontend"
Set-Location $frontendDir

npm.cmd run dev
