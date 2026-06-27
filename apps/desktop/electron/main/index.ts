import { app, BrowserWindow, dialog, ipcMain, shell } from "electron";
import { join } from "path";
import { BackendManager } from "./backend-manager";
import { registerBackendRequestHandler } from "./backend-request";

delete process.env.ELECTRON_RUN_AS_NODE;

let mainWindow: BrowserWindow | null = null;
const backendManager = new BackendManager();
registerBackendRequestHandler(backendManager);

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1600,
    height: 900,
    minWidth: 1280,
    minHeight: 720,
    backgroundColor: "#1a1a1a",
    show: false,
    webPreferences: {
      preload: join(__dirname, "../preload/index.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  mainWindow.on("ready-to-show", () => {
    mainWindow?.show();
  });

  if (process.env.ELECTRON_RENDERER_URL) {
    mainWindow.loadURL(process.env.ELECTRON_RENDERER_URL);
  } else {
    mainWindow.loadFile(join(__dirname, "../renderer/index.html"));
  }
}

app.whenReady().then(async () => {
  try {
    await backendManager.start();
  } catch (err) {
    console.error("[main] Backend failed to start:", err);
  }

  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  backendManager.stop();
});

ipcMain.handle("backend:getConnection", () => backendManager.getConnection());

ipcMain.handle("backend:getStatus", () => backendManager.getStatus());

ipcMain.handle("dialog:openDirectory", async () => {
  const result = await dialog.showOpenDialog(mainWindow!, {
    properties: ["openDirectory", "createDirectory"],
  });
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  return result.filePaths[0];
});

ipcMain.handle("dialog:openProject", async () => {
  const result = await dialog.showOpenDialog(mainWindow!, {
    properties: ["openDirectory"],
    title: "Open MontageAI Project",
  });
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  return result.filePaths[0];
});

ipcMain.handle("shell:revealInFolder", (_event, filePath: string) => {
  shell.showItemInFolder(filePath);
});
