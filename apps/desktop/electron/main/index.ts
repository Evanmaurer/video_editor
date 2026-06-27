import { app, BrowserWindow, dialog, ipcMain, protocol, shell } from "electron";
import { join } from "path";
import { resolveImportPaths } from "../media-import";
import { handleMontageFileRequest } from "../media-protocol";
import { resolvePlaybackVideoUrl } from "../media-playback-url";
import { readImageDataUrl } from "../thumbnail-data-url";
import { BackendManager } from "./backend-manager";
import { registerBackendRequestHandler } from "./backend-request";

delete process.env.ELECTRON_RUN_AS_NODE;

protocol.registerSchemesAsPrivileged([
  {
    scheme: "montage-file",
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      corsEnabled: true,
      stream: true,
    },
  },
]);

let mainWindow: BrowserWindow | null = null;
const backendManager = new BackendManager();
registerBackendRequestHandler(backendManager);

function getDialogWindow(): BrowserWindow | undefined {
  return mainWindow ?? BrowserWindow.getFocusedWindow() ?? undefined;
}

async function showOpenDialog(options: Electron.OpenDialogOptions) {
  const window = getDialogWindow();
  if (window) {
    return dialog.showOpenDialog(window, options);
  }
  return dialog.showOpenDialog(options);
}

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

  mainWindow.webContents.on("did-fail-load", (_event, code, description, url) => {
    console.error(`[main] Failed to load ${url}: ${code} ${description}`);
  });

  if (process.env.ELECTRON_RENDERER_URL) {
    mainWindow.loadURL(process.env.ELECTRON_RENDERER_URL);
  } else {
    mainWindow.loadFile(join(__dirname, "../renderer/index.html"));
  }
}

app.whenReady().then(async () => {
  protocol.handle("montage-file", (request) => handleMontageFileRequest(request));

  let backendStartError: string | null = null;

  try {
    await backendManager.start();
  } catch (err) {
    backendStartError = err instanceof Error ? err.message : String(err);
    console.error("[main] Backend failed to start:", err);
  }

  createWindow();

  if (backendStartError && mainWindow) {
    mainWindow.webContents.openDevTools({ mode: "detach" });
  }

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
  const result = await showOpenDialog({
    properties: ["openDirectory", "createDirectory"],
  });
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  return result.filePaths[0];
});

ipcMain.handle("dialog:openProject", async () => {
  const result = await showOpenDialog({
    properties: ["openDirectory"],
    title: "Open MontageAI Project",
  });
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  return result.filePaths[0];
});

ipcMain.handle("dialog:openVideoFiles", async () => {
  const result = await showOpenDialog({
    properties: ["openFile", "multiSelections"],
    filters: [
      {
        name: "Video",
        extensions: ["mp4", "mov", "mkv", "webm", "avi", "m4v"],
      },
    ],
  });
  if (result.canceled) {
    return [];
  }
  return result.filePaths;
});

ipcMain.handle("dialog:importVideoFolder", async () => {
  const result = await showOpenDialog({
    properties: ["openDirectory"],
    title: "Import Video Folder",
  });
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  return result.filePaths[0]!;
});

ipcMain.handle("import:resolvePaths", (_event, paths: string[]) => {
  return resolveImportPaths(paths);
});

ipcMain.handle("media:getThumbnailDataUrl", async (_event, filePath: string) => {
  return readImageDataUrl(filePath);
});

ipcMain.handle(
  "media:getPlaybackVideoUrl",
  (_event, filePath: string, proxyPath: string | null) => {
    return resolvePlaybackVideoUrl(filePath, proxyPath);
  },
);

ipcMain.handle("shell:revealInFolder", (_event, filePath: string) => {
  shell.showItemInFolder(filePath);
});
