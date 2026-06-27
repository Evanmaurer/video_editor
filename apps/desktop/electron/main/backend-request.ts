import { ipcMain } from "electron";
import type { BackendManager } from "./backend-manager";

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

export function registerBackendRequestHandler(backendManager: BackendManager): void {
  ipcMain.handle(
    "backend:request",
    async (_event, payload: BackendRequestPayload): Promise<BackendResponsePayload> => {
      const connection = backendManager.getConnection();
      if (!connection) {
        throw new Error("Backend not connected");
      }

      const path = payload.path.startsWith("/") ? payload.path : `/${payload.path}`;
      const url = `${connection.url}${path}`;
      const method = payload.method.toUpperCase();

      const headers: Record<string, string> = {
        "X-Montage-Token": connection.token,
      };
      if (payload.body !== undefined) {
        headers["Content-Type"] = "application/json";
      }

      const response = await fetch(url, {
        method,
        headers,
        body: payload.body !== undefined ? JSON.stringify(payload.body) : undefined,
      });

      const body = await response.text();
      if (!response.ok) {
        console.error(
          `[backend:request] ${method} ${url} → HTTP ${response.status}\n${body}`,
        );
      }

      return {
        ok: response.ok,
        status: response.status,
        statusText: response.statusText,
        body,
        url,
      };
    },
  );
}
