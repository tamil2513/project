@echo off
REM ─────────────────────────────────────────────────────────
REM  Saree Photography — One-click Setup and Run (Windows)
REM  Double-click this file to install and launch
REM ─────────────────────────────────────────────────────────

cd /d "%~dp0"

echo.
echo ================================================
echo   📷  Saree Photography Booking System
echo ================================================
echo.

echo → Installing Python dependencies...
pip install flask reportlab --quiet
echo   Done.
echo.

echo → Installing Node.js / Electron...
npm install --silent
echo   Done.
echo.

echo → Launching app...
npm start

pause
