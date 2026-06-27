# Software Architecture Document

**Product:** MontageAI  
**Version:** 1.0  
**Date:** 2026-06-26

---

## 1. Architecture Overview

MontageAI follows a **hybrid desktop architecture**: an Electron shell hosts a React frontend, which communicates with a local Python backend via HTTP/WebSocket over localhost. All media processing, AI inference, and rendering run in the Python backend. The frontend owns UI state and timeline interactions; the backend owns heavy computation and persistence.

```
┌─────────────────────────────────────────────────────────────────┐
│                     ELECTRON MAIN PROCESS                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Window Mgmt  │  │ Backend Proc │  │ File System Access   │  │
│  │ Menu/IPC     │  │ Spawner      │  │ Native Dialogs       │  │
│  └──────────────┘  └──────┬───────┘  └──────────────────────┘  │
└───────────────────────────┼─────────────────────────────────────┘
                            │ spawn / health check
┌───────────────────────────┼─────────────────────────────────────┐
│                     ELECTRON RENDERER (React)                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │ Timeline │ │ Preview  │ │ Media    │ │ AI Chat /        │  │
│  │ Engine   │ │ Player   │ │ Library  │ │ Suggestions      │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────────┬─────────┘  │
│       └────────────┴────────────┴────────────────┘              │
│                         │                                        │
│              ┌──────────▼──────────┐                            │
│              │   Frontend Services  │                            │
│              │   (API Client, State)│                            │
│              └──────────┬──────────┘                            │
└─────────────────────────┼───────────────────────────────────────┘
                          │ HTTP REST + WebSocket
┌─────────────────────────▼───────────────────────────────────────┐
│                     PYTHON BACKEND (FastAPI)                      │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌─────────────┐  │
│  │ Project    │ │ Media      │ │ Timeline   │ │ Render      │  │
│  │ Service    │ │ Service    │ │ Service    │ │ Service     │  │
│  └────────────┘ └────────────┘ └────────────┘ └─────────────┘  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                    AI Engine (Orchestrator)               │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────────┐ │  │
│  │  │ Clip    │ │ Albion  │ │ Music   │ │ Style / Timeline│ │  │
│  │  │Analyzer │ │Analyzer │ │Analyzer │ │ Planner Agents  │ │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────────────┘ │  │
│  └────────────────────────────────────────────────────────────┘  │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐                   │
│  │ FFmpeg     │ │ SQLite     │ │ Job Queue  │                   │
│  │ Pipeline   │ │ Repository │ │ (asyncio)  │                   │
│  └────────────┘ └────────────┘ └────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
                          │
              ┌───────────▼───────────┐
              │   Local File System   │
              │  (project folder)     │
              └───────────────────────┘
```

## 2. Architectural Style

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Pattern | Layered + Event-driven | Clear separation; async jobs for long tasks |
| Frontend | Component-based SPA | React ecosystem; rich UI |
| Backend | Service-oriented modules | Independent testing; agent isolation |
| Communication | REST + WebSocket | REST for CRUD; WS for progress streams |
| State | Frontend owns UI state; backend owns persistence | Avoid split-brain |
| AI | Agent pipeline with orchestrator | Independent agents; composable |

## 3. Core Modules

### 3.1 Module Map

| Module | Layer | Responsibility |
|--------|-------|----------------|
| Project Management | Backend + Frontend | CRUD projects, settings, auto-save |
| Media Library | Backend + Frontend | Import, catalog, thumbnails, proxies |
| Timeline Engine | Frontend (logic) + Shared types | Timeline document, edits, undo/redo |
| Preview Renderer | Frontend | Canvas/WebCodecs or proxy playback |
| AI Engine | Backend | Orchestrates all AI agents |
| Clip Analyzer | Backend (AI Agent) | Scene/motion/excitement analysis |
| Albion Event Analyzer | Backend (AI Agent) | Game-specific event detection |
| Music Analyzer | Backend (AI Agent) | BPM, beats, drops, energy |
| Style Analyzer | Backend (AI Agent) | Reference montage style extraction |
| Timeline Planner | Backend (AI Agent) | Generate timeline from inputs |
| Rendering Engine | Backend | FFmpeg export pipeline |
| Audio Engine | Backend | Mixing, normalization, ducking |
| Effects Engine | Backend + Frontend | Speed ramps, zooms, transitions |
| Thumbnail Generator | Backend (AI Agent) | YouTube thumbnail candidates |
| AI Chat Assistant | Backend + Frontend | NL timeline editing |
| Settings | Frontend + Backend | User preferences, model paths |

### 3.2 Dependency Rules

```
Frontend ──► Shared Types (read-only)
Frontend ──► Backend API (HTTP/WS)
Backend Services ──► Repository Layer ──► SQLite
Backend Services ──► AI Engine ──► Individual Agents
Backend Services ──► FFmpeg Pipeline
AI Agents ──► ML Models (PyTorch/ONNX)
AI Agents ──✗ Frontend (never direct)
```

