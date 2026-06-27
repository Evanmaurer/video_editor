import { join } from "path";
import { describe, expect, it } from "vitest";
import { resolveBackendDir, resolvePythonPath } from "../../electron/main/backend-paths";

const repoRoot = join(__dirname, "../../../..");
const desktopRoot = join(repoRoot, "apps/desktop");
const mainOutDir = join(desktopRoot, "out/main");

describe("resolveBackendDir", () => {
  it("finds apps/backend from repo root cwd", () => {
    expect(resolveBackendDir(repoRoot, mainOutDir)).toBe(join(repoRoot, "apps/backend"));
  });

  it("finds apps/backend from apps/desktop cwd", () => {
    expect(resolveBackendDir(desktopRoot, mainOutDir)).toBe(join(repoRoot, "apps/backend"));
  });

  it("finds apps/backend from compiled out/main location", () => {
    expect(resolveBackendDir(desktopRoot, mainOutDir)).toBe(join(repoRoot, "apps/backend"));
  });
});

describe("resolvePythonPath", () => {
  it("returns venv python when setup has been run", () => {
    const pythonPath = resolvePythonPath(repoRoot, mainOutDir);
    if (pythonPath) {
      expect(pythonPath).toContain(".venv");
      expect(pythonPath).toMatch(/python(\.exe)?$/);
    }
  });
});
