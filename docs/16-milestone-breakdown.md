# Milestone Breakdown

**Product:** MontageAI  
**Version:** 1.1  
**Date:** 2026-06-27 (revised milestone plan)

---

## Milestone Workflow

### Sub-milestone rules (Milestone 2)

Milestone 2 is implemented as six sequential sub-milestones. **Do not begin the next sub-milestone until the current one is complete, tested, documented, and committed.**

| Sub-milestone | Name |
|---------------|------|
| M2-001 | Media Processing Engine |
| M2-002 | Media Library |
| M2-003 | Timeline Engine |
| M2-004 | Playback Engine |
| M2-005 | Export Engine |
| M2-006 | AI Metadata Engine |

### Milestone completion rules (all milestones)

At the completion of each milestone (M2–M7):

1. Stop implementation work
2. Summarize work completed
3. Update `PROJECT_STATE.md`
4. **Wait for stakeholder approval** before proceeding to the next milestone

---

## Milestone 0: Design Package ✓

**Duration:** 2 weeks  
**Goal:** Complete software design documentation; no code.  
**Status:** Complete (2026-06-26)

---

## Milestone 1: Application Shell ✓

**Duration:** 3 weeks  
**Goal:** Electron app launches with professional dark UI; Python backend connects; project CRUD works.  
**Status:** Complete (2026-06-27, tag `milestone-1`)

### Exit Criteria
- [x] App launches on macOS in < 5s
- [x] Backend health check passes
- [x] Create project → folder structure created → reopen project works
- [x] All panels render (empty state)
- [x] Unit + integration tests for project service and API
- [x] PROJECT_STATE.md updated

---

## Milestone 2: Media Processing Engine

**Duration:** 8–12 weeks (six sub-milestones)  
**Goal:** Full media processing backend, library UI, timeline, playback, export, and AI metadata cache — the core editing engine before AI analysis.

Milestone 2 is **not** complete until all six sub-milestones (M2-001 through M2-006) are done.

---

### M2-001 — Media Processing Engine

**Goal:** Backend media processing infrastructure.

| Deliverable | Priority |
|-------------|----------|
| FFmpeg wrapper (probe, transcode, extract) | P0 |
| Media import (files/folders) | P0 |
| Metadata extraction (FFprobe) | P0 |
| Proxy generation (720p H.264) | P0 |
| Waveform generation | P0 |
| Thumbnail generation | P0 |
| Background job queue | P0 |
| WebSocket progress events | P0 |
| SQLite media repository | P0 |
| Alembic migrations for media tables | P0 |

**Exit criteria:**
- Import 100 clips; metadata extracted in < 60s
- Proxies and waveforms generated in background with progress
- Unit + integration tests for FFmpeg wrapper and MediaService
- Documented, committed; approval to proceed to M2-002

---

### M2-002 — Media Library

**Goal:** Frontend media library with real imported data.

| Deliverable | Priority |
|-------------|----------|
| Media library grid view | P0 |
| Media library list view | P1 |
| ClipCard with metadata display | P0 |
| File import dialog (drag-drop + IPC + API) | P0 |
| Import progress UI | P0 |
| Duplicate file detection | P1 |
| Media item delete | P1 |

**Exit criteria:**
- Import folder → clips visible in library with thumbnails and metadata
- E2E or integration test: import → see clips in library
- Documented, committed; approval to proceed to M2-003

---

### M2-003 — Timeline Engine

**Goal:** Multi-track timeline document, editing commands, and UI.

| Deliverable | Priority |
|-------------|----------|
| Timeline JSON schema + validation | P0 |
| Timeline Engine (commands, undo/redo) | P0 |
| Multi-track timeline UI | P0 |
| Clip drag-drop onto timeline | P0 |
| Trim, split, move clips | P0 |
| Playhead + ruler | P0 |
| Snap to beats (when beat data available) | P1 |
| Auto-save (debounced) | P0 |
| Inspector panel (clip properties) | P0 |
| Keyboard shortcuts | P1 |

**Exit criteria:**
- Manual timeline editing with 50+ clips
- Undo/redo for all operations
- Timeline persists across app restart
- Unit tests for Timeline Engine commands
- Documented, committed; approval to proceed to M2-004

---

### M2-004 — Playback Engine

**Goal:** Preview playback of timeline using proxy media.

| Deliverable | Priority |
|-------------|----------|
| PreviewController + PreviewWindow | P0 |
| Transport controls (play/pause/seek) | P0 |
| Proxy-based sequential playback | P0 |
| Audio playback sync | P0 |
| Scrubbing and frame-accurate seek | P1 |

**Exit criteria:**
- Preview plays proxy clips in timeline sequence
- Transport controls respond correctly
- Unit/integration tests for playback controller
- Documented, committed; approval to proceed to M2-005

---

### M2-005 — Export Engine

**Goal:** Render timeline to video file via FFmpeg.

| Deliverable | Priority |
|-------------|----------|
| Render graph builder | P0 |
| FFmpeg render pipeline | P0 |
| Export presets (H.264 1080p60) | P0 |
| Render queue + job handler | P0 |
| Render progress (WebSocket) | P0 |
| Render Queue UI | P0 |
| Basic audio mixing | P1 |

**Exit criteria:**
- Export 3-min 1080p60 montage successfully
- Render progress shown in real time
- Unit tests for render graph builder
- Documented, committed; approval to proceed to M2-006

---

### M2-006 — AI Metadata Engine

**Goal:** Cache layer for AI-derived metadata attached to media and timeline elements (structure only — no analysis agents yet).