**Forbidden:**
- Frontend accessing SQLite directly
- AI agents mutating timeline without going through Timeline Service
- Circular imports between backend services

## 4. Process Architecture

### 4.1 Electron Processes

| Process | Role |
|---------|------|
| Main | App lifecycle, native menus, spawns Python backend, IPC bridge |
| Renderer | React UI, timeline, preview |
| Preload | Secure IPC expose (file dialogs, shell open) |

### 4.2 Python Backend

Single FastAPI process with:
- **Uvicorn** ASGI server on dynamic localhost port
- **asyncio** job queue for analysis/render tasks
- **Thread pool** for CPU-bound FFmpeg/OpenCV work
- **GPU worker pool** (optional) for PyTorch inference

### 4.3 Startup Sequence

1. Electron main starts
2. Main spawns Python backend subprocess
3. Main polls `/health` until ready (timeout 30s)
4. Renderer loads; connects to backend
5. User opens/creates project

## 5. Data Flow

### 5.1 Import → Analyze → Timeline

```
User imports clips
    → Media Service: register files, generate proxies/thumbnails
    → Job Queue: enqueue ClipAnalyzer + AlbionAnalyzer per clip
    → WebSocket: progress events to frontend
    → Repository: persist analysis results
User imports music + references
    → MusicAnalyzer + StyleAnalyzer jobs
User clicks "Generate Timeline"
    → TimelinePlannerAgent: reads all metadata
    → Timeline Service: creates timeline document
    → Frontend: loads timeline into Timeline Engine
```

### 5.2 Edit → Export

```
User edits timeline (manual or AI chat)
    → Timeline Engine: local state + undo stack
    → Auto-save: debounced sync to backend
User clicks Export
    → Render Service: build FFmpeg graph from timeline
    → Job Queue: render job
    → WebSocket: render progress
    → Output file written to user path
```

## 6. Project File Layout (Runtime)

```
MyMontageProject/
├── project.json              # Project manifest
├── project.db                # SQLite database
├── media/
│   ├── originals/            # Symlinks or copies (configurable)
│   └── proxies/              # Low-res proxy files
├── thumbnails/
├── analysis/                 # Cached agent outputs (JSON)
├── timelines/
│   └── main.timeline.json    # Current timeline document
├── exports/
├── cache/
└── logs/
```

## 7. Communication Protocol

| Channel | Use Case | Format |
|---------|----------|--------|
| REST | CRUD, commands | JSON |
| WebSocket | Job progress, analysis streams | JSON events |
| IPC (Electron) | Native dialogs, reveal in finder | Typed messages |

See [12-api-design.md](./12-api-design.md) for full API specification.

## 8. Shared Package

TypeScript and Python share timeline/media type definitions:

- `packages/shared-types/` — JSON Schema source of truth
- Codegen: TypeScript interfaces + Python dataclasses/Pydantic models

## 9. Error Handling Strategy

| Layer | Strategy |
|-------|----------|
| AI Agents | Return result with confidence; never throw for low confidence |
| Services | Domain exceptions → HTTP status codes |
| Frontend | Toast notifications + retry for transient errors |
| Render | Fail job with detailed FFmpeg stderr log |

## 10. Scalability Considerations

- Job queue supports concurrent analysis (configurable workers)
- Proxy generation parallelized
- Large projects: paginated media library queries
- Timeline: virtualized rendering for 1000+ clips

## 11. Extensibility — Game Plugins

Albion analyzer implements `GameAnalyzerPlugin` interface:

```python
class GameAnalyzerPlugin(Protocol):
    game_id: str
    def analyze(self, clip: MediaClip, frames: FrameBatch) -> list[GameEvent]: ...
    def get_event_types(self) -> list[EventTypeDefinition]: ...
```

Future games add new plugin modules without changing core architecture.

## 12. Security Model

- Backend binds to `127.0.0.1` only
- Random port per session; token auth on API
- No external network unless user opts into cloud LLM
- Electron context isolation enabled; no nodeIntegration in renderer

## 13. Observability

- Structured logging (JSON) with `correlation_id` per job
- Log files in project `logs/` directory
- Optional debug panel in app (dev mode)

## 14. Architecture Decision Records

| ADR | Decision | See |
|-----|----------|-----|
| ADR-001 | Electron + Python split | [13-technology-decisions.md](./13-technology-decisions.md) |
| ADR-002 | SQLite per project | [13-technology-decisions.md](./13-technology-decisions.md) |
| ADR-003 | Timeline as JSON document | [08-timeline-engine-design.md](./08-timeline-engine-design.md) |
| ADR-004 | FFmpeg for all rendering | [09-rendering-pipeline-design.md](./09-rendering-pipeline-design.md) |
| ADR-005 | Agent orchestrator pattern | [07-ai-agent-design.md](./07-ai-agent-design.md) |
