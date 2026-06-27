# Development Guide

**Product:** MontageAI  
**Version:** 1.0  
**Date:** 2026-06-26

---

## 1. Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Node.js | 22 LTS | Frontend build (required — Node 24.16+ and 26.x break Electron install) |
| pnpm | 9+ | Package manager |
| Python | 3.11+ | Backend + AI |
| FFmpeg | 6.0+ | Media processing |
| Git | 2.40+ | Version control |

**Optional:**
- CUDA-capable GPU + drivers (AI inference acceleration)
- Homebrew (macOS, for FFmpeg if not bundled)

---

## 2. Repository Setup

```bash
# Clone repository
git clone <repo-url> montage-ai
cd montage-ai

# Run setup script (installs all dependencies)
./scripts/setup.sh
```

### Manual Setup

```bash
# Frontend dependencies
pnpm install

# Backend virtual environment
cd apps/backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
cd ../..

# Download AI models (optional — script planned for M3+)
# ./scripts/download-models.sh

# Download test media (optional — script planned for M2+)
# ./scripts/download-test-media.sh
```

---

## 3. Development Workflow

### 3.1 Start Development Server

```bash
# From repo root — starts Electron and the Python FastAPI backend automatically
pnpm dev
```

`pnpm dev` runs `electron-vite dev`. The Electron **main process** spawns the Python backend before opening the window:

1. Spawns `apps/backend/.venv/bin/python -m montage_backend.main`
2. Waits for the backend `/ready` endpoint to respond
3. Opens the Electron window and connects the renderer via IPC

No separate backend terminal is required for normal development.

#### Backend environment variables

| Variable | Development default | Purpose |
|----------|---------------------|---------|
| `MONTAGE_BACKEND_URL` | `http://127.0.0.1:8000` | API base URL. When set, Electron connects here and does not spawn a backend. |
| `MONTAGE_AUTH_TOKEN` | `montage-dev-token` | Shared auth token for API/WebSocket (must match on manually started backends) |
| `MONTAGE_HOST` | `127.0.0.1` | Backend bind/connect host |
| `MONTAGE_PORT` | `8000` | Backend port when spawning or connecting |
| `MONTAGE_APP_DATA_DIR` | `~/.montage-ai` | App data directory (Electron sets this when spawning) |
| `MONTAGE_LOG_LEVEL` | `INFO` | Backend log level |

Copy `.env.example` to `.env` to customize. Electron main reads `process.env` at startup.

**Development flow:** Electron resolves `http://127.0.0.1:8000` by default. It connects to an existing server on that port, or spawns one there if none is running. The renderer receives the backend URL via IPC; HTTP requests are proxied through the main process (`backend:request` IPC) to avoid browser CORS.

When running the backend manually, set `MONTAGE_AUTO_SPAWN=false` in `.env` so Electron connects only (no duplicate spawn).

Manual backend (must use the same auth token):

```bash
cd apps/backend && source .venv/bin/activate
MONTAGE_AUTH_TOKEN=montage-dev-token MONTAGE_PORT=8000 python -m montage_backend.main
# or:
MONTAGE_AUTH_TOKEN=montage-dev-token uvicorn montage_backend.main:app --reload --port 8000
```

If the backend fails to start, the UI shows the Python stderr traceback (not just "Failed to fetch").

### 3.2 Electron-Vite Output Paths

**electron-vite v2** compiles the main and preload processes to `apps/desktop/out/`:

| Process | Source | Build output | package.json |
|---------|--------|--------------|--------------|
| Main | `electron/main/index.ts` | `out/main/index.js` | `"main": "out/main/index.js"` |
| Preload | `electron/preload/index.ts` | `out/preload/index.js` | (referenced from main) |
| Renderer | `index.html` + `src/` | `out/renderer/` (production) | Dev: Vite at `localhost:5173` |

electron-vite resolves the Electron entry from `package.json` `"main"` after building. If `"main"` points to a different directory (e.g. legacy `dist-electron/`), startup fails with:

```
Error: No electron app entry file found: .../dist-electron/main/index.js
```

