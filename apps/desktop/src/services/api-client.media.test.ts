import { beforeEach, describe, expect, it, vi } from "vitest";
import { MontageApiClient } from "@/services/api-client";

const backendRequest = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  global.window = {
    montageAPI: {
      backendRequest,
    },
  } as unknown as Window & typeof globalThis;
});

describe("MontageApiClient media endpoints", () => {
  const client = new MontageApiClient("http://127.0.0.1:8000");

  it("lists media items", async () => {
    backendRequest.mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      body: JSON.stringify({ items: [{ id: "media-1", file_name: "clip.mp4" }] }),
      url: "http://127.0.0.1:8000/api/v1/projects/p1/media",
    });

    const items = await client.listMedia("p1");
    expect(backendRequest).toHaveBeenCalledWith({
      method: "GET",
      path: "/api/v1/projects/p1/media",
    });
    expect(items).toHaveLength(1);
  });

  it("imports files", async () => {
    backendRequest.mockResolvedValue({
      ok: true,
      status: 202,
      statusText: "Accepted",
      body: JSON.stringify({ imported: [], skipped: [], duplicates: [] }),
      url: "http://127.0.0.1:8000/api/v1/projects/p1/media/import",
    });

    await client.importMedia("p1", { paths: ["/tmp/clip.mp4"] });
    expect(backendRequest).toHaveBeenCalledWith({
      method: "POST",
      path: "/api/v1/projects/p1/media/import",
      body: { paths: ["/tmp/clip.mp4"] },
    });
  });

  it("imports folders", async () => {
    backendRequest.mockResolvedValue({
      ok: true,
      status: 202,
      statusText: "Accepted",
      body: JSON.stringify({ imported: [], skipped: [], duplicates: [] }),
      url: "http://127.0.0.1:8000/api/v1/projects/p1/media/import-folder",
    });

    await client.importFolder("p1", { path: "/tmp/Footage" });
    expect(backendRequest).toHaveBeenCalledWith({
      method: "POST",
      path: "/api/v1/projects/p1/media/import-folder",
      body: { path: "/tmp/Footage" },
    });
  });
});
