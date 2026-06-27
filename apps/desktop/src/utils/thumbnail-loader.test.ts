import { describe, expect, it, vi, afterEach } from "vitest";
import { loadThumbnailSrc } from "./thumbnail-loader";

describe("loadThumbnailSrc", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("prefers IPC data URLs when available", async () => {
    vi.stubGlobal("window", {
      montageAPI: {
        getThumbnailDataUrl: vi.fn().mockResolvedValue("data:image/jpeg;base64,abc"),
        getBackendConnection: vi.fn(),
      },
    });

    await expect(
      loadThumbnailSrc("/project/thumbnails/poster.jpg", "project-1", "media-1"),
    ).resolves.toBe("data:image/jpeg;base64,abc");
  });

  it("falls back to backend blob URLs when IPC returns null", async () => {
    const blob = new Blob(["jpeg"], { type: "image/jpeg" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      blob: vi.fn().mockResolvedValue(blob),
    }));
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn().mockReturnValue("blob:thumbnail"),
      revokeObjectURL: vi.fn(),
    });
    vi.stubGlobal("window", {
      montageAPI: {
        getThumbnailDataUrl: vi.fn().mockResolvedValue(null),
        getBackendConnection: vi.fn().mockResolvedValue({
          url: "http://127.0.0.1:8000",
          token: "montage-dev-token",
        }),
      },
    });

    await expect(
      loadThumbnailSrc("/project/thumbnails/poster.jpg", "project-1", "media-1"),
    ).resolves.toBe("blob:thumbnail");
  });
});
