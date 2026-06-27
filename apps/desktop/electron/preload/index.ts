import { contextBridge, ipcRenderer } from "electron";

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
  revealInFolder: (path: string) => Promise<void>;
}

const montageAPI: MontageAPI = {
  getBackendConnection: () => ipcRenderer.invoke("backend:getConnection"),
  getBackendStatus: () => ipcRenderer.invoke("backend:getStatus"),
  backendRequest: (payload) => ipcRenderer.invoke("backend:request", payload),
  openDirectory: () => ipcRenderer.invoke("dialog:openDirectory"),
  openProject: () => ipcRenderer.invoke("dialog:openProject"),
  revealInFolder: (path: string) => ipcRenderer.invoke("shell:revealInFolder", path),
};

contextBridge.exposeInMainWorld("montageAPI", montageAPI);
