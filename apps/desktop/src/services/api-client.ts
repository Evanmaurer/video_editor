import type {
  AppSettings,
  CreateProjectRequest,
  CreateTimelineRequest,
  HealthResponse,
  ImportFolderRequest,
  ImportMediaRequest,
  ImportMediaResponse,
  MediaItem,
  MediaListParams,
  OpenProjectRequest,
  Project,
  ProjectSummary,
  RenderJobDetail,
  RenderJobSummary,
  RenderLogResponse,
  RenderPresetInfo,
  AlbionTimelineAnnotationResult,
  MetadataFeatureKey,
  MetadataFeatureRecord,
  MediaMetadataSummary,
  UpsertMetadataFeatureRequest,
  SaveTimelineResponse,
  StartRenderRequest,
  TimelineDocument,
  TimelineSummary,
  UpdateMediaRequest,
} from "@montage/shared-types";

export class MontageApiError extends Error {
  constructor(
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "MontageApiError";
  }
}

export class MontageApiClient {
  constructor(private baseUrl: string) {}

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
  ): Promise<T> {
    const response = await window.montageAPI.backendRequest({ method, path, body });

    if (!response.ok) {
      let parsed: { error?: string; message?: string } = {};
      try {
        parsed = JSON.parse(response.body) as { error?: string; message?: string };
      } catch {
        // non-json error body
      }
      throw new MontageApiError(
        parsed.error ?? "REQUEST_FAILED",
        parsed.message ??
          `HTTP ${response.status} ${response.statusText}\nURL: ${response.url}\nBody: ${response.body}`,
      );
    }

    if (response.status === 204 || response.body.length === 0) {
      return undefined as T;
    }
    return JSON.parse(response.body) as T;
  }

  async getHealth(): Promise<HealthResponse> {
    const response = await window.montageAPI.backendRequest({
      method: "GET",
      path: "/health",
    });

    if (!response.ok) {
      throw new MontageApiError(
        "HEALTH_CHECK_FAILED",
        `HTTP ${response.status} ${response.statusText}\nURL: ${response.url}\nBody: ${response.body}`,
      );
    }

    return JSON.parse(response.body) as HealthResponse;
  }

  async createProject(data: CreateProjectRequest): Promise<Project> {
    return this.request("POST", "/api/v1/projects", data);
  }

  async openProject(data: OpenProjectRequest): Promise<Project> {
    return this.request("POST", "/api/v1/projects/open", data);
  }

  async getRecentProjects(): Promise<ProjectSummary[]> {
    const result = await this.request<{ items: ProjectSummary[] }>(
      "GET",
      "/api/v1/projects/recent",
    );
    return result.items;
  }

  async saveProject(project: Project): Promise<Project> {
    return this.request("PUT", `/api/v1/projects/${project.id}`, project);
  }

  async closeProject(projectId: string): Promise<void> {
    await this.request("POST", `/api/v1/projects/${projectId}/close`);
  }

  async getSettings(): Promise<AppSettings> {
    return this.request("GET", "/api/v1/settings");
  }

  async updateSettings(settings: AppSettings): Promise<AppSettings> {
    return this.request("PUT", "/api/v1/settings", settings);
  }

  async importMedia(
    projectId: string,
    data: ImportMediaRequest,
    wait = false,
  ): Promise<ImportMediaResponse> {
    const query = wait ? "?wait=true" : "";
    return this.request("POST", `/api/v1/projects/${projectId}/media/import${query}`, data);
  }

  async importFolder(
    projectId: string,
    data: ImportFolderRequest,
    wait = false,
  ): Promise<ImportMediaResponse> {
    const query = wait ? "?wait=true" : "";
    return this.request(
      "POST",
      `/api/v1/projects/${projectId}/media/import-folder${query}`,
      data,
    );
  }

  async listMedia(projectId: string, params: MediaListParams = {}): Promise<MediaItem[]> {
    const searchParams = new URLSearchParams();
    if (params.search) {
      searchParams.set("search", params.search);
    }
    if (params.sort_by) {
      searchParams.set("sort_by", params.sort_by);
    }
    if (params.sort_order) {
      searchParams.set("sort_order", params.sort_order);
    }
    if (params.favorites_only) {
      searchParams.set("favorites_only", "true");
    }
    for (const tag of params.tags ?? []) {
      searchParams.append("tags", tag);
    }
    const qs = searchParams.toString();
    const result = await this.request<{ items: MediaItem[] }>(
      "GET",
      `/api/v1/projects/${projectId}/media${qs ? `?${qs}` : ""}`,
    );
    return result.items;
  }

  async getMediaItem(projectId: string, mediaId: string): Promise<MediaItem> {
    return this.request("GET", `/api/v1/projects/${projectId}/media/${mediaId}`);
  }

  async updateMedia(
    projectId: string,
    mediaId: string,
    data: UpdateMediaRequest,
  ): Promise<MediaItem> {
    return this.request("PATCH", `/api/v1/projects/${projectId}/media/${mediaId}`, data);
  }

  async deleteMedia(projectId: string, mediaId: string): Promise<void> {
    await this.request("DELETE", `/api/v1/projects/${projectId}/media/${mediaId}`);
  }

  async listTimelines(projectId: string): Promise<TimelineSummary[]> {
    const result = await this.request<{ items: TimelineSummary[] }>(
      "GET",
      `/api/v1/projects/${projectId}/timelines`,
    );
    return result.items;
  }

  async getActiveTimeline(projectId: string): Promise<TimelineDocument> {
    return this.request("GET", `/api/v1/projects/${projectId}/timelines/active`);
  }

  async createTimeline(
    projectId: string,
    data: CreateTimelineRequest = {},
  ): Promise<TimelineDocument> {
    return this.request("POST", `/api/v1/projects/${projectId}/timelines`, data);
  }

  async getTimeline(projectId: string, timelineId: string): Promise<TimelineDocument> {
    return this.request("GET", `/api/v1/projects/${projectId}/timelines/${timelineId}`);
  }

  async saveTimeline(
    projectId: string,
    timelineId: string,
    document: TimelineDocument,
  ): Promise<SaveTimelineResponse> {
    return this.request(
      "PUT",
      `/api/v1/projects/${projectId}/timelines/${timelineId}`,
      document,
    );
  }

  async decodePlaybackFrame(
    projectId: string,
    data: {
      media_id: string;
      source_ms: number;
      frame_rate: number;
      quality: "proxy" | "full";
    },
  ): Promise<{
    image_base64: string;
    decode_time_ms: number;
    cache_hit: boolean;
    gpu_accelerated: boolean;
  }> {
    return this.request("POST", `/api/v1/projects/${projectId}/playback/decode`, data);
  }

  async prefetchPlaybackFrames(
    projectId: string,
    data: {
      frame_rate: number;
      requests: Array<{
        media_id: string;
        source_ms: number;
        quality: "proxy" | "full";
      }>;
    },
  ): Promise<void> {
    await this.request("POST", `/api/v1/projects/${projectId}/playback/prefetch`, data);
  }

  async reportPlaybackMetrics(
    projectId: string,
    data: { playback_fps: number; dropped_frames: number },
  ): Promise<{
    playback_fps: number;
    dropped_frames: number;
    decode_time_ms: number;
    memory_usage_mb: number;
    gpu_accelerated: boolean;
    cache_hit_rate: number;
  }> {
    return this.request("POST", `/api/v1/projects/${projectId}/playback/metrics`, data);
  }

  async getPlaybackMetrics(projectId: string): Promise<{
    playback_fps: number;
    dropped_frames: number;
    decode_time_ms: number;
    memory_usage_mb: number;
    gpu_accelerated: boolean;
    cache_hit_rate: number;
  }> {
    return this.request("GET", `/api/v1/projects/${projectId}/playback/metrics`);
  }

  async listRenderPresets(projectId: string): Promise<RenderPresetInfo[]> {
    return this.request("GET", `/api/v1/projects/${projectId}/render/presets`);
  }

  async startRender(
    projectId: string,
    data: StartRenderRequest,
  ): Promise<RenderJobSummary> {
    return this.request("POST", `/api/v1/projects/${projectId}/render`, data);
  }

  async listRenderJobs(projectId: string): Promise<RenderJobSummary[]> {
    return this.request("GET", `/api/v1/projects/${projectId}/render/jobs`);
  }

  async getRenderJob(projectId: string, jobId: string): Promise<RenderJobDetail> {
    return this.request("GET", `/api/v1/projects/${projectId}/render/jobs/${jobId}`);
  }

  async getRenderLogs(projectId: string, jobId: string): Promise<RenderLogResponse> {
    return this.request("GET", `/api/v1/projects/${projectId}/render/jobs/${jobId}/logs`);
  }

  async pauseRenderJob(projectId: string, jobId: string): Promise<RenderJobSummary> {
    return this.request("POST", `/api/v1/projects/${projectId}/render/jobs/${jobId}/pause`);
  }

  async resumeRenderJob(projectId: string, jobId: string): Promise<RenderJobSummary> {
    return this.request("POST", `/api/v1/projects/${projectId}/render/jobs/${jobId}/resume`);
  }

  async cancelRenderJob(projectId: string, jobId: string): Promise<RenderJobSummary> {
    return this.request("POST", `/api/v1/projects/${projectId}/render/jobs/${jobId}/cancel`);
  }

  async getMediaMetadata(projectId: string, mediaId: string): Promise<MediaMetadataSummary> {
    return this.request("GET", `/api/v1/projects/${projectId}/media/${mediaId}/metadata`);
  }

  async analyzeMediaMetadata(projectId: string, mediaId: string): Promise<MediaMetadataSummary> {
    return this.request("POST", `/api/v1/projects/${projectId}/media/${mediaId}/metadata/analyze`);
  }

  async upsertMediaMetadataFeature(
    projectId: string,
    mediaId: string,
    featureKey: MetadataFeatureKey,
    data: UpsertMetadataFeatureRequest,
  ): Promise<MetadataFeatureRecord> {
    return this.request(
      "PUT",
      `/api/v1/projects/${projectId}/media/${mediaId}/metadata/${featureKey}`,
      data,
    );
  }

  async getAlbionTimelineAnnotations(
    projectId: string,
    mediaId: string,
  ): Promise<AlbionTimelineAnnotationResult | null> {
    return this.request(
      "GET",
      `/api/v1/projects/${projectId}/media/${mediaId}/analysis/albion/annotations`,
    );
  }
}

let client: MontageApiClient | null = null;

export async function initApiClient(): Promise<MontageApiClient> {
  const status = await window.montageAPI.getBackendStatus();
  const connection = await window.montageAPI.getBackendConnection();
  if (!connection) {
    throw new Error(status.errorDetail ?? status.error ?? "Backend not connected");
  }

  client = new MontageApiClient(connection.url);
  return client;
}

export function getApiClient(): MontageApiClient {
  if (!client) {
    throw new Error("API client not initialized");
  }
  return client;
}
