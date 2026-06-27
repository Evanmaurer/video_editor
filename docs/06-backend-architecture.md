# Backend Architecture

**Product:** MontageAI  
**Stack:** Python 3.11+ / FastAPI / SQLite / FFmpeg  
**Version:** 1.0  
**Date:** 2026-06-26

---

## 1. Overview

The Python backend is a local FastAPI server spawned by Electron on startup. It handles all persistence, media processing, AI agent orchestration, and rendering. It binds exclusively to `127.0.0.1` on a dynamic port with token-based authentication.

## 2. Technology Choices

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Web framework | FastAPI | Async, OpenAPI, Pydantic integration |
| ASGI server | Uvicorn | Production-ready; WebSocket support |
| ORM | SQLAlchemy 2.0 | Mature; migration support |
| Migrations | Alembic | Version-controlled schema |
| Validation | Pydantic v2 | Shared models with JSON Schema |
| Job queue | asyncio + custom queue | No external deps; sufficient for desktop |
| Media | FFmpeg CLI + PyAV | FFmpeg for render; PyAV for frame extraction |
| CV | OpenCV | Frame processing, motion detection |
| ML | PyTorch + ONNX Runtime | Training flexibility + inference speed |
| Speech | Whisper (local) | Voice detection/transcription |
| OCR | EasyOCR or Tesseract | Kill feed, UI text |
| Logging | structlog | Structured JSON logs |

## 3. Layer Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      API Layer                           │
│  FastAPI routes, WebSocket handlers, middleware          │
├─────────────────────────────────────────────────────────┤
│                    Service Layer                         │
│  Business logic, orchestration, validation               │
├─────────────────────────────────────────────────────────┤
│                   Repository Layer                       │
│  Database access, query abstraction                      │
├─────────────────────────────────────────────────────────┤
│                    Domain Layer                          │
│  Pydantic models, domain exceptions                      │
├─────────────────────────────────────────────────────────┤
│              Infrastructure Layer                        │
│  FFmpeg, AI Engine, Job Queue, File System              │
└─────────────────────────────────────────────────────────┘
```

## 4. Application Entry

```python
# montage_backend/main.py
app = FastAPI(title="MontageAI Backend", version="1.0.0")

@app.on_event("startup")
async def startup():
    configure_logging()
    await job_queue.start(workers=settings.worker_count)
    await model_registry.load_models()

@app.on_event("shutdown")
async def shutdown():
    await job_queue.shutdown(timeout=30)
    await model_registry.unload_models()
```

## 5. Service Modules

### 5.1 ProjectService

```python
class ProjectService:
    async def create_project(self, request: CreateProjectRequest) -> Project: ...
    async def open_project(self, path: Path) -> Project: ...
    async def close_project(self, project_id: str) -> None: ...
    async def get_recent_projects(self) -> list[ProjectSummary]: ...
    async def update_settings(self, project_id: str, settings: ProjectSettings) -> Project: ...
```

**Responsibilities:** Project lifecycle, folder scaffolding, settings persistence.

### 5.2 MediaService

```python
class MediaService:
    async def import_files(self, project_id: str, paths: list[Path], role: MediaRole) -> ImportResult: ...
    async def get_media_items(self, project_id: str, filters: MediaFilters) -> list[MediaItem]: ...
    async def generate_proxy(self, media_item_id: str) -> Path: ...
    async def generate_thumbnail(self, media_item_id: str, timestamp_ms: int) -> Path: ...
    async def delete_media_item(self, media_item_id: str) -> None: ...
```

**Import pipeline:**
1. Validate file (codec, duration, corruption check via FFprobe)
2. Register in `media_items` table
3. Enqueue proxy + thumbnail generation
4. Enqueue analysis jobs (clip + game analyzer based on role)

### 5.3 AnalysisService

```python
class AnalysisService:
    async def start_clip_analysis(self, media_item_id: str) -> Job: ...
    async def start_music_analysis(self, music_track_id: str) -> Job: ...
    async def start_style_analysis(self, reference_id: str) -> Job: ...
    async def get_clip_analysis(self, media_item_id: str) -> ClipAnalysisResult: ...
    async def get_game_events(self, media_item_id: str) -> list[GameEvent]: ...
    async def rank_clips(self, project_id: str, criteria: RankCriteria) -> list[RankedClip]: ...
