import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ImportMediaResponse, MediaItem } from "@montage/shared-types";

const mockApi = {
  listMedia: vi.fn(),
  importMedia: vi.fn(),
  importFolder: vi.fn(),
  updateMedia: vi.fn(),
  deleteMedia: vi.fn(),
};

vi.mock("@/services/api-client", () => ({
  getApiClient: () => mockApi,
}));

import { useMediaStore } from "@/stores/media-store";

const sampleItem = (overrides: Partial<MediaItem> = {}): MediaItem => ({
  id: "media-1",
  project_id: "project-1",
  file_path: "/tmp/clip.mp4",
  file_name: "clip.mp4",
  source_path: null,
  media_type: "video",
  role: "clip",
  storage_mode: "copy",
  sha256_hash: "abc",
  duration_ms: 1000,
  width: 1920,
  height: 1080,
  frame_rate: 60,
  codec: "h264",
  frame_count: 60,
  audio_sample_rate: 48000,
  bitrate: 1_000_000,
  file_size_bytes: 100,
  proxy_path: null,
  thumbnail_path: null,
  waveform_path: null,
  proxy_status: "processing",
  waveform_status: "processing",
  scene_status: "processing",
  metadata_status: "pending",
  tags: [],
  is_favorite: false,
  import_status: "processing",
  error_message: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  ...overrides,
});

describe("useMediaStore", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useMediaStore.setState({
      items: [],
      isLoading: false,
      isImporting: false,
      error: null,
      pollTimer: null,
    });
  });

  it("loads media for a project", async () => {
    mockApi.listMedia.mockResolvedValue([sampleItem()]);
    await useMediaStore.getState().loadMedia("project-1");
    expect(mockApi.listMedia).toHaveBeenCalledWith("project-1", expect.any(Object));
    expect(useMediaStore.getState().items).toHaveLength(1);
  });

  it("imports files and refreshes the library", async () => {
    const response: ImportMediaResponse = {
      imported: [{ media_id: "media-1", file_name: "clip.mp4", status: "processing" }],
      skipped: [],
      duplicates: [],
    };
    mockApi.importMedia.mockResolvedValue(response);
    mockApi.listMedia.mockResolvedValue([sampleItem()]);

    await useMediaStore.getState().importPaths("project-1", ["/tmp/clip.mp4"]);

    expect(mockApi.importMedia).toHaveBeenCalledWith("project-1", {
      paths: ["/tmp/clip.mp4"],
      role: "clip",
      storage_mode: "copy",
    });
    expect(mockApi.listMedia).toHaveBeenCalled();
    expect(useMediaStore.getState().items).toHaveLength(1);
  });

  it("imports folders through the folder endpoint", async () => {
    const response: ImportMediaResponse = {
      imported: [{ media_id: "media-2", file_name: "nested.mp4", status: "processing" }],
      skipped: [],
      duplicates: [],
    };
    mockApi.importFolder.mockResolvedValue(response);
    mockApi.listMedia.mockResolvedValue([sampleItem({ id: "media-2", file_name: "nested.mp4" })]);

    await useMediaStore.getState().importFolder("project-1", "/tmp/Footage");

    expect(mockApi.importFolder).toHaveBeenCalledWith("project-1", {
      path: "/tmp/Footage",
      role: "clip",
      storage_mode: "copy",
    });
    expect(useMediaStore.getState().items[0]?.file_name).toBe("nested.mp4");
  });
});
