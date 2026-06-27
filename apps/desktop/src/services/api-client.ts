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
  constructor(
    private baseUrl: string,
    private token: string,
  ) {}

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
  ): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        "X-Montage-Token": this.token,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    if (!response.ok) {
      const error = (await response.json().catch(() => ({}))) as {
        error?: string;
        message?: string;
      };
      throw new MontageApiError(
        error.error ?? "REQUEST_FAILED",
        error.message ?? `Request failed: ${response.status}`,
      );
    }

    if (response.status === 204) {
      return undefined as T;
    }
    return response.json() as Promise<T>;
  }

  async getHealth(): Promise<HealthResponse> {
    const response = await fetch(`${this.baseUrl}/health`);
    return response.json() as Promise<HealthResponse>;
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
  const connection = await window.montageAPI.getBackendConnection();
  if (!connection) {
    throw new Error("Backend not connected");
  }
  client = new MontageApiClient(connection.url, connection.token);
  return client;
}

export function getApiClient(): MontageApiClient {
  if (!client) {
    throw new Error("API client not initialized");
  }
  return client;
}
