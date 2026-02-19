#!/bin/bash
# ─────────────────────────────────────────────────────────
#  Saree Photography — One-click Setup & Run (macOS)
#  Double-click this file or run: bash START_MAC.sh
# ─────────────────────────────────────────────────────────

cd "$(dirname "$0")"
echo ""
echo "================================================"
echo "  📷  Saree Photography Booking System"
echo "================================================"
echo ""

# Install Python deps
echo "→ Installing Python dependencies..."
pip3 install flask reportlab --quiet
echo "  ✅ Python dependencies ready"
echo ""

# Install Node deps
echo "→ Installing Node.js / Electron..."
npm install --silent
echo "  ✅ Electron ready"
echo ""

# Launch
echo "→ Launching app..."
npm start
