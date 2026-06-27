/** Shared types for MontageAI frontend and backend contract. */

export interface ProjectSettings {
  auto_analyze_on_import: boolean;
  auto_generate_timeline: boolean;
  auto_save_interval_ms: number;
}

export const DEFAULT_PROJECT_SETTINGS: ProjectSettings = {
  auto_analyze_on_import: true,
  auto_generate_timeline: false,
  auto_save_interval_ms: 60000,
};

export interface Project {
  id: string;
  name: string;
  root_path: string;
  width: number;
  height: number;
  frame_rate: number;
  target_game: string;
  settings: ProjectSettings;
  created_at: string;
  updated_at: string;
}

export interface ProjectSummary {
  id: string;
  name: string;
  path: string;
  updated_at: string;
}

export interface CreateProjectRequest {
  name: string;
  root_path: string;
  width?: number;
  height?: number;
  frame_rate?: number;
  target_game?: string;
  settings?: Partial<ProjectSettings>;
}

export interface OpenProjectRequest {
  path: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  models_loaded: boolean;
  queue_depth: number;
  gpu_available: boolean;
  gpu_name: string | null;
  cpu_only_mode: boolean;
  performance_note: string | null;
}

export interface BackendReadyEvent {
  port: number;
  token: string;
}

export type LlmProviderType = "ollama" | "openai" | "none";

export interface LlmProviderConfig {
  provider: LlmProviderType;
  model: string;
  api_key?: string;
  base_url?: string;
}

export const DEFAULT_LLM_CONFIG: LlmProviderConfig = {
  provider: "ollama",
  model: "qwen3:8b-instruct",
  base_url: "http://127.0.0.1:11434",
};

export const FALLBACK_LLM_CONFIG: LlmProviderConfig = {
  provider: "ollama",
  model: "llama3.2:3b",
  base_url: "http://127.0.0.1:11434",
};

export interface AppSettings {
  default_project_path: string;
  llm: LlmProviderConfig;
  gpu_enabled: boolean;
  worker_count: number;
}

export interface GpuInfo {
  available: boolean;
  name: string | null;
  estimated_speedup: string;
  cpu_only_warning: string | null;
}

export interface AiFeatureStatus {
  chat_enabled: boolean;
  chat_disabled_reason: string | null;
  ocr_available: boolean;
  albion_detection_available: boolean;
  music_analysis_available: boolean;
}

export type ViewState = "welcome" | "editor" | "settings";

export type WSEvent =
  | { type: "job.progress"; job_id: string; progress: number; message: string }
  | { type: "job.complete"; job_id: string }
  | { type: "job.failed"; job_id: string; error: string }
  | { type: "backend.status"; status: string };
