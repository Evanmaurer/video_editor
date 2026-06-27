# Milestone 1 Summary — Application Shell

**Product:** MontageAI  
**Version:** 0.1.0  
**Completed:** 2026-06-27  
**Git tag:** `milestone-1`

---

## Goal

Deliver a launchable desktop application shell with a connected Python backend, project lifecycle management, and a professional dark UI — no media pipeline or AI analysis yet.

---

## Delivered

### Desktop (Electron + React)
- electron-vite scaffold with main, preload, and renderer processes
- Welcome screen with New Project wizard and Open Project flow
- Resizable panel layout (Media, Preview, Timeline, Inspector, AI Suggestions)
- In-app menu bar, toolbar placeholders, status bar
- Settings panel (GPU toggle, LLM provider configuration)
- Backend auto-spawn in dev; connect-only mode via `MONTAGE_AUTO_SPAWN=false`
- IPC-proxied API requests (`backend:request`) — no renderer CORS issues
- Dev default backend URL: `http://127.0.0.1:8000`

### Backend (Python FastAPI)
- Health and readiness endpoints (`/health`, `/ready`)
- Token auth middleware (`X-Montage-Token`)
- Project CRUD: create, open, save, close, recent list
- App settings persistence in `app.db`
- LLM provider abstraction (Ollama, OpenAI, none)
- GPU auto-detection with CPU fallback
- Structured JSON error responses + traceback logging for unhandled errors
- Lazy `app.db` initialization on first API request (prevents 500 on fresh install)

### Shared infrastructure
- pnpm monorepo with `@montage/shared-types` package
- `./scripts/setup.sh` — Node + Python bootstrap
- `./scripts/validate-electron-config.mjs` — electron-vite entry path guard
- `.node-version` pin (Node 22 LTS)
- `.env.example` for local configuration

---

## Test coverage (M1 exit)

| Suite | Count | Tool |
|-------|-------|------|
| Backend unit | 8 | pytest |
| Backend integration | 10 | pytest + httpx |
| Frontend unit | 14 | Vitest |
| **Total** | **32** | |

Critical workflows covered:
- Health check (no auth required)
- API auth enforcement
- Project create on clean `app.db`
- Project open / save / settings roundtrip
- Structured error responses (duplicate project, invalid path)
- Electron entry path validation
- Backend URL resolution

---

## Known limitations (M1)

- Panels are empty shells — no media, timeline editing, or preview playback
- Toolbar actions are disabled placeholders
- WebSocket client scaffold only; no real-time job progress
- No Alembic migrations yet (`create_all` for app/project DB)
- No Playwright E2E tests yet (planned M2)
- LLM chat UI not wired; provider config only
- Native OS menu deferred; in-app menu bar used instead
- Production packaging not implemented (`build-release.sh` planned)

---

## Setup verification

From a clean clone:

```bash
./scripts/setup.sh
pnpm dev
```

Then use **New Project** in the welcome screen. Project folder and `project.db` are created on disk; the editor shell opens.

**Requirements:** Node.js 22 LTS, Python 3.11+, pnpm 9+.

---

## Next milestone

**Milestone 2: Media Processing Engine** — six sequential sub-milestones:

| Sub-milestone | Focus |
|---------------|-------|
| M2-001 | Media Processing Engine (FFmpeg, import, proxy, waveform) |
| M2-002 | Media Library |
| M2-003 | Timeline Engine |
| M2-004 | Playback Engine |
| M2-005 | Export Engine |
| M2-006 | AI Metadata Engine |

Then M3 (AI Analysis Pipeline) through M7 (Polish & Production). See [16-milestone-breakdown.md](./16-milestone-breakdown.md) and [PROJECT_STATE.md](../PROJECT_STATE.md).
