import { describe, expect, it } from "vitest";
import { montageFileUrlToPath, pathToMontageFileUrl } from "./media-file-url";
import { resolvePlaybackVideoUrl } from "./media-playback-url";
import { existsSync, mkdtempSync, writeFileSync } from "fs";
import { join } from "path";
import { tmpdir } from "os";

describe("media-file-url", () => {
  it("round-trips absolute macOS paths", () => {
    const path = "/Users/evanmaurer/video_editor/project/thumbnails/clip_strip.jpg";
    const url = pathToMontageFileUrl(path);
    expect(url).toBe(
      "montage-file:///Users/evanmaurer/video_editor/project/thumbnails/clip_strip.jpg",
    );
    expect(montageFileUrlToPath(url)).toBe(path);
  });

  it("encodes spaces and special characters in path segments", () => {
    const path = "/Users/evan/My Clips/foo bar.jpg";
    const url = pathToMontageFileUrl(path);
    expect(url).toContain("My%20Clips");
    expect(montageFileUrlToPath(url)).toBe(path);
  });

  it("handles host-style montage-file URLs", () => {
    expect(montageFileUrlToPath("montage-file://Users/evan/clips/video.mp4")).toBe(
      "/Users/evan/clips/video.mp4",
    );
  });
});

describe("resolvePlaybackVideoUrl", () => {
  it("prefers an existing proxy over the original file", () => {
    const dir = mkdtempSync(join(tmpdir(), "montage-playback-"));
    const original = join(dir, "original.mp4");
    const proxy = join(dir, "proxy.mp4");
    writeFileSync(original, "orig");
    writeFileSync(proxy, "proxy");

    const url = resolvePlaybackVideoUrl(original, proxy);
    expect(url).toBe(pathToMontageFileUrl(proxy));
  });

  it("falls back to the original when proxy is missing", () => {
    const dir = mkdtempSync(join(tmpdir(), "montage-playback-"));
    const original = join(dir, "original.mp4");
    const proxy = join(dir, "missing-proxy.mp4");
    writeFileSync(original, "orig");

    const url = resolvePlaybackVideoUrl(original, proxy);
    expect(url).toBe(pathToMontageFileUrl(original));
    expect(existsSync(original)).toBe(true);
  });
});
