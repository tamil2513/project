const { app, BrowserWindow, ipcMain, shell } = require('electron')
const { spawn } = require('child_process')
const path = require('path')
const http = require('http')
const fs = require('fs')

let mainWindow
let pythonProcess

// ── Find the backend server executable ────────────────────────────────────────
// In production (packaged): uses the bundled PyInstaller exe in resources/server/
// In development (npm start): uses python3 directly
function startBackend() {
  let cmd, args, opts

  const bundledExe = path.join(process.resourcesPath, 'server', 'server.exe')
  const bundledBin = path.join(process.resourcesPath, 'server', 'server')

  if (app.isPackaged && fs.existsSync(bundledExe)) {
    // Windows packaged: run bundled .exe
    cmd  = bundledExe
    args = []
    opts = { stdio: ['ignore', 'pipe', 'pipe'] }
  } else if (app.isPackaged && fs.existsSync(bundledBin)) {
    // Mac/Linux packaged
    cmd  = bundledBin
    args = []
    opts = { stdio: ['ignore', 'pipe', 'pipe'] }
  } else {
    // Development: use system python3
    const scriptPath = path.join(__dirname, 'backend', 'server.py')
    cmd  = process.platform === 'win32' ? 'python' : 'python3'
    args = [scriptPath]
    opts = { cwd: __dirname, stdio: ['ignore', 'pipe', 'pipe'] }
  }

  pythonProcess = spawn(cmd, args, opts)
  pythonProcess.stdout?.on('data', d => console.log('[Backend]', d.toString().trim()))
  pythonProcess.stderr?.on('data', d => console.log('[Backend ERR]', d.toString().trim()))
  pythonProcess.on('error', err => console.error('[Backend failed]', err.message))
  console.log('Backend started:', cmd)
}

// ── Wait for backend to respond ────────────────────────────────────────────────
function waitForBackend(tries, cb) {
  if (tries <= 0) { cb(); return }
  const req = http.get('http://127.0.0.1:5050/api/ping', res => {
    if (res.statusCode === 200) cb()
    else retry()
  })
  req.on('error', retry)
  req.end()
  function retry() { setTimeout(() => waitForBackend(tries - 1, cb), 500) }
}

// ── Create window ──────────────────────────────────────────────────────────────
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 860,
    minWidth: 1024,
    minHeight: 640,
    backgroundColor: '#0a0a0f',
    autoHideMenuBar: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    show: false,
    icon: path.join(__dirname, 'frontend', 'assets', 'icon.ico')
  })

  mainWindow.loadFile(path.join(__dirname, 'frontend', 'index.html'))
  mainWindow.once('ready-to-show', () => mainWindow.show())
}

// ── IPC: open a folder in Explorer/Finder ─────────────────────────────────────
ipcMain.handle('open-folder', async (_, folderPath) => {
  // Resolve path relative to app or user data
  let resolved = folderPath
  if (!path.isAbsolute(folderPath)) {
    // In packaged app, data lives next to the exe in user's AppData
    const base = app.isPackaged
      ? path.join(app.getPath('userData'))
      : path.join(__dirname)
    resolved = path.join(base, folderPath)
  }
  // Create folder if it doesn't exist
  if (!fs.existsSync(resolved)) fs.mkdirSync(resolved, { recursive: true })
  await shell.openPath(resolved)
  return resolved
})

ipcMain.handle('open-file', async (_, filePath) => {
  if (fs.existsSync(filePath)) {
    await shell.openPath(filePath)
    return { ok: true }
  }
  return { ok: false }
})

// ── App lifecycle ──────────────────────────────────────────────────────────────
app.whenReady().then(() => {
  startBackend()
  waitForBackend(40, createWindow)
})

app.on('window-all-closed', () => {
  if (pythonProcess) pythonProcess.kill()
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', () => {
  if (pythonProcess) pythonProcess.kill()
})
