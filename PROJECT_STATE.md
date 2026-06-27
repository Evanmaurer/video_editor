# PROJECT_STATE.md — MontageAI

> This file is the project's memory. Updated after every meaningful coding session.

---

## Current Milestone

**Milestone 1: Application Shell** — **Complete** (2026-06-27, tag `milestone-1`)

**Next:** Milestone 2 — Media Pipeline (not started)

---

## Completed Work

### Milestone 0 (2026-06-26)
- Complete software design package (20 documents)

### Milestone 1 (2026-06-27)
- [x] Monorepo initialized (pnpm workspaces, Node 22 LTS pin)
- [x] Electron + React + TypeScript + TailwindCSS app scaffold
- [x] Python FastAPI backend scaffold
- [x] Backend spawn + health check + auth token (Electron main process)
- [x] IPC-proxied API requests (main-process fetch, no renderer CORS)
- [x] Welcome screen with New Project / Open Project
- [x] New Project wizard (create project on disk)
- [x] Project create / open / save / close API + service
- [x] Recent projects list
- [x] Resizable panel layout shell (Media, Preview, Timeline, Inspector, AI Suggestions)
- [x] Menu bar, toolbar (disabled placeholders), status bar
- [x] Settings panel (GPU toggle, LLM provider abstraction config)
- [x] LLM provider abstraction (Ollama, OpenAI, none) — selectable in Settings
- [x] GPU auto-detection with CPU fallback + performance warning in health/status
- [x] WebSocket client scaffold
- [x] Shared types package
- [x] Structured logging (structlog backend)
- [x] Structured JSON error responses + full traceback logging for unhandled exceptions
- [x] Lazy `app.db` initialization (`ensure_database_started`) — fixes fresh-install 500
- [x] Albion template system design stub (`ai/plugins/albion/`)
- [x] `./scripts/setup.sh` — documented bootstrap for clean clone
- [x] `./scripts/validate-electron-config.mjs` — electron-vite entry path guard
- [x] `.env.example` for dev configuration
- [x] Unit tests: ProjectService (4), LlmService (4), backend config/paths (8 frontend)
- [x] Integration tests: API (10)
- [x] Frontend unit tests: 14 total (Vitest)
- [x] All 32 tests passing; TypeScript strict check passing
- [x] Documentation updated for M1 implementation
- [x] Git tag `milestone-1` + [milestone-1-summary.md](docs/milestone-1-summary.md)

---

## Work In Progress

None — awaiting Milestone 2 kickoff.

---

## Known Bugs

All M1 bugs resolved:

| ID | Issue | Status |
|----|-------|--------|
| BUG-001 | ~~electron-vite entry path (`dist-electron/` vs `out/`)~~ | **Fixed** |
| BUG-002 | ~~Electron postinstall skipped (allowBuilds, Node 26)~~ | **Fixed** |
| BUG-003 | ~~Backend ready signal race~~ | **Fixed** |
| BUG-004 | ~~Missing CORS for dev renderer~~ | **Fixed** |
| BUG-005 | ~~Random spawned port in dev~~ | **Fixed** |
| BUG-006 | ~~Renderer CORS/OPTIONS 401~~ | **Fixed** (IPC proxy) |
| BUG-007 | ~~POST `/api/v1/projects` HTTP 500 on fresh install~~ | **Fixed** |

---

## Known Limitations (M1)

| Limitation | Impact | Target milestone |
|------------|--------|------------------|
| Empty panel shells | No media, timeline editing, or preview playback | M2–M4 |
| Disabled toolbar | Placeholder actions only | M2+ |
| No media import | Cannot add clips | M2 |
| No background job queue | No long-running tasks | M2 |
| WebSocket scaffold only | No live progress events | M2 |
| LLM config only | No AI chat UI | M7 |
| In-app menu bar | No native OS menu | Deferred |
| No production installer | Dev workflow only | M8 |
| No E2E tests | Manual verification only | M2 |

---

## Technical Debt

| Item | Priority | Notes |
|------|----------|-------|
| Alembic migrations | Medium | Using filtered `create_all` for M1; add Alembic in M2 |
| Electron E2E tests | Medium | Playwright Electron tests planned M2 |
| Native application menu | Low | In-app menu bar sufficient for M1 |
| `codegen.sh` / shared-types codegen | Low | Manual types for M1; automate in M2 |
| `download-models.sh` | Low | Required M3+; script not yet created |
| `build-release.sh` | Low | Production packaging M8 |
| LLM hardware-based default selection | Low | Auto-pick model by RAM/VRAM in M7 |
| Albion calibration wizard | — | Planned Milestone 3 |

---

## Deferred Improvements

| Improvement | Reason deferred | Revisit |
|-------------|-----------------|---------|
| Renderer direct fetch + CORS | IPC proxy is simpler and reliable for M1 | M2 if needed |
| Dynamic backend port in dev | Fixed `:8000` reduces confusion | Production only |
| Shared UI component package | Single app for M1 | M3+ |
| Turbo monorepo task runner | pnpm filters sufficient | When CI grows |
| Timeline engine | Out of M1 scope | M4 |
| FFmpeg integration | Out of M1 scope | M2 |

---

## Architectural Decisions

| ADR | Decision | Rationale |
|-----|----------|-----------|
| ADR-001 | Electron + Python hybrid | React UI + Python ML/media |
| ADR-002 | SQLite per project | Portable, zero-config |
| ADR-003 | Timeline as JSON document | Editable, diffable, AI-friendly |
| ADR-004 | FFmpeg for all rendering | Industry standard |
| ADR-005 | Agent orchestrator pattern | Independent, testable AI agents |
| ADR-006 | Zustand for frontend state | Lightweight, performant |
| ADR-007 | FastAPI for backend | Async, OpenAPI, WebSocket |
| ADR-008 | JSON Schema shared types | Single source of truth |
| ADR-009 | Proxy media for preview/analysis | 4x faster |
| ADR-010 | Local-first with optional cloud LLM | Privacy; offline capability |
| ADR-011 | LLM provider abstraction | Ollama + OpenAI + none |
| ADR-012 | GPU optional with CPU fallback | App functional without GPU |
| ADR-013 | Data-driven Albion UI templates | Presets + calibration wizard |
| ADR-014 | Graceful AI degradation | AI failures never block editing |
| ADR-015 | IPC-proxied backend HTTP | Avoids Electron renderer CORS in dev |

---

## Next Priorities (Milestone 2: Media Pipeline)

1. M2-001: FFmpeg wrapper (probe, transcode, extract)
2. M2-002: MediaService.import_files
3. M2-007: Background job queue
4. M2-010: Media library grid UI with real data
5. M2-019: E2E test — import folder → see clips

**Do not start Milestone 3 work until M2 exit criteria are met.**

---

## Metrics

| Metric | Value |
|--------|-------|
| Milestone | 1 of 8 complete |
| Backend tests | 18 passing |
| Frontend tests | 14 passing |
| Total tests | 32 passing |
| Open P0 bugs | 0 |
| Git tag | `milestone-1` |

---

## Session Log

| Date | Milestone | Summary |
|------|-----------|---------|
| 2026-06-26 | M0 | Created complete software design package (20 documents) |
| 2026-06-27 | M1 | Application shell: Electron UI, Python backend, project CRUD, settings, LLM/GPU scaffolding |
| 2026-06-27 | M1 | Fixed electron-vite paths, backend spawn/CORS/port issues, IPC API proxy, project create 500 |
| 2026-06-27 | M1 | Stabilization pass: removed debug logging, docs updated, tag `milestone-1` |
