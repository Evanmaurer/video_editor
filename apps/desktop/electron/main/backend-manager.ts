import { app } from "electron";
import { spawn, ChildProcess } from "child_process";
import { join } from "path";
import {
  isDevelopmentMode,
  resolveBackendConfig,
  type ResolvedBackendConfig,
} from "./backend-config";
import { resolveBackendDir, resolvePythonPath } from "./backend-paths";

export type BackendStatus = "starting" | "ready" | "error" | "stopped";

export interface BackendConnection {
  url: string;
  token: string;
  wsUrl: string;
}

export interface BackendStatusInfo {
  status: BackendStatus;
  error: string | null;
  errorDetail: string | null;
  resolvedUrl: string | null;
  rendererOrigin: string | null;
  proxyUrl: null;
}

const READY_POLL_INTERVAL_MS = 100;
const STARTUP_TIMEOUT_MS = 60_000;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function buildConnection(baseUrl: string, token: string): BackendConnection {
  const url = baseUrl.replace(/\/$/, "");
  const wsBase = url.replace(/^http/, "ws");
  return {
    url,
    token,
    wsUrl: `${wsBase}/ws?token=${encodeURIComponent(token)}`,
  };
}

export async function waitForBackendReady(
  url: string,
  timeoutMs = STARTUP_TIMEOUT_MS,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let lastError = "Backend did not respond";

  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${url.replace(/\/$/, "")}/ready`, {
        signal: AbortSignal.timeout(2_000),
      });
      if (response.ok) {
        return;
      }
      lastError = `Backend /ready returned ${response.status}`;
    } catch (err) {
      lastError = err instanceof Error ? err.message : String(err);
    }
    await sleep(READY_POLL_INTERVAL_MS);
  }

  throw new Error(`Backend not ready: ${lastError}`);
}

export class BackendManager {
  private process: ChildProcess | null = null;
  private connection: BackendConnection | null = null;
  private status: BackendStatus = "stopped";
  private errorMessage: string | null = null;
  private errorDetail: string | null = null;
  private stderrBuffer = "";
  private resolvedUrl: string | null = null;
  private rendererOrigin: string | null = null;

  async start(): Promise<BackendConnection> {
    if (this.connection) {
      return this.connection;
    }

    const isDev = isDevelopmentMode();
    this.rendererOrigin = process.env.ELECTRON_RENDERER_URL ?? null;

    const config = resolveBackendConfig(isDev);

    if (config.url) {
      this.resolvedUrl = config.url;
    }

    if (config.externalOnly) {
      return this.connectExternal(buildConnection(config.url, config.token));
    }

    if (isDev && config.url) {
      try {
        return await this.connectExternal(buildConnection(config.url, config.token));
      } catch {
        // No existing server — spawn below.
      }
    }

    return this.spawnBackend(config);
  }

  private async connectExternal(connection: BackendConnection): Promise<BackendConnection> {
    this.status = "starting";
    this.errorMessage = null;
    this.errorDetail = null;

    try {
      await waitForBackendReady(connection.url);
      await this.assertMediaLibraryAvailable(connection.url);
      this.connection = connection;
      this.resolvedUrl = connection.url;
      this.status = "ready";
      return connection;
    } catch (err) {
      this.status = "error";
      this.errorMessage = err instanceof Error ? err.message : String(err);
      this.errorDetail = this.errorMessage;
      throw err;
    }
  }

  private async assertMediaLibraryAvailable(baseUrl: string): Promise<void> {
    const response = await fetch(`${baseUrl.replace(/\/$/, "")}/health`, {
      signal: AbortSignal.timeout(2_000),
    });
    if (!response.ok) {
      throw new Error(`Backend health check failed: HTTP ${response.status}`);
    }
    const health = (await response.json()) as { features?: string[] };
    if (!health.features?.includes("media_library")) {
      throw new Error(
        "Connected backend is missing the media library API. Stop any old backend on port 8000 and restart the app.",
      );
    }
  }

  private async spawnBackend(config: ResolvedBackendConfig): Promise<BackendConnection> {
    this.status = "starting";
    this.errorMessage = null;
    this.errorDetail = null;
    this.stderrBuffer = "";

    const backendDir = resolveBackendDir(process.cwd(), __dirname);
    const pythonPath = resolvePythonPath(process.cwd(), __dirname);

    if (!backendDir) {
      const message = "Could not find apps/backend. Run ./scripts/setup.sh from the repo root.";
      this.setError(message);
      throw new Error(message);
    }

    if (!pythonPath) {
      const message =
        `Python venv not found at ${join(backendDir, ".venv")}. Run ./scripts/setup.sh.`;
      this.setError(message);
      throw new Error(message);
    }

    const spawnEnv: NodeJS.ProcessEnv = {
      ...process.env,
      PYTHONUNBUFFERED: "1",
      MONTAGE_APP_DATA_DIR: join(app.getPath("userData"), "montage-ai"),
    };

    if (config.spawnPort > 0) {
      spawnEnv.MONTAGE_PORT = String(config.spawnPort);
      spawnEnv.MONTAGE_HOST = new URL(config.url).hostname;
    } else {
      delete spawnEnv.MONTAGE_PORT;
    }

    if (config.token) {
      spawnEnv.MONTAGE_AUTH_TOKEN = config.token;
    }

    return new Promise((resolve, reject) => {
      this.process = spawn(pythonPath, ["-m", "montage_backend.main"], {
        cwd: backendDir,
        env: spawnEnv,
        stdio: ["ignore", "pipe", "pipe"],
      });

      let resolved = false;
      let stdoutBuffer = "";

      const timeout = setTimeout(() => {
        if (!resolved) {
          const message = "Backend startup timed out waiting for ready signal";
          this.setError(message, this.stderrBuffer);
          reject(new Error(message));
        }
      }, STARTUP_TIMEOUT_MS);

      const fail = (message: string) => {
        if (resolved) {
          return;
        }
        resolved = true;
        clearTimeout(timeout);
        this.setError(message, this.stderrBuffer);
        reject(new Error(message));
      };

      const succeed = async (connection: BackendConnection) => {
        if (resolved) {
          return;
        }
        try {
          await waitForBackendReady(connection.url);
          await this.assertMediaLibraryAvailable(connection.url);
          resolved = true;
          clearTimeout(timeout);
          this.connection = connection;
          this.resolvedUrl = connection.url;
          this.status = "ready";
          resolve(connection);
        } catch (err) {
          fail(err instanceof Error ? err.message : String(err));
        }
      };

      const connectionFromStdout = (ready: { port: number; token: string; host?: string }) => {
        if (config.useFixedUrl) {
          return buildConnection(config.url, config.token || ready.token);
        }
        const host = ready.host ?? "127.0.0.1";
        return buildConnection(`http://${host}:${ready.port}`, ready.token);
      };

      const tryConnectExisting = () => {
        if (!config.useFixedUrl || !config.url) {
          return;
        }
        void succeed(buildConnection(config.url, config.token));
      };

      this.process.stdout?.on("data", (chunk: Buffer) => {
        stdoutBuffer += chunk.toString();
        const lines = stdoutBuffer.split("\n");
        stdoutBuffer = lines.pop() ?? "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith("{") || !trimmed.includes("port")) {
            continue;
          }
          try {
            const ready = JSON.parse(trimmed) as {
              port: number;
              token: string;
              host?: string;
            };
            void succeed(connectionFromStdout(ready));
          } catch {
            // ignore non-json lines
          }
        }
      });

      this.process.stderr?.on("data", (chunk: Buffer) => {
        const text = chunk.toString();
        this.stderrBuffer += text;
        console.error("[backend]", text);

        if (
          !resolved &&
          config.useFixedUrl &&
          /address already in use|errno 48/i.test(text)
        ) {
          tryConnectExisting();
        }
      });

      this.process.on("error", (err) => {
        fail(err.message);
      });

      this.process.on("exit", (code, signal) => {
        if (resolved) {
          if (code !== 0 && code !== null) {
            this.setError(
              `Backend exited with code ${code}${signal ? ` (${signal})` : ""}`,
              this.stderrBuffer,
            );
            this.connection = null;
          }
          return;
        }

        if (
          config.useFixedUrl &&
          config.url &&
          /address already in use|errno 48/i.test(this.stderrBuffer)
        ) {
          tryConnectExisting();
          return;
        }

        const message =
          code === null
            ? `Backend terminated (${signal ?? "unknown signal"})`
            : `Backend exited with code ${code}`;
        fail(message);
      });
    });
  }

  stop(): void {
    if (this.process) {
      this.process.kill();
      this.process = null;
    }
    this.connection = null;
    this.status = "stopped";
  }

  getConnection(): BackendConnection | null {
    return this.connection;
  }

  getStatus(): BackendStatusInfo {
    return {
      status: this.status,
      error: this.errorMessage,
      errorDetail: this.errorDetail,
      resolvedUrl: this.resolvedUrl,
      rendererOrigin: this.rendererOrigin,
      proxyUrl: null,
    };
  }

  private setError(message: string, detail?: string): void {
    this.status = "error";
    this.errorMessage = message;
    const trimmed = detail?.trim();
    this.errorDetail = trimmed && trimmed.length > 0 ? trimmed : message;
  }
}
