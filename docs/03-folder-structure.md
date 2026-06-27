# Folder Structure

**Product:** MontageAI  
**Version:** 1.0  
**Date:** 2026-06-26

---

## Repository Root

```
montage-ai/
├── PROJECT_STATE.md                 # Living project memory (updated each session)
├── README.md                        # Project overview, quick start
├── LICENSE
├── .gitignore
├── .editorconfig
├── package.json                     # Root workspace (pnpm/npm workspaces)
├── pnpm-workspace.yaml
├── turbo.json                       # Optional: monorepo task runner
│
├── apps/
│   ├── desktop/                     # Electron application
│   └── backend/                     # Python FastAPI server
│
├── packages/
│   ├── shared-types/                # JSON Schema → TS + Python codegen
│   ├── ui/                          # Shared React components (future)
│   └── config/                      # Shared ESLint, TSConfig, Tailwind presets
│
├── ai/
│   ├── models/                      # Model weights (gitignored; download scripts)
│   ├── agents/                      # Agent implementations (Python)
│   ├── plugins/
│   │   └── albion/                  # Albion Online game plugin
│   └── training/                    # Fine-tuning scripts (future)
│
├── docs/                            # All design documentation
│
├── scripts/
│   ├── setup.sh                     # Dev environment bootstrap (M1)
│   └── validate-electron-config.mjs   # electron-vite entry path guard (M1)
│   # Planned: download-models.sh, codegen.sh, build-release.sh
│
├── assets/
│   ├── icons/                       # App icons
│   ├── fonts/
│   └── test-media/                  # Sample clips for dev (gitignored large files)
│
└── tests/
    ├── e2e/                         # Playwright end-to-end tests
    ├── integration/                 # Cross-module integration tests
    └── fixtures/                    # Test data factories
```

---

## `apps/desktop/` — Electron Frontend

```
apps/desktop/
├── package.json              # "main": "out/main/index.js" (electron-vite v2)
├── electron.vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── index.html
│
├── electron/
│   ├── main/
│   │   ├── index.ts                 # Main process entry
│   │   ├── backend-manager.ts       # Spawn/monitor Python backend
│   │   ├── backend-config.ts        # Dev/prod backend URL resolution
│   │   ├── backend-paths.ts         # Resolve backend dir + Python venv
│   │   └── backend-request.ts       # IPC HTTP proxy to backend
│   └── preload/
│       └── index.ts                 # Context bridge API
│
└── src/
    ├── main.tsx                     # React entry
    ├── App.tsx
    │
    ├── components/                  # Presentational UI components
    │   ├── layout/
    │   │   ├── MenuBar.tsx
    │   │   ├── Toolbar.tsx
    │   │   ├── PanelLayout.tsx
    │   │   └── StatusBar.tsx
    │   ├── media/
    │   │   ├── MediaLibrary.tsx
    │   │   ├── MediaGrid.tsx
    │   │   ├── MediaList.tsx
    │   │   └── ClipCard.tsx
    │   ├── timeline/
    │   │   ├── Timeline.tsx
    │   │   ├── Track.tsx
    │   │   ├── ClipBlock.tsx
    │   │   ├── Playhead.tsx
    │   │   ├── Ruler.tsx
    │   │   └── BeatMarkers.tsx
    │   ├── preview/
    │   │   ├── PreviewWindow.tsx
    │   │   └── TransportControls.tsx
    │   ├── inspector/
    │   │   ├── Inspector.tsx
    │   │   ├── ClipProperties.tsx
    │   │   └── EffectControls.tsx
    │   ├── ai/
    │   │   ├── SuggestionsPanel.tsx
    │   │   ├── SuggestionCard.tsx
    │   │   └── ChatPanel.tsx
    │   ├── render/
    │   │   └── RenderQueue.tsx
    │   └── common/
    │       ├── Button.tsx
    │       ├── Modal.tsx
    │       └── ProgressBar.tsx
    │
    ├── modules/                     # Business logic (no UI)
    │   ├── timeline-engine/
    │   │   ├── TimelineEngine.ts
    │   │   ├── commands/
    │   │   ├── undo-redo/
    │   │   └── snap/
    │   ├── preview/
    │   │   └── PreviewController.ts
    │   └── project/
    │       └── ProjectManager.ts
    │
    ├── services/                    # External communication
    │   ├── api-client.ts
    │   ├── websocket-client.ts
    │   └── ipc-service.ts
    │
    ├── stores/                      # State management (Zustand)
    │   ├── project-store.ts
    │   ├── media-store.ts
    │   ├── timeline-store.ts
    │   ├── ai-store.ts
    │   └── ui-store.ts
    │
    ├── hooks/
    ├── utils/
    ├── styles/
    │   └── globals.css
    └── types/                       # Re-exports from shared-types
```

---

## `apps/backend/` — Python Backend

