import { describe, expect, it } from "vitest";
import { montageFileUrlToPath, pathToMontageFileUrl } from "./media-file-url";

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
});
