#!/usr/bin/env node
/**
 * Validates Electron-Vite output paths and pnpm allowBuilds for electron/esbuild.
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "..");
const desktopRoot = join(repoRoot, "apps", "desktop");
const pkgPath = join(desktopRoot, "package.json");
const workspacePath = join(repoRoot, "pnpm-workspace.yaml");

const EXPECTED_MAIN = "out/main/index.js";
const EXPECTED_PRELOAD = "out/preload/index.js";
const REQUIRED_ALLOW_BUILDS = ["electron", "esbuild"];

function fail(message) {
  console.error(`[validate-electron-config] ${message}`);
  process.exit(1);
}

/** Node 24.16+ and 26.x stall extract-zip during electron postinstall (path.txt never written). */
function validateNodeVersion() {
  const [major, minor] = process.versions.node.split(".").map(Number);
  if (major === 26 || (major === 24 && minor >= 16)) {
    fail(
      `Node.js ${process.versions.node} breaks Electron postinstall (extract-zip stalls on Node 24.16+ / 26.x). ` +
        "Use Node.js 22 LTS — see .node-version. " +
        "https://github.com/electron/electron/issues/51619",
    );
  }
}

function validateAllowBuilds() {
  if (!existsSync(workspacePath)) {
    fail(`Missing ${workspacePath}`);
  }

  const raw = readFileSync(workspacePath, "utf8");

  if (!raw.includes("allowBuilds:")) {
    fail(
      "pnpm-workspace.yaml must define allowBuilds. pnpm v10+ blocks postinstall scripts by default; " +
        "Electron requires allowBuilds.electron: true.",
    );
  }

  if (/\n\s+['"]?\d+['"]?\s*:/.test(raw)) {
    fail(
      "pnpm-workspace.yaml allowBuilds appears corrupted (numeric keys detected). " +
        "Use: allowBuilds:\\n  electron: true\\n  esbuild: true",
    );
  }

  for (const pkg of REQUIRED_ALLOW_BUILDS) {
    const match = raw.match(new RegExp(`^\\s*${pkg}\\s*:\\s*(.+)$`, "m"));
    if (!match) {
      fail(`pnpm-workspace.yaml missing allowBuilds.${pkg}. Add "${pkg}: true" under allowBuilds.`);
    }
    const value = match[1].trim();
    if (value !== "true") {
      fail(
        `pnpm-workspace.yaml allowBuilds.${pkg} must be boolean true (found: ${value}). ` +
          "pnpm skips postinstall when this is a placeholder string.",
      );
    }
  }
}

if (!existsSync(pkgPath)) {
  fail(`Missing ${pkgPath}`);
}

const pkg = JSON.parse(readFileSync(pkgPath, "utf8"));

if (pkg.main !== EXPECTED_MAIN) {
  fail(
    `package.json "main" must be "${EXPECTED_MAIN}" (electron-vite v2 default). ` +
      `Found: "${pkg.main ?? "(unset)"}"`,
  );
}

validateAllowBuilds();

validateNodeVersion();

const mainEntry = join(desktopRoot, pkg.main);
const preloadEntry = join(desktopRoot, EXPECTED_PRELOAD);

const checkBuilt = process.argv.includes("--require-build");

if (checkBuilt) {
  if (!existsSync(mainEntry)) {
    fail(`Main entry not found after build: ${mainEntry}`);
  }
  if (!existsSync(preloadEntry)) {
    fail(`Preload entry not found after build: ${preloadEntry}`);
  }
  console.log("[validate-electron-config] Build outputs verified.");
} else {
  console.log("[validate-electron-config] package.json entry paths and allowBuilds OK.");
}

const checkElectron = process.argv.includes("--require-electron");

if (checkElectron) {
  const electronPkg = join(
    repoRoot,
    "node_modules/.pnpm/electron@33.4.11/node_modules/electron",
  );
  // Resolve via symlink from desktop package
  const electronDir = existsSync(join(desktopRoot, "node_modules/electron"))
    ? join(desktopRoot, "node_modules/electron")
    : electronPkg;
  const pathTxt = join(electronDir, "path.txt");
  if (!existsSync(pathTxt)) {
    fail(
      `Electron postinstall did not run (missing path.txt). ` +
        "Ensure pnpm-workspace.yaml has allowBuilds.electron: true, then run: pnpm install",
    );
  }
  console.log("[validate-electron-config] Electron binary install verified.");
}