**Validation:** Run `pnpm validate:electron` from the repo root, or `pnpm --filter @montage/desktop postbuild` after a production build. Regression test: `apps/desktop/src/config/electron-entry.test.ts`.

### 3.2.1 Electron Binary Install (pnpm + Node.js)

Two configuration requirements must be satisfied or `node_modules/electron/path.txt` is never created:

1. **pnpm v10+ `allowBuilds`** — Lifecycle scripts are blocked by default. `pnpm-workspace.yaml` must include:

   ```yaml
   allowBuilds:
     electron: true
     esbuild: true
   ```

   Placeholder strings (e.g. `electron: set this to true or false`) or corrupted numeric keys cause pnpm to skip postinstall with `ERR_PNPM_IGNORED_BUILDS`.

2. **Node.js 22 LTS** — Node.js 24.16+ and 26.x stall `extract-zip` during Electron's postinstall; install exits 0 but `path.txt` is missing ([electron#51619](https://github.com/electron/electron/issues/51619)). Use the version in `.node-version` (22). With Homebrew: `brew install node@22 && export PATH="/opt/homebrew/opt/node@22/bin:$PATH"`.

After install, verify: `pnpm exec electron --version` (from `apps/desktop`) and `node scripts/validate-electron-config.mjs --require-electron`.

### 3.3 Backend Only

```bash
cd apps/backend
source .venv/bin/activate
python -m montage_backend.main
# Or with fixed port:
MONTAGE_PORT=8000 python -m montage_backend.main
```

The backend prints a JSON line with `port`, `host`, and `token` once it is accepting connections. API docs: `http://127.0.0.1:<port>/docs`.

### 3.4 Frontend Only

```bash
cd apps/desktop
pnpm dev:renderer
```

Note: Frontend alone requires backend running separately.

---

## 4. Project Structure Quick Reference

```
montage-ai/
├── apps/desktop/          # Electron + React frontend
├── apps/backend/          # Python FastAPI backend
├── packages/shared-types/ # JSON Schema → TS + Python types
├── ai/agents/             # AI agent implementations
├── ai/plugins/albion/     # Albion Online game plugin
├── docs/                  # Design documentation
├── scripts/               # Setup, build, codegen scripts
├── tests/e2e/             # Playwright E2E tests
└── PROJECT_STATE.md       # Living project memory
```

See [03-folder-structure.md](./03-folder-structure.md) for complete structure.

---

## 5. Key Commands

| Command | Description |
|---------|-------------|
| `pnpm dev` | Start full dev environment (Electron + backend) |
| `pnpm test` | Run all tests (frontend Vitest + backend pytest) |
| `pnpm validate:electron` | Verify package.json main matches electron-vite `out/` output |
| `pnpm build` | Production build |
| `pnpm lint` | ESLint check |
| `pnpm typecheck` | TypeScript check |
| `cd apps/backend && pytest tests/` | Backend tests only |
| `ruff check .` | Python lint (from `apps/backend`) |
| `mypy montage_backend` | Python type check (from `apps/backend`) |

---

## 6. Shared Types Workflow

Types are defined in `packages/shared-types/src/` for Milestone 1. JSON Schema codegen (`./scripts/codegen.sh`) is planned for Milestone 2.

Never manually edit generated files once codegen is introduced.

---

## 7. Database Migrations

Milestone 1 uses filtered SQLAlchemy `create_all` for `app.db` and per-project `project.db`. Alembic migrations are planned for Milestone 2.

---

## 8. Adding a New AI Agent

1. Create agent file in `ai/agents/` implementing `BaseAgent`
2. Register in `ai/agents/orchestrator.py`
3. Add job handler in `apps/backend/montage_backend/jobs/handlers/`
4. Add API endpoint if needed
5. Add validation test dataset
6. Write unit tests
7. Update [07-ai-agent-design.md](./07-ai-agent-design.md)

See [07-ai-agent-design.md](./07-ai-agent-design.md) for agent interface specification.

---

