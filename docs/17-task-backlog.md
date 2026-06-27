# Task Backlog

**Product:** MontageAI  
**Version:** 1.0  
**Date:** 2026-06-26

Tasks are organized by milestone. Priority: P0 (must have), P1 (should have), P2 (nice to have).

---

## Milestone 0: Design ✦

| ID | Task | Priority | Status |
|----|------|----------|--------|
| M0-001 | Write Product Requirements Document | P0 | Done |
| M0-002 | Write Software Architecture Document | P0 | Done |
| M0-003 | Define folder structure | P0 | Done |
| M0-004 | Design database schema | P0 | Done |
| M0-005 | Write frontend architecture | P0 | Done |
| M0-006 | Write backend architecture | P0 | Done |
| M0-007 | Design AI agents | P0 | Done |
| M0-008 | Design timeline engine | P0 | Done |
| M0-009 | Design rendering pipeline | P0 | Done |
| M0-010 | Create UI wireframes | P0 | Done |
| M0-011 | Create sequence diagrams | P0 | Done |
| M0-012 | Design API | P0 | Done |
| M0-013 | Document technology decisions | P0 | Done |
| M0-014 | Write risk analysis | P0 | Done |
| M0-015 | Create development roadmap | P0 | Done |
| M0-016 | Break down milestones | P0 | Done |
| M0-017 | Create task backlog | P0 | Done |
| M0-018 | Write coding standards | P0 | Done |
| M0-019 | Write testing strategy | P0 | Done |
| M0-020 | Define definition of done | P0 | Done |
| M0-021 | Create PROJECT_STATE.md | P0 | Done |
| M0-022 | Architecture review and approval | P0 | Pending |

---

## Milestone 1: Application Shell

| ID | Task | Priority | Estimate |
|----|------|----------|----------|
| M1-001 | Initialize monorepo (pnpm workspaces, root config) | P0 | 2h |
| M1-002 | Scaffold Electron app (electron-vite + React + TS) | P0 | 4h |
| M1-003 | Configure TailwindCSS dark theme tokens | P0 | 2h |
| M1-004 | Scaffold Python backend (FastAPI + Uvicorn) | P0 | 3h |
| M1-005 | Implement backend spawn + health check in Electron main | P0 | 4h |
| M1-006 | Implement auth token generation + middleware | P0 | 2h |
| M1-007 | Create preload bridge (IPC API) | P0 | 3h |
| M1-008 | Create API client (typed HTTP) | P0 | 3h |
| M1-009 | Create WebSocket client | P0 | 2h |
| M1-010 | Implement ProjectService (create/open/save/close) | P0 | 6h |
| M1-011 | Implement project repository + SQLite setup | P0 | 4h |
| M1-012 | Create Alembic migration for projects table | P0 | 2h |
| M1-013 | Build Welcome screen UI | P0 | 4h |
| M1-014 | Build New Project wizard (3 steps) | P0 | 6h |
| M1-015 | Build panel layout shell (react-resizable-panels) | P0 | 4h |
| M1-016 | Build menu bar (File, Edit, View, Help) | P0 | 3h |
| M1-017 | Build status bar | P1 | 2h |
| M1-018 | Build settings panel (basic) | P1 | 4h |
| M1-019 | Scaffold shared-types package + JSON Schema | P0 | 4h |
| M1-020 | Setup structured logging (structlog + frontend) | P0 | 3h |
| M1-021 | Setup ESLint + Prettier + Ruff + mypy | P0 | 2h |
| M1-022 | Unit tests: ProjectService | P0 | 4h |
| M1-023 | Integration test: project create/open cycle | P0 | 3h |
| M1-024 | Update PROJECT_STATE.md | P0 | 1h |

**M1 Total Estimate:** ~75 hours (~2 weeks)

---

## Milestone 2: Media Pipeline

| ID | Task | Priority | Estimate |
|----|------|----------|----------|
| M2-001 | Implement FFmpeg wrapper (probe, transcode, extract) | P0 | 8h |
| M2-002 | Implement MediaService.import_files | P0 | 6h |
| M2-003 | Implement proxy generator (720p H.264) | P0 | 4h |
| M2-004 | Implement thumbnail generator | P0 | 3h |
| M2-005 | Implement media repository (CRUD + queries) | P0 | 4h |
| M2-006 | Create Alembic migration for media_items table | P0 | 2h |
| M2-007 | Implement job queue (asyncio) | P0 | 8h |
| M2-008 | Implement job handlers (proxy, thumbnail) | P0 | 4h |
| M2-009 | Implement WebSocket event broadcasting | P0 | 4h |
| M2-010 | Build MediaLibrary component (grid view) | P0 | 6h |
| M2-011 | Build MediaLibrary list view | P1 | 3h |
| M2-012 | Build ClipCard component | P0 | 3h |
| M2-013 | Implement file import dialog (IPC + API) | P0 | 4h |
| M2-014 | Build import progress UI | P0 | 3h |
| M2-015 | Implement duplicate detection | P1 | 2h |
| M2-016 | Implement media delete | P1 | 2h |
| M2-017 | Unit tests: FFmpeg wrapper | P0 | 4h |
| M2-018 | Unit tests: MediaService | P0 | 4h |
| M2-019 | Integration test: import → proxy → thumbnail | P0 | 4h |
| M2-020 | E2E test: import folder → see clips | P0 | 4h |
| M2-021 | Update PROJECT_STATE.md | P0 | 1h |

