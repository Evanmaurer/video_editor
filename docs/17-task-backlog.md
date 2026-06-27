# Task Backlog

**Product:** MontageAI  
**Version:** 1.1  
**Date:** 2026-06-27 (revised milestone plan)

Tasks are organized by milestone. Priority: P0 (must have), P1 (should have), P2 (nice to have).

**Workflow:** Within Milestone 2, complete each sub-milestone (M2-001 → M2-006) fully before starting the next. At each milestone completion, update PROJECT_STATE.md and wait for approval.

---

## Milestone 0: Design ✓

| ID | Task | Priority | Status |
|----|------|----------|--------|
| M0-001 | Write Product Requirements Document | P0 | Done |
| M0-002 | Write Software Architecture Document | P0 | Done |
| M0-003–M0-021 | Remaining design documents + PROJECT_STATE | P0 | Done |
| M0-022 | Architecture review and approval | P0 | Done |

---

## Milestone 1: Application Shell ✓

All M1 tasks complete. See git tag `milestone-1`.

---

## Milestone 2: Media Processing Engine

### M2-001 — Media Processing Engine

| ID | Task | Priority | Estimate |
|----|------|----------|----------|
| M2.1-001 | Implement FFmpeg wrapper (probe, transcode, extract) | P0 | 8h |
| M2.1-002 | Implement MediaService.import_files | P0 | 6h |
| M2.1-003 | Implement proxy generator (720p H.264) | P0 | 4h |
| M2.1-004 | Implement waveform generator | P0 | 4h |
| M2.1-005 | Implement thumbnail generator | P0 | 3h |
| M2.1-006 | Implement media repository (CRUD + queries) | P0 | 4h |
| M2.1-007 | Alembic migrations for media_items table | P0 | 2h |
| M2.1-008 | Implement job queue (asyncio) | P0 | 8h |
| M2.1-009 | Implement job handlers (proxy, waveform, thumbnail) | P0 | 6h |
| M2.1-010 | WebSocket event broadcasting for job progress | P0 | 4h |
| M2.1-011 | Unit tests: FFmpeg wrapper + MediaService | P0 | 8h |
| M2.1-012 | Integration test: import → proxy → waveform | P0 | 4h |
| M2.1-013 | Update docs + PROJECT_STATE.md | P0 | 1h |

### M2-002 — Media Library

| ID | Task | Priority | Estimate |
|----|------|----------|----------|
| M2.2-001 | Build MediaLibrary grid view | P0 | 6h |
| M2.2-002 | Build MediaLibrary list view | P1 | 3h |
| M2.2-003 | Build ClipCard component | P0 | 3h |
| M2.2-004 | File import dialog (IPC + API) + drag-drop | P0 | 4h |
| M2.2-005 | Import progress UI | P0 | 3h |
| M2.2-006 | Duplicate detection | P1 | 2h |
| M2.2-007 | Media delete | P1 | 2h |
| M2.2-008 | E2E/integration test: import folder → see clips | P0 | 4h |
| M2.2-009 | Update docs + PROJECT_STATE.md | P0 | 1h |

### M2-003 — Timeline Engine

| ID | Task | Priority | Estimate |
|----|------|----------|----------|
| M2.3-001 | Define timeline JSON Schema | P0 | 4h |
| M2.3-002 | Implement TimelineEngine (commands, undo/redo) | P0 | 16h |
| M2.3-003 | Implement snap engine | P1 | 4h |
| M2.3-004 | Implement TimelineService (backend) | P0 | 6h |
| M2.3-005 | Build Timeline UI (multi-track, ruler, playhead) | P0 | 16h |
| M2.3-006 | Clip drag-drop, trim, split, move | P0 | 12h |
| M2.3-007 | Inspector panel (clip properties) | P0 | 6h |
| M2.3-008 | Auto-save (debounced) | P0 | 3h |
| M2.3-009 | Keyboard shortcuts | P1 | 4h |
| M2.3-010 | Unit tests: TimelineEngine commands | P0 | 8h |
| M2.3-011 | Update docs + PROJECT_STATE.md | P0 | 1h |

### M2-004 — Playback Engine

