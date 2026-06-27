# Development Guide

**Product:** MontageAI  
**Version:** 1.0  
**Date:** 2026-06-26

---

## 1. Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Node.js | 20 LTS+ | Frontend build |
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

# Download AI models (optional for M1, required for M3+)
./scripts/download-models.sh

# Download test media (optional)
./scripts/download-test-media.sh
```

---

## 3. Development Workflow

### 3.1 Start Development Server

```bash
# Starts Electron + Python backend concurrently
pnpm dev
```

This runs:
1. Python backend on dynamic localhost port
2. Electron app with HMR

### 3.2 Backend Only

```bash
cd apps/backend
source .venv/bin/activate
uvicorn montage_backend.main:app --reload --port 8000
```

API docs available at `http://127.0.0.1:8000/docs`.

### 3.3 Frontend Only

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
| `pnpm dev` | Start full dev environment |
| `pnpm build` | Production build |
| `pnpm test` | Run all frontend tests |
| `pnpm lint` | ESLint check |
| `pnpm typecheck` | TypeScript check |
| `pytest` | Run all backend tests |
| `ruff check .` | Python lint |
| `mypy montage_backend ai` | Python type check |
| `./scripts/codegen.sh` | Regenerate shared types |
| `pnpm test:e2e` | Run Playwright E2E tests |

---

## 6. Shared Types Workflow

Types are defined once in JSON Schema and generated for both languages:

```bash
# 1. Edit schema
vim packages/shared-types/schemas/timeline.schema.json

# 2. Regenerate
./scripts/codegen.sh

# 3. TypeScript types updated in packages/shared-types/src/
# 4. Python models updated in packages/shared-types/python/
```

Never manually edit generated files.

---

## 7. Database Migrations

```bash
cd apps/backend
source .venv/bin/activate

# Create new migration
alembic revision --autogenerate -m "add clip_analysis table"

# Apply migrations
alembic upgrade head
```

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

# E2E tests (requires built app)
pnpm test:e2e

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

```bash
# Full production build
./scripts/build-release.sh

# Output:
# dist/montage-ai-{version}-mac.dmg
# dist/montage-ai-{version}-win.exe
```

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

1. Check current milestone in [PROJECT_STATE.md](../PROJECT_STATE.md)
2. Pick task from [17-task-backlog.md](./17-task-backlog.md)
3. Create branch: `milestone-{N}-{task-name}`
4. Implement following [18-coding-standards.md](./18-coding-standards.md)
5. Write tests per [19-testing-strategy.md](./19-testing-strategy.md)
6. Verify against [20-definition-of-done.md](./20-definition-of-done.md)
7. Update PROJECT_STATE.md
8. Create PR for review
9. After milestone exit criteria met → stakeholder approval → next milestone
