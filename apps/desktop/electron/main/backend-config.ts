import { app } from "electron";

/**
 * Reliable dev detection for electron-vite. Do not rely on app.isPackaged alone —
 * packaged detection can mis-route to the production dynamic-port spawn path.
 */
export function isDevelopmentMode(): boolean {
  if (process.env.ELECTRON_RENDERER_URL) {
    return true;
  }
  if (process.env.NODE_ENV === "development") {
    return true;
  }
  return !app.isPackaged;
}

/** Default development backend — must match between Electron and manually started servers. */
export const DEV_BACKEND_HOST = "127.0.0.1";
export const DEV_BACKEND_PORT = 8000;
export const DEV_BACKEND_URL = `http://${DEV_BACKEND_HOST}:${DEV_BACKEND_PORT}`;
export const DEV_AUTH_TOKEN = "montage-dev-token";

/** Vite dev-server origin (renderer). There is no API proxy — requests go directly to the backend URL via fetch. */
export const DEV_RENDERER_ORIGIN = "http://localhost:5173";

export interface ResolvedBackendConfig {
  url: string;
  token: string;
  /** Port passed to spawned Python process. 0 = OS-assigned (production only). */
  spawnPort: number;
  /** When true, never spawn — only connect to `url`. */
  externalOnly: boolean;
  /** In dev, ignore stdout port and always use `url`. */
  useFixedUrl: boolean;
  source: string;
}

function parsePort(value: string | undefined): number | null {
  if (!value?.trim()) {
    return null;
  }
  const port = Number(value);
  return Number.isInteger(port) && port > 0 ? port : null;
}

/**
 * Determines how Electron connects to the FastAPI backend.
 *
 * Development always resolves to http://127.0.0.1:8000 (never a random OS port).
 * Override with MONTAGE_BACKEND_URL or MONTAGE_HOST + MONTAGE_PORT.
 */
export function resolveBackendConfig(isDev: boolean): ResolvedBackendConfig {
  const explicitUrl = process.env.MONTAGE_BACKEND_URL?.trim();
  const explicitToken = process.env.MONTAGE_AUTH_TOKEN?.trim();

  if (explicitUrl) {
    return {
      url: explicitUrl.replace(/\/$/, ""),
      token: explicitToken ?? (isDev ? DEV_AUTH_TOKEN : ""),
      spawnPort: 0,
      externalOnly: true,
      useFixedUrl: true,
      source: "MONTAGE_BACKEND_URL",
    };
  }

  if (isDev) {
    const host = process.env.MONTAGE_HOST?.trim() || DEV_BACKEND_HOST;
    const port = parsePort(process.env.MONTAGE_PORT) ?? DEV_BACKEND_PORT;
    const url = `http://${host}:${port}`;
    const source =
      process.env.MONTAGE_HOST || process.env.MONTAGE_PORT
        ? "MONTAGE_HOST/MONTAGE_PORT"
        : "development-default";
    const externalOnly = process.env.MONTAGE_AUTO_SPAWN === "false";

    return {
      url,
      token: explicitToken ?? DEV_AUTH_TOKEN,
      spawnPort: port,
      externalOnly,
      useFixedUrl: true,
      source,
    };
  }

  return {
    url: "",
    token: "",
    spawnPort: 0,
    externalOnly: false,
    useFixedUrl: false,
    source: "production-spawn",
  };
}