```
apps/backend/
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
│
├── montage_backend/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app entry
│   ├── config.py                    # Settings (pydantic-settings)
│   ├── logging.py                   # Structured logging setup
│   │
│   ├── api/
│   │   ├── router.py                # Aggregate routes
│   │   ├── deps.py                  # Dependency injection
│   │   ├── middleware.py
│   │   └── routes/
│   │       ├── health.py
│   │       ├── projects.py
│   │       ├── media.py
│   │       ├── timeline.py
│   │       ├── analysis.py
│   │       ├── render.py
│   │       ├── ai_chat.py
│   │       └── settings.py
│   │
│   ├── services/
│   │   ├── project_service.py
│   │   ├── media_service.py
│   │   ├── timeline_service.py
│   │   ├── analysis_service.py
│   │   ├── render_service.py
│   │   ├── audio_service.py
│   │   └── thumbnail_service.py
│   │
│   ├── repositories/
│   │   ├── base.py
│   │   ├── project_repo.py
│   │   ├── media_repo.py
│   │   ├── analysis_repo.py
│   │   ├── timeline_repo.py
│   │   └── render_repo.py
│   │
│   ├── models/                      # Pydantic models + DB ORM
│   │   ├── domain/
│   │   └── db/
│   │
│   ├── jobs/
│   │   ├── queue.py                 # Async job queue
│   │   ├── worker.py
│   │   └── handlers/
│   │       ├── analyze_clip.py
│   │       ├── analyze_music.py
│   │       ├── generate_timeline.py
│   │       └── render_export.py
│   │
│   ├── media/
│   │   ├── ffmpeg_wrapper.py
│   │   ├── proxy_generator.py
│   │   ├── thumbnail_generator.py
│   │   └── probe.py                 # FFprobe metadata
│   │
│   ├── render/
│   │   ├── pipeline.py
│   │   ├── graph_builder.py
│   │   └── presets.py
│   │
│   └── ws/
│       └── events.py                # WebSocket event handlers
│
└── tests/
    ├── unit/
    ├── integration/
    └── conftest.py
```

---

## `ai/` — AI Components

```
ai/
├── models/
│   ├── README.md                    # Model inventory + download instructions
│   └── .gitkeep
│
├── agents/
│   ├── __init__.py
│   ├── base.py                      # BaseAgent, AgentResult protocol
│   ├── orchestrator.py              # AIEngine orchestrator
│   ├── clip_analyzer.py
│   ├── music_analyzer.py
│   ├── style_analyzer.py
│   ├── timeline_planner.py
│   ├── editing_agent.py
│   ├── audio_agent.py
│   ├── thumbnail_agent.py
│   └── chat_assistant.py
│
├── plugins/
│   └── albion/
│       ├── __init__.py
│       ├── analyzer.py              # AlbionEventAnalyzer
│       ├── detectors/
│       │   ├── bomb_detector.py
│       │   ├── wipe_detector.py
│       │   ├── loot_detector.py
│       │   ├── engagement_detector.py
│       │   └── kill_feed_detector.py
│       ├── templates/               # UI region templates for OCR
│       └── config.yaml              # Thresholds, regions
│
├── inference/
│   ├── torch_runner.py
│   ├── onnx_runner.py
│   └── model_registry.py
│
└── training/
    └── README.md                    # Future fine-tuning docs
```

---

## `packages/shared-types/`

```
packages/shared-types/
├── package.json
├── schemas/
│   ├── timeline.schema.json
│   ├── media.schema.json
│   ├── analysis.schema.json
│   ├── ai-suggestion.schema.json
│   ├── project.schema.json
│   └── events.schema.json           # WebSocket event schemas
├── src/
│   └── index.ts                     # Generated TS types
├── python/
│   └── montage_types/               # Generated Pydantic models
└── scripts/
    └── codegen.ts
```

---

## `docs/`

```
docs/
├── README.md
├── product-vision.md
├── requirements.md
├── 01-prd.md … 20-definition-of-done.md
├── ui-ux-design.md
└── development-guide.md
```

---

## `tests/`

```
tests/
├── e2e/
│   ├── playwright.config.ts
│   ├── import-analyze-export.spec.ts
│   └── timeline-editing.spec.ts
├── integration/
│   ├── backend-api.test.ts
│   └── timeline-sync.test.ts
└── fixtures/
    ├── sample-project/
    └── factories/
```

---

## Naming Conventions

| Context | Convention | Example |
|---------|------------|---------|
| React components | PascalCase | `Timeline.tsx` |
| TS modules/hooks | camelCase | `useTimeline.ts` |
| Python modules | snake_case | `clip_analyzer.py` |
| Python classes | PascalCase | `ClipAnalyzerAgent` |
| API routes | kebab-case | `/api/v1/media-items` |
| DB tables | snake_case | `clip_analysis` |
| JSON fields | snake_case | `excitement_score` |
| Env vars | SCREAMING_SNAKE | `MONTAGE_AI_MODEL_PATH` |

---

## Files Explicitly Gitignored

```
node_modules/
dist/
out/
*.pyc
__pycache__/
.venv/
ai/models/*.onnx
ai/models/*.pt
assets/test-media/*.mp4
*.db
projects/
.env
logs/
.cache/
```