## 9. Adding a New Game Plugin

1. Create directory `ai/plugins/{game_name}/`
2. Implement `GameAnalyzerPlugin` protocol
3. Add detector modules in `detectors/`
4. Create UI template config (`config.yaml`)
5. Register plugin in orchestrator
6. Add validation test dataset
7. Update documentation

---

## 10. Testing

```bash
# Frontend unit tests
pnpm test

# Backend unit tests
cd apps/backend && pytest tests/unit

# Backend integration tests
cd apps/backend && pytest tests/integration

# E2E tests (planned Milestone 2)
# pnpm test:e2e

# AI validation tests
cd apps/backend && pytest tests/validation
```

See [19-testing-strategy.md](./19-testing-strategy.md) for full testing guide.

---

## 11. Debugging

### Frontend
- Electron DevTools: `Cmd+Option+I` (macOS) / `Ctrl+Shift+I` (Windows)
- React DevTools extension
- Zustand DevTools

### Backend
- FastAPI auto-docs: `http://127.0.0.1:PORT/docs`
- Log files: `{project}/logs/backend.log`
- Debug mode: `MONTAGE_LOG_LEVEL=DEBUG pnpm dev`

### AI Agents
- Set `MONTAGE_LOG_LEVEL=DEBUG` for verbose agent logging
- Validation test runner: `pytest tests/validation -v --tb=short`
- Frame dump: set `MONTAGE_DUMP_FRAMES=1` to save analyzed frames to `/tmp`

---

## 12. Building for Production

Production packaging (`./scripts/build-release.sh`) is planned for Milestone 7.

---

## 13. Coding Standards

Follow [18-coding-standards.md](./18-coding-standards.md). Key rules:

- TypeScript strict mode; Python type hints everywhere
- No placeholder code
- Structured logging with correlation IDs
- AI outputs must include confidence + reasoning
- Tests required for all new features

---

## 14. Documentation Maintenance

Update docs when architecture changes:

| Change | Update |
|--------|--------|
| New API endpoint | `12-api-design.md` |
| New database table | `04-database-schema.md` |
| New AI agent | `07-ai-agent-design.md` |
| New module | `02-software-architecture.md`, `03-folder-structure.md` |
| Any meaningful work session | `PROJECT_STATE.md` |

---

## 15. Getting Help

1. Check [docs/README.md](./README.md) for document index
2. Check [PROJECT_STATE.md](../PROJECT_STATE.md) for current status
3. Check [17-task-backlog.md](./17-task-backlog.md) for planned work
4. Review [02-software-architecture.md](./02-software-architecture.md) for system overview

---

## 16. Milestone Workflow

### Milestone structure (M2–M7)

| Milestone | Name |
|-----------|------|
| M2 | Media Processing Engine (6 sub-milestones) |
| M3 | AI Analysis Pipeline |
| M4 | AI Montage Generation |
| M5 | Albion Online Intelligence |
| M6 | AI Assistant |
| M7 | Polish & Production |

### Sub-milestone rules (Milestone 2 only)

Milestone 2 is implemented as M2-001 through M2-006. **Do not begin the next sub-milestone until the current one is complete, tested, documented, and committed.**

### Milestone completion rules (all milestones)

At the completion of each milestone:

1. Stop implementation
2. Summarize work completed
3. Update [PROJECT_STATE.md](../PROJECT_STATE.md)
4. **Wait for stakeholder approval** before proceeding

### Daily workflow

1. Check current milestone/sub-milestone in [PROJECT_STATE.md](../PROJECT_STATE.md)
2. Pick task from [17-task-backlog.md](./17-task-backlog.md)
3. Create branch: `milestone-{N}-{task-name}` or `m2-001-{task-name}`
4. Implement following [18-coding-standards.md](./18-coding-standards.md)
5. Write tests per [19-testing-strategy.md](./19-testing-strategy.md)
6. Verify against [20-definition-of-done.md](./20-definition-of-done.md)
7. Update PROJECT_STATE.md
8. Commit; request review/approval before next sub-milestone or milestone