| ID | Task | Priority | Estimate |
|----|------|----------|----------|
| M2.4-001 | PreviewController + PreviewWindow | P0 | 8h |
| M2.4-002 | Transport controls | P0 | 3h |
| M2.4-003 | Proxy-based sequential playback | P0 | 8h |
| M2.4-004 | Audio playback sync | P0 | 6h |
| M2.4-005 | Scrubbing / seek | P1 | 4h |
| M2.4-006 | Unit/integration tests | P0 | 4h |
| M2.4-007 | Update docs + PROJECT_STATE.md | P0 | 1h |

### M2-005 — Export Engine

| ID | Task | Priority | Estimate |
|----|------|----------|----------|
| M2.5-001 | RenderGraphBuilder | P0 | 10h |
| M2.5-002 | FFmpeg render pipeline + job handler | P0 | 8h |
| M2.5-003 | Export presets (H.264 1080p60) | P0 | 2h |
| M2.5-004 | Render progress parsing + WebSocket | P0 | 4h |
| M2.5-005 | Render Queue UI | P0 | 6h |
| M2.5-006 | Basic audio mixing | P1 | 6h |
| M2.5-007 | Unit tests: RenderGraphBuilder | P0 | 6h |
| M2.5-008 | Integration test: export 3-min montage | P0 | 4h |
| M2.5-009 | Update docs + PROJECT_STATE.md | P0 | 1h |

### M2-006 — AI Metadata Engine

| ID | Task | Priority | Estimate |
|----|------|----------|----------|
| M2.6-001 | AI metadata schema (confidence, reasoning, tags) | P0 | 4h |
| M2.6-002 | Metadata cache storage (SQLite) + repository | P0 | 6h |
| M2.6-003 | API to read/write metadata on media items | P0 | 4h |
| M2.6-004 | UI hooks to display metadata on clips | P1 | 4h |
| M2.6-005 | Metadata invalidation on re-import | P0 | 2h |
| M2.6-006 | Unit + integration tests | P0 | 4h |
| M2.6-007 | Milestone 2 summary + PROJECT_STATE.md | P0 | 2h |

**M2 total estimate:** ~200 hours (~5 weeks)

---

## Milestone 3: AI Analysis Pipeline

| ID | Task | Priority | Estimate |
|----|------|----------|----------|
| M3-001 | BaseAgent interface + orchestrator | P0 | 6h |
| M3-002 | Model registry (load/unload) | P0 | 4h |
| M3-003 | Frame extractor (PyAV) | P0 | 4h |
| M3-004 | Clip analysis agent | P0 | 16h |
| M3-005 | Scene understanding | P0 | 8h |
| M3-006 | Motion analysis | P0 | 6h |
| M3-007 | OCR integration (EasyOCR) | P0 | 4h |
| M3-008 | Object detection | P0 | 8h |
| M3-009 | Audio analysis | P0 | 6h |
| M3-010 | CLIP embeddings + semantic indexing | P0 | 10h |
| M3-011 | Analysis job handlers + progress UI | P0 | 6h |
| M3-012 | Clip scores/tags in media library | P0 | 4h |
| M3-013 | Validation test set + metrics | P0 | 8h |
| M3-014 | Unit + integration tests | P0 | 10h |
| M3-015 | Milestone summary + PROJECT_STATE.md | P0 | 2h |

**M3 total estimate:** ~102 hours

---

## Milestone 4: AI Montage Generation

| ID | Task | Priority | Estimate |
|----|------|----------|----------|
| M4-001 | Music Analyzer (BPM, beats, drops) | P0 | 10h |
| M4-002 | Style Analyzer (reference montage profiling) | P0 | 10h |
| M4-003 | Highlight selection algorithm | P0 | 8h |
| M4-004 | Beat-sync placement + pacing engine | P0 | 10h |
| M4-005 | Transition + effects selection | P0 | 8h |
| M4-006 | Camera shake detection | P1 | 4h |
| M4-007 | Timeline Planner agent | P0 | 16h |
| M4-008 | "Generate Timeline" API + UI workflow | P0 | 8h |
| M4-009 | AI Suggestions panel (accept/reject) | P0 | 6h |
| M4-010 | Integration test: analyze → generate | P0 | 4h |
| M4-011 | Milestone summary + PROJECT_STATE.md | P0 | 2h |

