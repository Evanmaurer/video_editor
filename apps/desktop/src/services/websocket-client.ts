import type { WSEvent } from "@montage/shared-types";

type EventHandler = (event: WSEvent) => void;

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private handlers: Set<EventHandler> = new Set();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  async connect(): Promise<void> {
    const connection = await window.montageAPI.getBackendConnection();
    if (!connection) {
      throw new Error("Backend not connected");
    }

    return new Promise((resolve, reject) => {
      let settled = false;
      const timeout = setTimeout(() => {
        if (settled) {
          return;
        }
        settled = true;
        this.ws?.close();
        reject(new Error("WebSocket connection timed out"));
      }, 5_000);

      this.ws = new WebSocket(connection.wsUrl);

      this.ws.onopen = () => {
        if (settled) {
          return;
        }
        settled = true;
        clearTimeout(timeout);
        resolve();
      };

      this.ws.onerror = () => {
        if (settled) {
          return;
        }
        settled = true;
        clearTimeout(timeout);
        reject(new Error("WebSocket connection failed"));
      };

      this.ws.onmessage = (message) => {
        try {
          const event = JSON.parse(message.data as string) as WSEvent;
          this.handlers.forEach((handler) => handler(event));
        } catch {
          // ignore malformed messages
        }
      };

      this.ws.onclose = (event) => {
        clearTimeout(timeout);
        if (!settled) {
          settled = true;
          if (event.code === 1008) {
            reject(new Error("WebSocket rejected: invalid auth token"));
            return;
          }
          reject(new Error("WebSocket closed before connecting"));
          return;
        }
        this.scheduleReconnect();
      };
    });
  }

  onEvent(handler: EventHandler): () => void {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }
    this.ws?.close();
    this.ws = null;
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) {
      return;
    }
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      void this.connect().catch(() => {
        this.scheduleReconnect();
      });
    }, 3000);
  }
}

export const wsClient = new WebSocketClient();
