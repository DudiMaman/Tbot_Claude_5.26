const { app, BrowserWindow, Menu, Notification, shell, ipcMain } = require('electron');
const { autoUpdater } = require('electron-updater');
const path = require('path');

const ADMIN_URL = process.env.ADMIN_URL || 'https://app.building-management.co.il';

function createWindow() {
  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    autoHideMenuBar: false,
    title: 'ניהול מבנים',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  win.loadURL(ADMIN_URL);

  // Open external links in default browser
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith(ADMIN_URL)) {
      shell.openExternal(url);
      return { action: 'deny' };
    }
    return { action: 'allow' };
  });

  // Native menu
  const menu = Menu.buildFromTemplate([
    {
      label: 'קובץ',
      submenu: [
        { role: 'reload', label: 'רענון' },
        { role: 'quit', label: 'יציאה' },
      ],
    },
    {
      label: 'עריכה',
      submenu: [
        { role: 'undo', label: 'בטל' },
        { role: 'redo', label: 'בצע שוב' },
        { type: 'separator' },
        { role: 'cut', label: 'גזירה' },
        { role: 'copy', label: 'העתקה' },
        { role: 'paste', label: 'הדבקה' },
      ],
    },
  ]);
  Menu.setApplicationMenu(menu);
}

ipcMain.on('notification', (_event, { title, body }) => {
  new Notification({ title, body }).show();
});

app.whenReady().then(() => {
  createWindow();
  if (app.isPackaged) {
    autoUpdater.checkForUpdatesAndNotify().catch(() => {});
  }
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
