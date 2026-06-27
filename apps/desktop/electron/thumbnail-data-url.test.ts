import { describe, expect, it, vi } from "vitest";
import { readImageDataUrl } from "./thumbnail-data-url";

describe("readImageDataUrl", () => {
  it("returns null for missing files", async () => {
    await expect(readImageDataUrl("/tmp/montage-missing-thumbnail.jpg")).resolves.toBeNull();
  });

  it("returns null for empty paths", async () => {
    await expect(readImageDataUrl("")).resolves.toBeNull();
    await expect(readImageDataUrl("   ")).resolves.toBeNull();
  });
});
