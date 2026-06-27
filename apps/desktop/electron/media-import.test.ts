import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { collectVideoFiles, isVideoFilePath, resolveImportPaths } from "./media-import";

describe("media-import", () => {
  it("detects supported video extensions", () => {
    expect(isVideoFilePath("/clips/gameplay.mp4")).toBe(true);
    expect(isVideoFilePath("/clips/readme.txt")).toBe(false);
  });

  it("collects videos recursively from folders", () => {
    const root = mkdtempSync(join(tmpdir(), "montage-import-"));
    const nested = join(root, "nested");
    mkdirSync(nested, { recursive: true });
    writeFileSync(join(root, "a.mp4"), "a");
    writeFileSync(join(nested, "b.mov"), "b");
    writeFileSync(join(root, "notes.txt"), "ignore");

    const files = collectVideoFiles(root);
    expect(files.map((path) => path.split("/").pop())).toEqual(["a.mp4", "b.mov"]);
  });

  it("resolves dropped folders and files into importable video paths", () => {
    const root = mkdtempSync(join(tmpdir(), "montage-drop-"));
    writeFileSync(join(root, "solo.webm"), "solo");

    const resolved = resolveImportPaths([root, join(root, "solo.webm")]);
    expect(resolved).toEqual([join(root, "solo.webm")]);
  });
});
