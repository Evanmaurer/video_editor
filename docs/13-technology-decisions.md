# Technology Decisions

**Product:** MontageAI  
**Version:** 1.0  
**Date:** 2026-06-26

---

## ADR Index

| ADR | Title | Status |
|-----|-------|--------|
| ADR-001 | Electron + Python Hybrid Architecture | Accepted |
| ADR-002 | SQLite Per Project | Accepted |
| ADR-003 | Timeline as JSON Document | Accepted |
| ADR-004 | FFmpeg for All Rendering | Accepted |
| ADR-005 | Agent Orchestrator Pattern | Accepted |
| ADR-006 | Zustand for Frontend State | Accepted |
| ADR-007 | FastAPI for Backend | Accepted |
| ADR-008 | JSON Schema for Shared Types | Accepted |
| ADR-009 | Proxy Media for Preview and Analysis | Accepted |
| ADR-010 | Local-First with Optional Cloud LLM | Accepted |
| ADR-011 | LLM Provider Abstraction | Accepted |
| ADR-012 | GPU Optional with CPU Fallback | Accepted |
| ADR-013 | Data-Driven Albion UI Templates | Accepted |
| ADR-014 | Graceful AI Degradation | Accepted |

---

## ADR-001: Electron + Python Hybrid Architecture

**Status:** Accepted  
**Date:** 2026-06-26

### Context

MontageAI needs a professional desktop UI and heavy Python-based AI/media processing. Options considered:

1. **Pure Electron (Node.js backend)** — JS ML ecosystem is weaker
2. **Pure Python (PyQt/Tauri+Python)** — UI framework less mature for NLE-style apps
3. **Electron frontend + Python backend** — Best of both worlds
4. **Tauri + Python sidecar** — Lighter but less mature ecosystem

### Decision

Electron frontend (React/TypeScript) + Python backend (FastAPI) as a spawned subprocess.

### Rationale

- React ecosystem is ideal for complex, panel-based professional UIs
- Python dominates ML/CV (PyTorch, OpenCV, Whisper, librosa)
- FFmpeg integration is mature in Python
- Electron provides native menus, file dialogs, auto-update path
- Subprocess isolation prevents Python crashes from killing UI

### Consequences

- Two runtime environments to package and maintain
- IPC/HTTP overhead is negligible for desktop (localhost)
- PyInstaller bundling required for Python backend
- Need robust backend lifecycle management (spawn, health check, restart)

---

## ADR-002: SQLite Per Project

**Status:** Accepted

### Context

Project metadata storage options: SQLite, PostgreSQL, JSON files only, LevelDB.

### Decision

One SQLite database per project (`project.db`), plus JSON files for timeline documents.

### Rationale

- Zero-config; no external database server
- Portable — copy project folder = complete backup
- SQL queries for filtering/ranking hundreds of clips
- WAL mode gives good concurrent read performance
- JSON timeline file is human-readable and diff-friendly

### Consequences

- No cross-project queries (acceptable for desktop app)
- Migration strategy needed (Alembic)
- Large JSON blobs (beat maps) stored in TEXT columns

---

## ADR-003: Timeline as JSON Document

**Status:** Accepted

### Context

Timeline representation options: JSON document, binary format, EDL/XML (FCP/Premiere), custom binary.

### Decision

JSON document with JSON Schema validation. Source of truth on disk; DB index for queries.

### Rationale

- Human-readable and debuggable
- AI agents output JSON naturally
- Easy to version, diff, and undo
- JSON Schema enables shared TypeScript/Python types
- Export to EDL/XML can be added as output format later

### Consequences

- Large timelines (1000+ clips) may be slow to parse — mitigate with DB index
- Need schema versioning for forward compatibility

---

## ADR-004: FFmpeg for All Rendering

**Status:** Accepted

### Context

Rendering options: FFmpeg CLI, GStreamer, custom pipeline, cloud render farm.

### Decision

FFmpeg CLI invoked via Python subprocess for all video rendering.

### Rationale