**M2 Total Estimate:** ~85 hours (~2 weeks)

---

## Milestone 3: Clip & Albion Analysis

| ID | Task | Priority | Estimate |
|----|------|----------|----------|
| M3-001 | Implement BaseAgent interface + AIEngine orchestrator | P0 | 6h |
| M3-002 | Implement model registry (load/unload) | P0 | 4h |
| M3-003 | Implement frame extractor (PyAV) | P0 | 4h |
| M3-004 | Implement Clip Analyzer agent | P0 | 16h |
| M3-005 | Implement scene detection (histogram + CLIP) | P0 | 8h |
| M3-006 | Implement motion analysis (optical flow) | P0 | 6h |
| M3-007 | Implement OCR integration (EasyOCR) | P0 | 4h |
| M3-008 | Implement excitement scoring | P0 | 4h |
| M3-009 | Implement Albion analyzer plugin scaffold | P0 | 4h |
| M3-010 | Implement BombDetector | P0 | 8h |
| M3-011 | Implement KillFeedDetector | P0 | 6h |
| M3-012 | Implement EngagementDetector | P0 | 4h |
| M3-013 | Implement WipeDetector | P0 | 4h |
| M3-014 | Implement LootDetector | P1 | 4h |
| M3-015 | Create Albion UI template config | P0 | 3h |
| M3-016 | Implement analysis job handlers | P0 | 4h |
| M3-017 | Implement analysis repositories | P0 | 4h |
| M3-018 | Create Alembic migrations (clip_analysis, game_events) | P0 | 2h |
| M3-019 | Build analysis progress overlay UI | P0 | 4h |
| M3-020 | Update ClipCard with scores and event badges | P0 | 4h |
| M3-021 | Build clip detail view | P0 | 6h |
| M3-022 | Implement filter/sort by score and event type | P0 | 4h |
| M3-023 | Build AI suggestion card component | P1 | 4h |
| M3-024 | Create validation test set (30+ labeled clips) | P0 | 8h |
| M3-025 | Unit tests: Clip Analyzer | P0 | 6h |
| M3-026 | Unit tests: Albion detectors | P0 | 6h |
| M3-027 | Integration test: analyze clip → store results | P0 | 4h |
| M3-028 | Update PROJECT_STATE.md | P0 | 1h |

**M3 Total Estimate:** ~140 hours (~3.5 weeks)

---

## Milestone 4: Music & Style Analysis

| ID | Task | Priority | Estimate |
|----|------|----------|----------|
| M4-001 | Implement Music Analyzer agent | P0 | 10h |
| M4-002 | Implement Style Analyzer agent | P0 | 10h |
| M4-003 | Implement music/style repositories | P0 | 4h |
| M4-004 | Create Alembic migrations (music_analysis, style_profiles) | P0 | 2h |
| M4-005 | Build music analysis display UI | P0 | 4h |
| M4-006 | Build beat markers on timeline ruler | P1 | 4h |
| M4-007 | Build style profile display | P1 | 3h |
| M4-008 | Unit tests: Music Analyzer | P0 | 4h |
| M4-009 | Unit tests: Style Analyzer | P0 | 4h |
| M4-010 | Update PROJECT_STATE.md | P0 | 1h |

**M4 Total Estimate:** ~46 hours (~1 week)

---

## Milestone 5: Timeline Engine

| ID | Task | Priority | Estimate |
|----|------|----------|----------|
| M5-001 | Define timeline JSON Schema | P0 | 4h |
| M5-002 | Implement TimelineEngine (core) | P0 | 12h |
| M5-003 | Implement command pattern (all commands) | P0 | 10h |
| M5-004 | Implement undo/redo stack | P0 | 4h |
| M5-005 | Implement snap engine | P1 | 4h |
| M5-006 | Implement timeline validation | P0 | 3h |
| M5-007 | Implement TimelineService (backend) | P0 | 6h |
| M5-008 | Build Timeline component (multi-track) | P0 | 12h |
| M5-009 | Build Track + ClipBlock components | P0 | 8h |
| M5-010 | Build Playhead + Ruler components | P0 | 4h |
| M5-011 | Implement clip drag-drop | P0 | 6h |
| M5-012 | Implement trim handles | P0 | 6h |
| M5-013 | Implement split at playhead | P0 | 3h |
| M5-014 | Build PreviewController + PreviewWindow | P0 | 8h |
| M5-015 | Build TransportControls | P0 | 3h |
| M5-016 | Build Inspector panel (clip properties) | P0 | 6h |
| M5-017 | Implement auto-save (debounced) | P0 | 3h |
| M5-018 | Implement keyboard shortcuts | P1 | 4h |
| M5-019 | Unit tests: TimelineEngine commands | P0 | 8h |
| M5-020 | Unit tests: snap engine | P1 | 3h |
| M5-021 | Integration test: create/edit/save timeline | P0 | 4h |
| M5-022 | Update PROJECT_STATE.md | P0 | 1h |

