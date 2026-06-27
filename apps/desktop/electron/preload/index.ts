import { contextBridge, ipcRenderer, webUtils } from "electron";
import { pathToMontageFileUrl } from "../media-file-url";

export interface BackendRequestPayload {
  method: string;
  path: string;
  body?: unknown;
}

export interface BackendResponsePayload {
  ok: boolean;
  status: number;
  statusText: string;
  body: string;
  url: string;
}

export interface MontageAPI {
  getBackendConnection: () => Promise<{
    url: string;
    token: string;
    wsUrl: string;
  } | null>;
  getBackendStatus: () => Promise<{
    status: string;
    error: string | null;
    errorDetail: string | null;
    resolvedUrl: string | null;
    rendererOrigin: string | null;
    proxyUrl: null;
  }>;
  backendRequest: (payload: BackendRequestPayload) => Promise<BackendResponsePayload>;
  openDirectory: () => Promise<string | null>;
  openProject: () => Promise<string | null>;
  openVideoFiles: () => Promise<string[]>;
  importVideoFolder: () => Promise<string | null>;
  resolveImportPaths: (paths: string[]) => Promise<string[]>;
  getMediaFileUrl: (path: string) => string;
  getPlaybackVideoUrl: (filePath: string, proxyPath?: string | null) => Promise<string | null>;
  getThumbnailDataUrl: (path: string) => Promise<string | null>;
  getPathForFile: (file: File) => string | null;
  revealInFolder: (path: string) => Promise<void>;
}

const montageAPI: MontageAPI = {
  getBackendConnection: () => ipcRenderer.invoke("backend:getConnection"),
  getBackendStatus: () => ipcRenderer.invoke("backend:getStatus"),
  backendRequest: (payload) => ipcRenderer.invoke("backend:request", payload),
  openDirectory: () => ipcRenderer.invoke("dialog:openDirectory"),
  openProject: () => ipcRenderer.invoke("dialog:openProject"),
  openVideoFiles: () => ipcRenderer.invoke("dialog:openVideoFiles"),
  importVideoFolder: () => ipcRenderer.invoke("dialog:importVideoFolder"),
  resolveImportPaths: (paths) => ipcRenderer.invoke("import:resolvePaths", paths),
  getMediaFileUrl: (path: string) => {
    try {
      return pathToMontageFileUrl(path);
    } catch {
      return "";
    }
  },
  getPlaybackVideoUrl: (filePath: string, proxyPath?: string | null) =>
    ipcRenderer.invoke("media:getPlaybackVideoUrl", filePath, proxyPath ?? null),
  getThumbnailDataUrl: (path: string) => ipcRenderer.invoke("media:getThumbnailDataUrl", path),
  getPathForFile: (file: File) => {
    try {
      return webUtils.getPathForFile(file);
    } catch {
      const legacy = file as File & { path?: string };
      return legacy.path ?? null;
    }
  },
  revealInFolder: (path: string) => ipcRenderer.invoke("shell:revealInFolder", path),
};

contextBridge.exposeInMainWorld("montageAPI", montageAPI);
