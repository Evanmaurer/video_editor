import { app } from "electron";
import { spawn, ChildProcess } from "child_process";
import { existsSync } from "fs";
import { join } from "path";

export type BackendStatus = "starting" | "ready" | "error" | "stopped";

export interface BackendConnection {
  url: string;
  token: string;
  wsUrl: string;
}

export class BackendManager {
  private process: ChildProcess | null = null;
  private connection: BackendConnection | null = null;
  private status: BackendStatus = "stopped";
  private errorMessage: string | null = null;

  async start(): Promise<BackendConnection> {
    if (this.connection) {
      return this.connection;
    }

    this.status = "starting";
    const pythonPath = this.resolvePythonPath();
    const backendDir = this.resolveBackendDir();

    return new Promise((resolve, reject) => {
      const env = {
        ...process.env,
        PYTHONUNBUFFERED: "1",
        MONTAGE_APP_DATA_DIR: join(app.getPath("userData"), "montage-ai"),
      };

      this.process = spawn(pythonPath, ["-m", "montage_backend.main"], {
        cwd: backendDir,
        env,
        stdio: ["ignore", "pipe", "pipe"],
      });

      let resolved = false;
      let stdoutBuffer = "";
      const timeout = setTimeout(() => {
        if (!resolved) {
          this.status = "error";
          this.errorMessage = "Backend startup timed out";
          reject(new Error(this.errorMessage));
        }
      }, 30000);

      this.process.stdout?.on("data", (chunk: Buffer) => {
        stdoutBuffer += chunk.toString();
        const lines = stdoutBuffer.split("\n");
        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith("{") && trimmed.includes("port")) {
            try {
              const ready = JSON.parse(trimmed) as { port: number; token: string };
              this.connection = {
                url: `http://127.0.0.1:${ready.port}`,
                token: ready.token,
                wsUrl: `ws://127.0.0.1:${ready.port}/ws?token=${ready.token}`,
              };
              this.status = "ready";
              resolved = true;
              clearTimeout(timeout);
              resolve(this.connection);
            } catch {
              // ignore non-json lines
            }
          }
        }
      });

      this.process.stderr?.on("data", (chunk: Buffer) => {
        console.error("[backend]", chunk.toString());
      });

      this.process.on("error", (err) => {
        this.status = "error";
        this.errorMessage = err.message;
        if (!resolved) {
          clearTimeout(timeout);
          reject(err);
        }
      });

      this.process.on("exit", (code) => {
        if (code !== 0 && code !== null && !resolved) {
          this.status = "error";
          this.errorMessage = `Backend exited with code ${code}`;
          clearTimeout(timeout);
          reject(new Error(this.errorMessage));
        }
        if (code !== null) {
          this.connection = null;
        }
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

  getStatus(): { status: BackendStatus; error: string | null } {
    return { status: this.status, error: this.errorMessage };
  }

  private resolvePythonPath(): string {
    const candidates = [
      join(process.cwd(), "apps/backend/.venv/bin/python"),
      join(process.cwd(), "../backend/.venv/bin/python"),
      join(__dirname, "../../../../backend/.venv/bin/python"),
    ];
    for (const candidate of candidates) {
      if (existsSync(candidate)) {
        return candidate;
      }
    }
    return process.platform === "win32" ? "python" : "python3";
  }

  private resolveBackendDir(): string {
    const candidates = [
      join(process.cwd(), "apps/backend"),
      join(process.cwd(), "../backend"),
      join(__dirname, "../../../../backend"),
    ];
    for (const candidate of candidates) {
      if (existsSync(join(candidate, "montage_backend"))) {
        return candidate;
      }
    }
    return join(process.cwd(), "apps/backend");
  }
}
