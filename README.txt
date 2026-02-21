╔══════════════════════════════════════════════════════════════╗
║          📷  SHREE PHOTOGRAPHY — BOOKING SYSTEM             ║
╚══════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  STEP 1 — Run on your Mac (development)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  pip3 install flask reportlab --break-system-packages
  npm install
  npm start

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  STEP 2 — Push to GitHub (one time setup)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. Go to https://github.com/new
  2. Create a new PRIVATE repository called "saree-photography"
  3. In Terminal, inside this folder run:

     git init
     git add .
     git commit -m "Initial commit"
     git remote add origin https://github.com/YOUR_USERNAME/saree-photography.git
     git push -u origin main

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  STEP 3 — Build Windows .exe (automatic!)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Every time you want a new Windows installer, run:

     git tag v1.0.0
     git push origin v1.0.0

  GitHub Actions will automatically:
  ✅ Bundle Python into the app (no Python needed on Windows)
  ✅ Build a Windows installer (.exe)
  ✅ Attach it to a GitHub Release for download

  To download: Go to your repo → Releases → Download .exe

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  STEP 4 — Install on Windows (end users)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. Download SareePhotography-Setup.exe from GitHub Releases
  2. Double-click to install
  3. Open from Desktop shortcut
  ✅ No Python, no Node, no Terminal — just works!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  FILE STRUCTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  SareePhotography/
  ├── .github/
  │   └── workflows/
  │       └── build.yml     ← GitHub Actions (builds Windows .exe)
  ├── backend/
  │   ├── server.py         ← Flask API (all business logic)
  │   ├── server.spec       ← PyInstaller config (bundles Python)
  │   └── requirements.txt
  ├── frontend/
  │   └── index.html        ← Complete dark luxury UI
  ├── data/
  │   └── events.csv        ← ⚠️  BACK THIS UP — all your bookings!
  ├── invoices/             ← PDF invoices auto-saved here
  ├── calendars/            ← .ics calendar files saved here
  ├── main.js               ← Electron main process
  ├── preload.js            ← Electron bridge
  ├── package.json
  └── README.txt            ← This file

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  FEATURES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ✅ Advance 1 + Advance 2 split payments
  ✅ Auto balance calculation (Amount - Adv1 - Adv2)
  ✅ Double-booking conflict detection with real-time warning
  ✅ PDF invoice auto-generated on every save
  ✅ Calendar .ics export (Google/Apple/Outlook/Windows Calendar)
  ✅ Open Invoices/Calendars folder buttons
  ✅ Search + filter bookings
  ✅ Dark luxury UI (black + gold)
  ✅ Windows installer — no dependencies for end users

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ⚠️  IMPORTANT — BACKUP YOUR DATA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  All bookings are stored in:  data/events.csv
  Back this file up regularly!
