import { readdirSync, statSync } from "fs";
import { join } from "path";
import { isVideoFilePath } from "../src/utils/video-extensions";

export { isVideoFilePath, VIDEO_EXTENSIONS } from "../src/utils/video-extensions";

export function collectVideoFiles(root: string): string[] {
  const results: string[] = [];

  function walk(dir: string): void {
    let entries: string[];
    try {
      entries = readdirSync(dir);
    } catch {
      return;
    }
    for (const entry of entries) {
      const fullPath = join(dir, entry);
      let stat;
      try {
        stat = statSync(fullPath);
      } catch {
        continue;
      }
      if (stat.isDirectory()) {
        walk(fullPath);
      } else if (isVideoFilePath(fullPath)) {
        results.push(fullPath);
      }
    }
  }

  walk(root);
  return results.sort();
}

export function resolveImportPaths(paths: string[]): string[] {
  const resolved: string[] = [];
  const seen = new Set<string>();

  for (const rawPath of paths) {
    if (!rawPath) {
      continue;
    }
    let stat;
    try {
      stat = statSync(rawPath);
    } catch {
      continue;
    }

    const candidates = stat.isDirectory() ? collectVideoFiles(rawPath) : [rawPath];
    for (const candidate of candidates) {
      if (!isVideoFilePath(candidate) || seen.has(candidate)) {
        continue;
      }
      seen.add(candidate);
      resolved.push(candidate);
    }
  }

  return resolved.sort();
}
