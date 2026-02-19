const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electron', {
  openFolder: (p) => ipcRenderer.invoke('open-folder', p),
  openFile:   (p) => ipcRenderer.invoke('open-file', p),
})

contextBridge.exposeInMainWorld('API', 'http://127.0.0.1:5050/api')
