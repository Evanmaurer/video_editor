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
  ffmpeg_available?: boolean;
  ffmpeg_note?: string | null;
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

export type MediaType = "video" | "audio" | "image";
export type MediaRole = "clip" | "music" | "reference" | "voice" | "other";
export type ImportStatus =
  | "pending"
  | "processing"
  | "ready"
  | "error"
  | "cancelled"
  | "duplicate";
export type StorageMode = "copy" | "reference";
export type ProcessingStatus = "pending" | "processing" | "ready" | "error";
export type MediaSortField = "name" | "duration" | "created_at" | "favorite";
export type MediaSortOrder = "asc" | "desc";

export interface MediaItem {
  id: string;
  project_id: string;
  file_path: string;
  file_name: string;
  source_path: string | null;
  media_type: MediaType;
  role: MediaRole;
  storage_mode: StorageMode;
  sha256_hash: string | null;
  duration_ms: number | null;
  width: number | null;
  height: number | null;
  frame_rate: number | null;
  codec: string | null;
  frame_count: number | null;
  audio_sample_rate: number | null;
  bitrate: number | null;
  file_size_bytes: number | null;
  proxy_path: string | null;
  thumbnail_path: string | null;
  waveform_path: string | null;
  proxy_status: ProcessingStatus;
  waveform_status: ProcessingStatus;
  scene_status: ProcessingStatus;
  metadata_status: ProcessingStatus;
  tags: string[];
  is_favorite: boolean;
  import_status: ImportStatus;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface ImportMediaRequest {
  paths: string[];
  role?: MediaRole;
  storage_mode?: StorageMode;
}

export interface ImportFolderRequest {
  path: string;
  role?: MediaRole;
  storage_mode?: StorageMode;
}

export interface ImportMediaResult {
  media_id: string;
  file_name: string;
  status: ImportStatus;
  error?: string | null;
  sha256_hash?: string | null;
}

export interface ImportMediaResponse {
  imported: ImportMediaResult[];
  skipped: string[];
  duplicates: ImportMediaResult[];
}

export interface MediaListParams {
  search?: string;
  sort_by?: MediaSortField;
  sort_order?: MediaSortOrder;
  tags?: string[];
  favorites_only?: boolean;
}

export interface UpdateMediaRequest {
  tags?: string[];
  is_favorite?: boolean;
}

export type WSEvent =
  | { type: "job.progress"; job_id: string; progress: number; message: string }
  | { type: "job.complete"; job_id: string }
  | { type: "job.failed"; job_id: string; error: string }
  | {
      type: "render.progress";
      job_id: string;
      project_id: string;
      status: RenderJobStatus;
      progress: number;
      eta_seconds: number | null;
      elapsed_seconds: number;
      output_path: string | null;
      error_message: string | null;
      message?: string | null;
    }
  | { type: "backend.status"; status: string };

export type RenderJobStatus =
  | "queued"
  | "running"
  | "paused"
  | "completed"
  | "failed"
  | "cancelled";

export type RenderCodec = "h264";

export interface RenderPresetInfo {
  id: string;
  label: string;
  codec: RenderCodec;
  width: number;
  height: number;
  frame_rate: number;
  hardware_available: boolean;
}

export interface RenderJobSummary {
  id: string;
  project_id: string;
  timeline_id: string;
  preset_id: string;
  status: RenderJobStatus;
  progress: number;
  output_path: string | null;
  error_message: string | null;
  eta_seconds: number | null;
  elapsed_seconds: number;
  created_at: string;
  updated_at: string;
}

export interface RenderJobDetail extends RenderJobSummary {
  ffmpeg_command: string | null;
  hardware_encoding: boolean;
  log_tail: string[];
}

export interface RenderLogResponse {
  job_id: string;
  lines: string[];
  total_lines: number;
}

export interface StartRenderRequest {
  timeline_id?: string | null;
  preset_id?: string;
  output_name?: string | null;
  use_hardware_encoding?: boolean;
}

// --- Timeline (M2-003) ---

export type TrackType = "video" | "audio" | "overlay" | "subtitle";

export interface TimelineSettings {
  width: number;
  height: number;
  frame_rate: number;
  sample_rate: number;
}

export interface TimelineClip {
  id: string;
  media_item_id: string;
  track_id: string;
  start_ms: number;
  end_ms: number;
  source_in_ms: number;
  source_out_ms: number;
  speed: number;
  opacity: number;
  name?: string;
}

export interface TimelineTrack {
  id: string;
  type: TrackType;
  name: string;
  index: number;
  muted: boolean;
  locked: boolean;
  visible: boolean;
  volume: number;
  clips: TimelineClip[];
}

export interface TimelineMarker {
  id: string;
  time_ms: number;
  label: string;
  color: string;
  type: "user" | "beat" | "drop" | "event";
}

export interface TimelineDocument {
  id: string;
  project_id: string;
  name: string;
  version: number;
  settings: TimelineSettings;
  duration_ms: number;
  tracks: TimelineTrack[];
  markers: TimelineMarker[];
  beat_markers: TimelineMarker[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface TimelineSummary {
  id: string;
  project_id: string;
  name: string;
  duration_ms: number;
  is_active: boolean;
  version: number;
  updated_at: string;
}

export interface SaveTimelineResponse {
  id: string;
  version: number;
  updated_at: string;
}

export interface CreateTimelineRequest {
  name?: string;
}

// --- AI Metadata (M2-006) ---

export type MetadataFeatureKey = "visual" | "audio" | "ai_cache";

export interface SceneMarker {
  timestamp_ms: number;
  score: number;
}

export interface VisualMetadata {
  scenes: SceneMarker[];
  motion_score: number;
  camera_movement: {
    label: string;
    pan: number;
    zoom: number;
    shake: number;
  };
  brightness: {
    mean: number;
    min: number;
    max: number;
    std: number;
  };
  color_histogram: {
    bins: number;
    r: number[];
    g: number[];
    b: number[];
  };
  blur_score: number;
  sharpness: number;
  keyframes: Array<{ timestamp_ms: number }>;
}

export interface AudioMetadata {
  loudness_lufs: number | null;
  mean_volume_db: number | null;
  max_volume_db: number | null;
  peaks: number[];
  silence_regions: Array<{ start_ms: number; end_ms: number }>;
  beat_markers: Array<{ timestamp_ms: number; strength: number }>;
  speech: {
    has_speech: boolean;
    speech_ratio: number;
    confidence: number;
  };
}

export interface AICacheMetadata {
  ocr_text: unknown[] | null;
  embedding_vectors: number[] | null;
  object_detections: unknown[] | null;
  face_detections: unknown[] | null;
  optical_flow: Record<string, unknown> | null;
  clip_embeddings: number[] | null;
  schema_version: number;
}

export interface MetadataFeatureRecord {
  media_id: string;
  feature_key: MetadataFeatureKey;
  status: ProcessingStatus;
  payload: Record<string, unknown>;
  confidence: number | null;
  reasoning: string | null;
  source_fingerprint: string | null;
  schema_version: number;
  created_at: string;
  updated_at: string;
}

export interface MediaMetadataSummary {
  media_id: string;
  status: ProcessingStatus;
  source_fingerprint: string | null;
  visual: VisualMetadata | null;
  audio: AudioMetadata | null;
  ai_cache: AICacheMetadata | null;
  features: MetadataFeatureRecord[];
}

export interface UpsertMetadataFeatureRequest {
  payload: Record<string, unknown>;
  confidence?: number | null;
  reasoning?: string | null;
  status?: ProcessingStatus;
}
