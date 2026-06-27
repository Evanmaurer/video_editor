import { describe, expect, it } from "vitest";
import { isVideoFilePath } from "@/utils/video-extensions";

describe("video-extensions", () => {
  it("detects supported video extensions", () => {
    expect(isVideoFilePath("/clips/gameplay.mp4")).toBe(true);
    expect(isVideoFilePath("/clips/readme.txt")).toBe(false);
  });
});
