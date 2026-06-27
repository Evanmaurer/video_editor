import { contextBridge, ipcRenderer } from "electron";

export interface MontageAPI {
  getBackendConnection: () => Promise<{
    url: string;
    token: string;
    wsUrl: string;
  } | null>;
  getBackendStatus: () => Promise<{ status: string; error: string | null }>;
  openDirectory: () => Promise<string | null>;
  openProject: () => Promise<string | null>;
  revealInFolder: (path: string) => Promise<void>;
}

const montageAPI: MontageAPI = {
  getBackendConnection: () => ipcRenderer.invoke("backend:getConnection"),
  getBackendStatus: () => ipcRenderer.invoke("backend:getStatus"),
  openDirectory: () => ipcRenderer.invoke("dialog:openDirectory"),
  openProject: () => ipcRenderer.invoke("dialog:openProject"),
  revealInFolder: (path: string) => ipcRenderer.invoke("shell:revealInFolder", path),
};

contextBridge.exposeInMainWorld("montageAPI", montageAPI);