**M4 total estimate:** ~86 hours

---

## Milestone 5: Albion Online Intelligence

| ID | Task | Priority | Estimate |
|----|------|----------|----------|
| M5-001 | Albion analyzer plugin scaffold | P0 | 4h |
| M5-002 | Albion-specific OCR | P0 | 6h |
| M5-003 | BombDetector | P0 | 8h |
| M5-004 | KillFeedDetector | P0 | 6h |
| M5-005 | Cooldown recognition | P0 | 6h |
| M5-006 | Party status detection | P0 | 4h |
| M5-007 | Player recognition | P1 | 6h |
| M5-008 | Battle timeline extraction | P0 | 8h |
| M5-009 | Guild metadata extraction | P1 | 4h |
| M5-010 | Engagement scoring | P0 | 4h |
| M5-011 | UI template system + calibration wizard | P0 | 8h |
| M5-012 | Event badges + filters in media library | P0 | 4h |
| M5-013 | Validation test set (30+ labeled clips) | P0 | 8h |
| M5-014 | Unit + integration tests | P0 | 8h |
| M5-015 | Milestone summary + PROJECT_STATE.md | P0 | 2h |

**M5 total estimate:** ~86 hours

---

## Milestone 6: AI Assistant

| ID | Task | Priority | Estimate |
|----|------|----------|----------|
| M6-001 | Chat panel UI | P0 | 6h |
| M6-002 | Chat Assistant agent + LLM integration | P0 | 10h |
| M6-003 | Project context injection | P0 | 4h |
| M6-004 | NL command parser | P0 | 8h |
| M6-005 | Editing Agent (timeline modifications) | P0 | 8h |
| M6-006 | Suggestion flow with confidence/reasoning | P0 | 4h |
| M6-007 | Generate montage from NL instructions | P0 | 10h |
| M6-008 | Unit + integration tests | P0 | 6h |
| M6-009 | E2E test: chat-driven edit | P0 | 4h |
| M6-010 | Milestone summary + PROJECT_STATE.md | P0 | 2h |

**M6 total estimate:** ~62 hours

---

## Milestone 7: Polish & Production

| ID | Task | Priority | Estimate |
|----|------|----------|----------|
| M7-001 | Performance profiling + optimization | P0 | 12h |
| M7-002 | Error handling polish | P0 | 8h |
| M7-003 | Complete E2E test suite | P0 | 12h |
| M7-004 | electron-builder (macOS + Windows) | P0 | 8h |
| M7-005 | PyInstaller backend bundling | P0 | 6h |
| M7-006 | Auto-updater | P1 | 6h |
| M7-007 | Crash reporting | P0 | 4h |
| M7-008 | User documentation | P0 | 8h |
| M7-009 | Beta program + feedback | P0 | 8h |
| M7-010 | Bug fixes from beta | P0 | 20h |
| M7-011 | v1.0 release + tag | P0 | 4h |
| M7-012 | Milestone summary + PROJECT_STATE.md | P0 | 2h |

**M7 total estimate:** ~98 hours

---

## Backlog Summary

| Milestone | Status | Estimated Hours |
|-----------|--------|-----------------|
| M0 | Complete | 40 |
| M1 | Complete | 75 |
| M2 (6 sub-milestones) | Not started | ~200 |
| M3 | Not started | ~102 |
| M4 | Not started | ~86 |
| M5 | Not started | ~86 |
| M6 | Not started | ~62 |
| M7 | Not started | ~98 |
| **Remaining** | | **~634 hours** |

**Estimated calendar time (remaining):** 30–38 weeks (1–2 engineers)

---

## Icebox (Post-v1.0)

| ID | Task | Priority |
|----|------|----------|
| ICE-001 | Second game plugin framework | P2 |
| ICE-002 | Full-res preview via frame server | P2 |
| ICE-003 | Hardware render acceleration | P2 |
| ICE-004 | Batch project processing | P2 |
| ICE-005 | Motion graphics engine | P3 |
| ICE-006 | Cloud collaboration | P3 |