- Industry standard; supports all needed codecs and filters
- Complex filter graphs for transitions, effects, audio mixing
- Hardware encoding support (VideoToolbox, NVENC)
- No licensing concerns for desktop app
- PyAV complements FFmpeg for frame-level access

### Consequences

- FFmpeg must be bundled (Windows) or detected (macOS)
- Filter graph complexity requires careful testing
- Progress parsing from stderr is fragile but well-documented

---

## ADR-005: Agent Orchestrator Pattern

**Status:** Accepted

### Context

AI architecture options: monolithic pipeline, microservices, agent orchestrator, single LLM does everything.

### Decision

Independent agents with a central orchestrator. Each agent is a Python class implementing `BaseAgent`.

### Rationale

- Agents are independently testable and versionable
- New games add new analyzer plugins without changing core
- Agents can be re-run individually (re-analyze one clip)
- Confidence/reasoning enforced at agent interface level
- Avoids single-point-of-failure in AI pipeline

### Consequences

- Orchestrator adds complexity but pays off in maintainability
- Agent version management needed
- Inter-agent data passing must be typed (Pydantic models)

---

## ADR-006: Zustand for Frontend State

**Status:** Accepted

### Context

State management options: Redux Toolkit, Zustand, Jotai, MobX, React Context.

### Decision

Zustand with selector-based subscriptions.

### Rationale

- Minimal boilerplate vs Redux
- Good performance with selectors
- Easy to integrate with Timeline Engine (external module)
- Small bundle size
- Sufficient for desktop app complexity

### Consequences

- No built-in devtools middleware (Zustand devtools available)
- Less structure enforcement than Redux — mitigated by clear store boundaries

---

## ADR-007: FastAPI for Backend

**Status:** Accepted

### Context

Python web framework options: FastAPI, Flask, Django, raw asyncio.

### Decision

FastAPI with Uvicorn ASGI server.

### Rationale

- Native async support for job queue and WebSocket
- Automatic OpenAPI generation
- Pydantic v2 integration for request/response validation
- WebSocket support built-in
- Excellent performance for local API

### Consequences

- ASGI-specific patterns needed (thread pool for blocking work)
- FastAPI startup/shutdown events for lifecycle management

---

## ADR-008: JSON Schema for Shared Types

**Status:** Accepted

### Context

Frontend (TypeScript) and backend (Python) must share type definitions for timeline, analysis results, API payloads.

### Decision

JSON Schema as source of truth in `packages/shared-types/schemas/`. Codegen to TypeScript interfaces and Pydantic models.

### Rationale

- Language-neutral schema definition
- Validation on both sides
- Single source of truth prevents drift
- AI agent outputs validate against schemas

### Consequences

- Codegen step in build pipeline
- Schema changes require regeneration and coordinated updates

---

## ADR-009: Proxy Media for Preview and Analysis

**Status:** Accepted

### Context

Working with full-resolution 1080p60 gameplay footage (potentially hundreds of clips) is slow for preview and analysis.

### Decision

Generate 720p30 H.264 proxy files on import. Use proxies for preview and AI analysis; originals for final export only.

### Rationale

- 4x+ faster decode for analysis
- Smooth preview playback
- Original files never modified
- Standard NLE workflow (Premiere, Resolve use proxies)

### Consequences

- Additional disk space (~10-15% of original)
- Proxy generation adds to import time (background, non-blocking)
- Must track proxy ↔ original mapping

---

## ADR-010: Local-First with Optional Cloud LLM

**Status:** Accepted

### Context

AI Chat Assistant needs language understanding. Options: cloud API only, local LLM only, hybrid.

### Decision

Local-first: rule-based parser + optional local small LLM (Llama 3.2 3B / Phi-3). Cloud API (OpenAI/Anthropic) as opt-in upgrade.

### Rationale

- Privacy: gameplay footage stays local
- Offline capability for core editing
- Cloud opt-in for users who want better NL understanding
- Rule-based parser handles 80% of common commands without any LLM

### Consequences

