import { existsSync } from "fs";
import { join } from "path";

const PYTHON_BIN =
  process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python";

function isBackendDir(dir: string): boolean {
  return existsSync(join(dir, "montage_backend", "main.py"));
}

/**
 * Resolve apps/backend from repo root, apps/desktop cwd, or compiled out/main location.
 */
export function resolveBackendDir(cwd: string, mainDir: string): string | null {
  const candidates = [
    join(cwd, "apps/backend"),
    join(cwd, "../backend"),
    join(mainDir, "../../../../apps/backend"),
    join(mainDir, "../../../backend"),
  ];

  for (const candidate of candidates) {
    if (isBackendDir(candidate)) {
      return candidate;
    }
  }
  return null;
}

export function resolvePythonPath(cwd: string, mainDir: string): string | null {
  const backendDir = resolveBackendDir(cwd, mainDir);
  if (!backendDir) {
    return null;
  }

  const venvPython = join(backendDir, PYTHON_BIN);
  return existsSync(venvPython) ? venvPython : null;
}
