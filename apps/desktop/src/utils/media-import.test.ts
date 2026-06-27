import { describe, expect, it } from "vitest";
import { collectDropPaths } from "@/utils/media-import";

describe("collectDropPaths", () => {
  it("maps dropped files to absolute paths", () => {
    const file = { name: "clip.mp4" } as File;
    const paths = collectDropPaths([file], () => "/tmp/clip.mp4");
    expect(paths).toEqual(["/tmp/clip.mp4"]);
  });

  it("skips files without resolvable paths", () => {
    const file = { name: "clip.mp4" } as File;
    const paths = collectDropPaths([file], () => null);
    expect(paths).toEqual([]);
  });
});