```

Delegates to AI Engine orchestrator. Persists results via repositories.

### 5.4 TimelineService

```python
class TimelineService:
    async def create_timeline(self, project_id: str, name: str) -> Timeline: ...
    async def get_timeline(self, timeline_id: str) -> TimelineDocument: ...
    async def save_timeline(self, timeline_id: str, doc: TimelineDocument) -> Timeline: ...
    async def generate_timeline(self, request: GenerateTimelineRequest) -> TimelineDocument: ...
    async def apply_edit_commands(self, timeline_id: str, commands: list[EditCommand]) -> TimelineDocument: ...
```

Timeline JSON file is source of truth; DB index updated on save for query performance.

### 5.5 RenderService

```python
class RenderService:
    async def start_render(self, request: RenderRequest) -> RenderJob: ...
    async def cancel_render(self, job_id: str) -> None: ...
    async def get_render_status(self, job_id: str) -> RenderJob: ...
    async def get_presets(self) -> list[RenderPreset]: ...
```

See [09-rendering-pipeline-design.md](./09-rendering-pipeline-design.md).

### 5.6 AudioService

```python
class AudioService:
    async def analyze_audio_levels(self, media_item_id: str) -> AudioLevels: ...
    async def generate_mix(self, timeline_id: str, settings: MixSettings) -> Path: ...
```

Used by RenderService and Audio Agent.

### 5.7 ThumbnailService

```python
class ThumbnailService:
    async def generate_candidates(self, timeline_id: str) -> list[ThumbnailCandidate]: ...
    async def render_thumbnail(self, candidate_id: str, output_path: Path) -> Path: ...
```

## 6. AI Engine Integration

```python
# montage_backend/services/analysis_service.py
class AnalysisService:
    def __init__(self, ai_engine: AIEngine, ...):
        self.ai_engine = ai_engine

    async def start_clip_analysis(self, media_item_id: str) -> Job:
        job = await self.job_queue.enqueue(
            handler=analyze_clip_handler,
            payload={"media_item_id": media_item_id},
            correlation_id=generate_correlation_id(),
        )
        return job
```

The AI Engine lives in `ai/agents/` and is imported by backend job handlers. See [07-ai-agent-design.md](./07-ai-agent-design.md).

## 7. Job Queue

### 7.1 Design

```python
class JobQueue:
    async def enqueue(self, handler: JobHandler, payload: dict, correlation_id: str) -> Job: ...
    async def cancel(self, job_id: str) -> bool: ...
    async def get_status(self, job_id: str) -> JobStatus: ...

    # Internal
    async def _worker_loop(self, worker_id: int) -> None: ...
```

### 7.2 Job Types

| Job Type | Handler | Typical Duration | Priority |
|----------|---------|------------------|----------|
| `proxy_generate` | `proxy_generator` | 5-30s | High |
| `thumbnail_generate` | `thumbnail_generator` | 1-5s | High |
| `clip_analyze` | `analyze_clip_handler` | 10-60s | Normal |
| `albion_analyze` | `analyze_albion_handler` | 10-60s | Normal |
| `music_analyze` | `analyze_music_handler` | 5-20s | Normal |
| `style_analyze` | `analyze_style_handler` | 30-120s | Low |
| `timeline_generate` | `generate_timeline_handler` | 30-120s | Normal |
| `render_export` | `render_export_handler` | 1-10min | Low |

### 7.3 Concurrency

- Default: 2 CPU workers + 1 GPU worker (if available)
- Configurable in settings
- GPU worker serializes PyTorch inference to avoid OOM

### 7.4 Progress Reporting

Workers emit progress via asyncio event bus → WebSocket broadcast:

```python
await event_bus.emit(JobProgressEvent(
    job_id=job.id,
    progress=0.45,
    message="Analyzing motion: frame 1350/3000",
    correlation_id=job.correlation_id,
))
```

## 8. Repository Layer

```python
class MediaRepository:
    async def create(self, item: MediaItemCreate) -> MediaItem: ...
    async def get_by_id(self, id: str) -> MediaItem | None: ...
    async def list_by_project(self, project_id: str, filters: MediaFilters) -> list[MediaItem]: ...
    async def update_status(self, id: str, status: ImportStatus) -> None: ...
    async def delete(self, id: str) -> None: ...
