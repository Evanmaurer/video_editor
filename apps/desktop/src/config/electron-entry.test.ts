import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../../../..");
const workspacePath = join(repoRoot, "pnpm-workspace.yaml");

/** electron-vite v2 default output directories (see node_modules/electron-vite). */
const ELECTRON_VITE_MAIN_ENTRY = "out/main/index.js";

describe("electron-vite entry configuration", () => {
  it('package.json "main" matches electron-vite v2 default output path', () => {
    const pkg = JSON.parse(
      readFileSync(join(repoRoot, "apps/desktop/package.json"), "utf8"),
    ) as { main?: string };

    expect(pkg.main).toBe(ELECTRON_VITE_MAIN_ENTRY);
  });
});

describe("pnpm allowBuilds configuration", () => {
  it("allows electron and esbuild postinstall scripts (pnpm v10+ requirement)", () => {
    const workspace = readFileSync(workspacePath, "utf8");

    expect(workspace).toMatch(/allowBuilds:/);
    expect(workspace).toMatch(/^\s*electron:\s*true\s*$/m);
    expect(workspace).toMatch(/^\s*esbuild:\s*true\s*$/m);
    expect(workspace).not.toMatch(/set this to true or false/);
    expect(workspace).not.toMatch(/^\s*['"]?\d+['"]?\s*:/m);
  });
});

describe("Node.js engine constraint", () => {
  it("requires Node 22 LTS (Node 24.16+ / 26.x break electron postinstall)", () => {
    const rootPkg = JSON.parse(
      readFileSync(join(repoRoot, "package.json"), "utf8"),
    ) as { engines?: { node?: string } };

    expect(rootPkg.engines?.node).toMatch(/\^22/);
  });
});
