const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('bm', {
  showNotification: (title, body) => ipcRenderer.send('notification', { title, body }),
  platform: process.platform,
});