```

Repositories use SQLAlchemy async sessions. No raw SQL in services.

## 9. Media Processing

### 9.1 FFmpeg Wrapper

```python
class FFmpegWrapper:
    async def probe(self, path: Path) -> MediaProbeResult: ...
    async def transcode(self, input: Path, output: Path, options: TranscodeOptions) -> None: ...
    async def extract_frame(self, input: Path, timestamp_ms: int, output: Path) -> Path: ...
    async def extract_audio(self, input: Path, output: Path) -> Path: ...
    async def render_complex(self, filter_graph: str, output: Path) -> None: ...
```

All FFmpeg calls run in thread pool executor to avoid blocking event loop.

### 9.2 Proxy Generation

- Output: 720p H.264, 30fps, CRF 28
- Stored in `{project}/media/proxies/{media_id}.mp4`
- Used for preview and AI analysis (faster)

### 9.3 Frame Extraction (for AI)

```python
class FrameExtractor:
    def extract_batch(self, video_path: Path, timestamps_ms: list[int]) -> FrameBatch: ...
    def extract_range(self, video_path: Path, start_ms: int, end_ms: int, fps: float) -> Iterator[Frame]: ...
```

Uses PyAV for efficient seeking.

## 10. Authentication

```python
# Generated on backend startup; passed to Electron via stdout
AUTH_TOKEN = secrets.token_urlsafe(32)

# Middleware validates on every request
class AuthMiddleware:
    async def __call__(self, request, call_next):
        token = request.headers.get("X-Montage-Token")
        if token != settings.auth_token:
            raise HTTPException(401)
        return await call_next(request)
```

WebSocket connections authenticate via query param: `ws://127.0.0.1:PORT/ws?token=...`

## 11. Configuration

```python
class Settings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 0  # OS-assigned
    worker_count: int = 2
    gpu_enabled: bool = True
    model_dir: Path = Path("ai/models")
    ffmpeg_path: Path | None = None  # auto-detect
    log_level: str = "INFO"
    max_upload_size_mb: int = 0  # N/A for local files

    model_config = SettingsConfigDict(env_prefix="MONTAGE_")
```

## 12. Error Handling

Domain errors and unhandled exceptions are handled in `montage_backend/api/exception_handlers.py`:

```python
class MontageError(Exception):
    code: str
    message: str
    details: dict | None = None

# Handlers registered in main.py:
# - MontageError → structured JSON (400/404/409)
# - SQLAlchemyError → DATABASE_ERROR (500) + logged traceback
# - Exception → INTERNAL_SERVER_ERROR (500) + logged traceback
```

Response shape:

```json
{
  "error": "PROJECT_ALREADY_EXISTS",
  "message": "Project already exists at /path",
  "details": null
}
```

## 13. Logging

```python
logger.info(
    "clip_analysis_complete",
    media_item_id=media_item_id,
    excitement_score=result.excitement_score,
    duration_ms=elapsed,
    correlation_id=correlation_id,
)
```

Logs written to:
- `{project}/logs/backend.log`
- stderr (dev mode)

## 14. Health & Lifecycle

```
GET /health → { "status": "ok", "version": "1.0.0", "models_loaded": true, "queue_depth": 3 }
GET /ready  → { "status": "ready" }  # models loaded, DB connected
```

Electron main process polls `/health` during startup (max 30s, 500ms interval).

## 15. Database Connection

```python
# One connection pool per active project
engine = create_async_engine(f"sqlite+aiosqlite:///{project_db_path}")
async_session = async_sessionmaker(engine, expire_on_commit=False)

# On project open
await run_migrations(project_db_path)
```

## 16. Testing (Backend)

| Level | Tool | Scope |
|-------|------|-------|
| Unit | pytest | Services, repositories, agents |
| Integration | pytest + httpx | API routes with test DB |
| Media | pytest | FFmpeg wrapper with test files |

Fixtures in `apps/backend/tests/conftest.py`.

## 17. Packaging

- PyInstaller bundles backend into single executable
- Bundled inside Electron `resources/backend/`
- AI models downloaded on first run (not bundled due to size)
- FFmpeg bundled for Windows; macOS uses Homebrew path or bundled
