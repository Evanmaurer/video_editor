import type {
  AppSettings,
  CreateProjectRequest,
  HealthResponse,
  OpenProjectRequest,
  Project,
  ProjectSummary,
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
