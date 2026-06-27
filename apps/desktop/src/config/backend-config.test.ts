import { describe, expect, it, beforeEach, afterEach } from "vitest";
import {
  DEV_AUTH_TOKEN,
  DEV_BACKEND_PORT,
  DEV_BACKEND_URL,
  resolveBackendConfig,
} from "../../electron/main/backend-config";

describe("resolveBackendConfig", () => {
  const env = process.env;

  beforeEach(() => {
    process.env = { ...env };
    delete process.env.MONTAGE_BACKEND_URL;
    delete process.env.MONTAGE_HOST;
    delete process.env.MONTAGE_PORT;
    delete process.env.MONTAGE_AUTH_TOKEN;
    delete process.env.MONTAGE_AUTO_SPAWN;
  });

  afterEach(() => {
    process.env = env;
  });

  it("defaults to http://127.0.0.1:8000 in development with fixed URL", () => {
    const config = resolveBackendConfig(true);
    expect(config.url).toBe(DEV_BACKEND_URL);
    expect(config.spawnPort).toBe(DEV_BACKEND_PORT);
    expect(config.useFixedUrl).toBe(true);
    expect(config.source).toBe("development-default");
    expect(config.token).toBe(DEV_AUTH_TOKEN);
  });

  it("uses MONTAGE_BACKEND_URL when set", () => {
    process.env.MONTAGE_BACKEND_URL = "http://127.0.0.1:9000";
    const config = resolveBackendConfig(true);
    expect(config.url).toBe("http://127.0.0.1:9000");
    expect(config.externalOnly).toBe(true);
    expect(config.useFixedUrl).toBe(true);
    expect(config.source).toBe("MONTAGE_BACKEND_URL");
  });

  it("sets externalOnly when MONTAGE_AUTO_SPAWN=false", () => {
    process.env.MONTAGE_AUTO_SPAWN = "false";
    const config = resolveBackendConfig(true);
    expect(config.externalOnly).toBe(true);
    expect(config.url).toBe(DEV_BACKEND_URL);
  });

  it("uses dynamic spawn in production", () => {
    const config = resolveBackendConfig(false);
    expect(config.url).toBe("");
    expect(config.spawnPort).toBe(0);
    expect(config.useFixedUrl).toBe(false);
    expect(config.source).toBe("production-spawn");
  });
});