- Local LLM adds ~2GB model download
- Rule-based parser must be maintained for common commands
- Cloud integration requires API key management in settings

---

## ADR-011: LLM Provider Abstraction

**Status:** Accepted (2026-06-27)

### Decision

Chat assistant uses a `LlmProvider` interface with pluggable backends: Ollama (default), OpenAI, and none. Model and provider are selectable in Settings. No hardcoded model in application code.

### Default Models

- **Capable hardware:** Qwen3 8B Instruct via Ollama (`qwen3:8b-instruct`)
- **Low-end hardware:** Llama 3.2 3B via Ollama (`llama3.2:3b`)

The rest of the application does not depend on which LLM is selected. If LLM is unavailable, AI chat disables gracefully; editor remains fully functional.

---

## ADR-012: GPU Optional with CPU Fallback

**Status:** Accepted (2026-06-27)

### Decision

GPU acceleration is optional. Backend auto-detects hardware on startup. GPU used when available and enabled in settings. CPU fallback always available with user-visible performance warning (~3-5x slower estimate).

---

## ADR-013: Data-Driven Albion UI Templates

**Status:** Accepted (2026-06-27)

### Decision

Albion event detection uses YAML template files supporting multiple resolutions and UI scales. Ship common presets. Include calibration wizard for user fine-tuning. New templates added without core code changes.

See `ai/plugins/albion/`.

---

## ADR-014: Graceful AI Degradation

**Status:** Accepted (2026-06-27)

### Decision

AI component failures must never block core workflows (import, manual edit, preview, export).

| Component failure | Fallback |
|-------------------|----------|
| OCR | Continue without OCR metadata |
| Albion detection | Use motion/scene analysis only |
| Music analysis | Manual beat markers |
| Local LLM | Disable AI chat; editor fully functional |
| Style analyzer | Timeline planner uses default pacing |

Agents return low-confidence results rather than throwing. Services catch agent errors and log; UI shows degraded state.

---

## Technology Stack Summary

| Layer | Technology | Version |
|-------|-----------|---------|
| Desktop shell | Electron | 33+ |
| Frontend framework | React | 18+ |
| Frontend language | TypeScript | 5.5+ (strict) |
| Frontend styling | TailwindCSS | 3.4+ |
| Frontend state | Zustand | 5+ |
| Frontend data fetching | TanStack Query | 5+ |
| Build tool | electron-vite | 2+ |
| Backend framework | FastAPI | 0.115+ |
| Backend language | Python | 3.11+ |
| Backend server | Uvicorn | 0.30+ |
| ORM | SQLAlchemy | 2.0+ |
| Migrations | Alembic | 1.13+ |
| Database | SQLite | 3.40+ |
| Video processing | FFmpeg | 6.0+ |
| Video frames | PyAV | 12+ |
| Computer vision | OpenCV | 4.9+ |
| ML framework | PyTorch | 2.2+ |
| ML inference | ONNX Runtime | 1.17+ |
| Speech | Whisper | (openai-whisper) |
| OCR | EasyOCR | 1.7+ |
| Audio analysis | librosa | 0.10+ |
| Logging | structlog | 24+ |
| Testing (JS) | Vitest + Playwright | Latest |
| Testing (Python) | pytest | 8+ |
| Monorepo | pnpm workspaces | 9+ |
| Linting (JS) | ESLint + Prettier | Latest |
| Linting (Python) | Ruff | 0.4+ |
| Type checking (Python) | mypy | 1.10+ |

---

## Rejected Alternatives

| Alternative | Reason Rejected |
|-------------|-----------------|
| Next.js | No SSR needed; Electron renders locally |
| Django | Too heavy for local API server |
| PostgreSQL | Overkill; requires external server |
| Redis job queue | Unnecessary external dependency for desktop |
| Canvas-based timeline | DOM approach simpler for v1; canvas upgrade later |
| Cloud-only AI | Privacy concerns; offline requirement |
| Tauri | Less mature Electron ecosystem for complex desktop apps |
| Single LLM for all AI | Not specialized enough; no structured confidence/reasoning |