| Deliverable | Priority |
|-------------|----------|
| AI metadata schema (confidence, reasoning, tags) | P0 |
| Metadata cache storage (SQLite) | P0 |
| API to read/write cached metadata on media items | P0 |
| UI hooks to display cached metadata on clips | P1 |
| Metadata invalidation on re-import/re-analyze | P0 |

**Exit criteria:**
- Metadata can be stored and retrieved for media items
- Timeline clips can reference cached AI metadata
- Unit + integration tests for metadata cache
- PROJECT_STATE.md updated; **Milestone 2 complete — await approval before M3**

---

## Milestone 3: AI Analysis Pipeline

**Duration:** 4–6 weeks  
**Goal:** Analyze clips with computer vision and audio — no montage generation yet.

| Deliverable | Priority |
|-------------|----------|
| Clip analysis agent | P0 |
| OCR integration | P0 |
| Object detection | P0 |
| Scene understanding | P0 |
| Motion analysis | P0 |
| Audio analysis | P0 |
| CLIP embeddings | P0 |
| Semantic indexing | P0 |
| Analysis job handlers + progress UI | P0 |
| Clip scores and tags in media library | P0 |

**Exit criteria:**
- 100 clips analyzed with scores and semantic index
- Analysis results stored in AI metadata cache (M2-006)
- Validation metrics documented per agent
- PROJECT_STATE.md updated; await approval before M4

---

## Milestone 4: AI Montage Generation

**Duration:** 3–5 weeks  
**Goal:** Automatically generate editable montages from analyzed clips and music.

| Deliverable | Priority |
|-------------|----------|
| Automatic highlight selection | P0 |
| Music synchronization | P0 |
| Beat detection | P0 |
| Pacing engine | P0 |
| Transition selection | P0 |
| Effects application | P0 |
| Camera shake detection | P1 |
| Montage generation workflow ("Generate Timeline") | P0 |
| AI suggestions panel (accept/reject) | P0 |

**Exit criteria:**
- Generate timeline from 100 analyzed clips in < 2 min
- Cuts aligned to beat map; transitions applied
- Generated timeline fully editable with undo/redo
- Integration test: analyze → generate → verify structure
- PROJECT_STATE.md updated; await approval before M5

---

## Milestone 5: Albion Online Intelligence

**Duration:** 4–5 weeks  
**Goal:** Game-specific detection and scoring for Albion Online.

| Deliverable | Priority |
|-------------|----------|
| Albion-specific OCR | P0 |
| Kill detection | P0 |
| Bomb detection | P0 |
| Cooldown recognition | P0 |
| Party status detection | P0 |
| Player recognition | P1 |
| Battle timeline extraction | P0 |
| Guild metadata extraction | P1 |
| Engagement scoring | P0 |
| Albion UI template system + calibration wizard | P0 |
| Event badges and filters in media library | P0 |

**Exit criteria:**
- Bomb detection ≥ 70% precision on validation set
- Albion events displayed with confidence on clip cards
- Battle timeline extractable from analyzed session
- PROJECT_STATE.md updated; await approval before M6

---

## Milestone 6: AI Assistant

**Duration:** 3–4 weeks  
**Goal:** Natural language assistant for editing and montage creation.

| Deliverable | Priority |
|-------------|----------|
| Chat panel UI | P0 |
| LLM integration (Ollama / OpenAI) | P0 |
| Project context injection | P0 |
| NL command parsing | P0 |
| Edit suggestions with confidence + reasoning | P0 |
| Execute edits on timeline (undoable) | P0 |
| Answer questions about project/media | P0 |
| Generate complete montages from instructions | P0 |

**Exit criteria:**
- Chat commands modify timeline (replace clip, adjust pacing, etc.)
- All chat edits are undoable
- Assistant can generate montage from natural language prompt
- E2E test: chat-driven edit workflow
- PROJECT_STATE.md updated; await approval before M7

---

## Milestone 7: Polish & Production

**Duration:** 4–6 weeks  
**Goal:** Production-ready release.

| Deliverable | Priority |
|-------------|----------|
| Performance optimization | P0 |
| Installer creation (macOS + Windows) | P0 |
| Auto-updater | P1 |
| Crash reporting | P0 |
| Profiling and memory optimization | P0 |
| End-to-end test suite | P0 |
| User documentation | P0 |
| Beta program + feedback | P0 |
| Release preparation and v1.0 tag | P0 |

**Exit criteria:**
- Beta with 5–10 Albion creators; NPS ≥ 30
- Zero P0 bugs open
- All E2E tests pass
- macOS + Windows installers built
- v1.0 tagged and released
- PROJECT_STATE.md updated

---

## Milestone Dependency Chart

```
M0 ──→ M1 ──→ M2-001 ──→ M2-002 ──→ M2-003 ──→ M2-004 ──→ M2-005 ──→ M2-006
                                                                              │
                    M3 (AI Analysis) ◄────────────────────────────────────────┘
                      │
                      ▼
                    M4 (AI Montage Generation)
                      │
                      ▼
                    M5 (Albion Intelligence)
                      │
                      ▼
                    M6 (AI Assistant)
                      │
                      ▼
                    M7 (Polish & Production)
```

M2 sub-milestones are strictly sequential. M3 requires M2 complete. M4 requires M3. M5 requires M4 (Albion scoring uses analysis pipeline). M6 requires M5. M7 requires M6.

---

## Milestone Review Process

1. Complete all exit criteria for the milestone (or sub-milestone)
2. Run test suite — all pass
3. Update documentation
4. Commit changes
5. Update PROJECT_STATE.md with summary
6. Demo working application
7. **Stakeholder approval to proceed**
8. Begin next milestone (or sub-milestone)