**M5 Total Estimate:** ~120 hours (~3 weeks)

---

## Milestone 6: AI Timeline Generation

| ID | Task | Priority | Estimate |
|----|------|----------|----------|
| M6-001 | Implement Timeline Planner agent | P0 | 16h |
| M6-002 | Implement clip selection algorithm | P0 | 6h |
| M6-003 | Implement beat-sync placement | P0 | 6h |
| M6-004 | Implement style profile application | P0 | 4h |
| M6-005 | Implement "Generate Timeline" API endpoint | P0 | 4h |
| M6-006 | Build "Generate Timeline" UI workflow | P0 | 4h |
| M6-007 | Build AI Suggestions panel | P0 | 6h |
| M6-008 | Implement accept/reject suggestion flow | P0 | 6h |
| M6-009 | Display AI metadata on timeline clips | P0 | 3h |
| M6-010 | Unit tests: Timeline Planner | P0 | 6h |
| M6-011 | Integration test: analyze → generate → verify | P0 | 4h |
| M6-012 | Update PROJECT_STATE.md | P0 | 1h |

**M6 Total Estimate:** ~66 hours (~1.5 weeks)

---

## Milestone 7: Export & AI Chat

| ID | Task | Priority | Estimate |
|----|------|----------|----------|
| M7-001 | Implement RenderGraphBuilder | P0 | 10h |
| M7-002 | Implement effect/transition compilers | P0 | 8h |
| M7-003 | Implement RenderService + job handler | P0 | 6h |
| M7-004 | Implement render progress parsing | P0 | 3h |
| M7-005 | Implement export presets | P0 | 2h |
| M7-006 | Build Render Queue UI | P0 | 6h |
| M7-007 | Implement Chat Assistant agent | P1 | 10h |
| M7-008 | Implement rule-based NL parser | P1 | 8h |
| M7-009 | Implement Editing Agent | P1 | 6h |
| M7-010 | Build Chat Panel UI | P1 | 6h |
| M7-011 | Implement Audio Agent (basic mixing) | P1 | 8h |
| M7-012 | Unit tests: RenderGraphBuilder | P0 | 6h |
| M7-013 | Unit tests: NL parser | P1 | 4h |
| M7-014 | E2E test: full workflow | P0 | 8h |
| M7-015 | Update PROJECT_STATE.md | P0 | 1h |

**M7 Total Estimate:** ~92 hours (~2.5 weeks)

---

## Milestone 8: Beta & Release

| ID | Task | Priority | Estimate |
|----|------|----------|----------|
| M8-001 | Implement Thumbnail Agent | P2 | 8h |
| M8-002 | Performance profiling + optimization | P0 | 12h |
| M8-003 | Error handling polish (all modules) | P0 | 8h |
| M8-004 | Complete E2E test suite | P0 | 12h |
| M8-005 | Setup electron-builder (macOS + Windows) | P0 | 8h |
| M8-006 | PyInstaller backend bundling | P0 | 6h |
| M8-007 | Model download UI | P1 | 4h |
| M8-008 | Beta distribution setup | P0 | 4h |
| M8-009 | User documentation | P1 | 8h |
| M8-010 | Beta feedback collection | P0 | 4h |
| M8-011 | Bug fixes from beta | P0 | 20h |
| M8-012 | v1.0 release | P0 | 4h |
| M8-013 | Update PROJECT_STATE.md | P0 | 1h |

**M8 Total Estimate:** ~99 hours (~2.5 weeks)

---

## Backlog Summary

| Milestone | Tasks | Estimated Hours |
|-----------|-------|-----------------|
| M0 | 22 | 40 (design) |
| M1 | 24 | 75 |
| M2 | 21 | 85 |
| M3 | 28 | 140 |
| M4 | 10 | 46 |
| M5 | 22 | 120 |
| M6 | 12 | 66 |
| M7 | 15 | 92 |
| M8 | 13 | 99 |
| **Total** | **167** | **~763 hours** |

**Estimated calendar time:** 33-40 weeks (1-2 engineers)

---

## Icebox (Post-v1.0)

| ID | Task | Priority |
|----|------|----------|
| ICE-001 | Second game plugin framework | P2 |
| ICE-002 | Full-res preview via frame server | P2 |
| ICE-003 | Hardware render acceleration | P2 |
| ICE-004 | Cloud LLM integration (OpenAI/Anthropic) | P2 |
| ICE-005 | Batch project processing | P2 |
| ICE-006 | Template system for montage styles | P2 |
| ICE-007 | Auto-updater | P2 |
| ICE-008 | EDL/XML export | P2 |
| ICE-009 | Motion graphics engine | P3 |
| ICE-010 | Cloud collaboration | P3 |
