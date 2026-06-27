# Milestone Breakdown

**Product:** MontageAI  
**Version:** 1.0  
**Date:** 2026-06-26

---

## Milestone 0: Design Package ✓

**Duration:** 2 weeks  
**Goal:** Complete software design documentation; no code.  
**Status:** Complete (2026-06-26)

---

## Milestone 1: Application Shell ✓

**Duration:** 3 weeks  
**Goal:** Electron app launches with professional dark UI; Python backend connects; project CRUD works.  
**Status:** Complete (2026-06-27)

### Features
| Feature | Priority |
|---------|----------|
| Electron app scaffold (electron-vite) | P0 |
| Python backend scaffold (FastAPI) | P0 |
| Backend spawn + health check | P0 |
| Auth token communication | P0 |
| Welcome screen (new/open project) | P0 |
| Project create/open/save/close | P0 |
| Panel layout shell (empty panels) | P0 |
| Menu bar (File, Edit, View, Help) | P0 |
| Settings panel (basic) | P1 |
| Structured logging (both sides) | P0 |
| Shared types package scaffold | P0 |

### Exit Criteria
- [x] App launches on macOS in < 5s
- [x] Backend health check passes
- [x] Create project → folder structure created → reopen project works
- [x] All panels render (empty state)
- [x] Unit tests for project service
- [x] PROJECT_STATE.md updated

---

## Milestone 2: Media Pipeline

**Duration:** 3-5 weeks  
**Goal:** Import media, generate proxies/thumbnails, display in media library.

### Features
| Feature | Priority |
|---------|----------|
| File import (drag-drop + dialog) | P0 |
| FFprobe metadata extraction | P0 |
| Proxy generation (720p H.264) | P0 |
| Thumbnail generation | P0 |
| Media library grid view | P0 |
| Media library list view | P0 |
| Import progress UI | P0 |
| Background job queue | P0 |
| WebSocket progress events | P0 |
| Duplicate file detection | P1 |
| Media item delete | P1 |
| SQLite media repository | P0 |

### Exit Criteria
- Import 100 clips in < 60s (metadata + queue)
- Proxies generated in background with progress
- Media library displays thumbnails and metadata
- E2E test: import folder → see clips in library
- PROJECT_STATE.md updated

---

## Milestone 3: Clip & Albion Analysis

**Duration:** 4-5 weeks  
**Goal:** AI analyzes clips; Albion events detected; clips ranked with scores.

### Features
| Feature | Priority |
|---------|----------|
| Clip Analyzer agent | P0 |
| Albion Event Analyzer agent | P0 |
| Analysis job handlers | P0 |
| Clip scores in media library | P0 |
| Event badges on clip cards | P0 |
| Filter by event type | P0 |
| Sort by score | P0 |
| Analysis progress overlay | P0 |
| Clip detail view with analysis | P0 |
| AI suggestion card UI (display) | P1 |
| Analysis validation test set | P0 |

### Exit Criteria
- 100 clips analyzed in < 50 min (GPU)
- Bomb detection ≥ 70% precision on validation set
- Clips display excitement, motion, rank scores
- Events shown with confidence on clip cards
- Unit + integration tests for both agents
- PROJECT_STATE.md updated

---

## Milestone 4: Music & Style Analysis

**Duration:** 2-3 weeks  
**Goal:** Music analyzed for beats/drops; style learned from references.

### Features
| Feature | Priority |
|---------|----------|
| Music import and registration | P0 |
| Reference montage import | P0 |
| Music Analyzer agent | P0 |
| Style Analyzer agent | P0 |
| BPM/beat display in UI | P0 |
| Beat markers on timeline ruler | P1 |
| Energy curve visualization | P2 |
| Style profile display | P1 |

### Exit Criteria
- BPM detection within ±2 BPM on 20 test tracks
- Beat map generated and stored
- Style profile extracted from reference montage
- Beat markers visible on timeline ruler
- Unit tests for music analyzer
- PROJECT_STATE.md updated

---

## Milestone 5: Timeline Engine

**Duration:** 4-5 weeks  
**Goal:** Full multi-track timeline with editing, preview, and undo/redo.

### Features
| Feature | Priority |
|---------|----------|
| Timeline document schema + validation | P0 |
| Timeline Engine (commands, undo/redo) | P0 |
| Multi-track timeline UI | P0 |
| Clip drag-drop onto timeline | P0 |
| Trim, split, move clips | P0 |
| Playhead + ruler | P0 |
| Preview playback (proxy) | P0 |
| Transport controls | P0 |
| Snap to beats | P1 |
| Auto-save (debounced) | P0 |
| Keyboard shortcuts | P1 |
| Inspector panel (clip properties) | P0 |

### Exit Criteria
- Manual timeline editing with 50+ clips
- Undo/redo works for all operations (100+ stack)
- Preview plays proxy clips in sequence
- Snap to beat markers when enabled
- Timeline persists across app restart
- Unit tests for Timeline Engine commands
- PROJECT_STATE.md updated

---

## Milestone 6: AI Timeline Generation

**Duration:** 2-3 weeks  
**Goal:** AI generates editable timeline from analyzed clips + music + style.

### Features
| Feature | Priority |
|---------|----------|
| Timeline Planner agent | P0 |
| "Generate Timeline" button + workflow | P0 |
| AI-placed clips with metadata | P0 |
| AI Suggestions panel (accept/reject) | P0 |
| Suggestion preview | P1 |
| Timeline generation progress | P0 |
| Placement reasoning display | P0 |

### Exit Criteria
- Generate timeline from 100 analyzed clips in < 2 min
- Timeline has video + music + game audio tracks
- Cuts aligned to beat map
- AI suggestions displayed with confidence/reasoning
- Accept/reject updates timeline
- Integration test: analyze → generate → verify timeline structure
- PROJECT_STATE.md updated

---

## Milestone 7: Export & AI Chat

**Duration:** 3-4 weeks  
**Goal:** Export video; edit timeline via natural language.

### Features
| Feature | Priority |
|---------|----------|
| FFmpeg render pipeline | P0 |
| Export presets (H.264 1080p60) | P0 |
| Render queue UI | P0 |
| Render progress (WebSocket) | P0 |
| AI Chat Assistant | P1 |
| NL command parsing (rule-based) | P1 |
| Chat-driven timeline edits | P1 |
| Audio mixing (basic) | P1 |
| Export validation | P0 |

### Exit Criteria
- Export 3-min 1080p60 montage successfully
- Render progress shown in real time
- Chat commands: replace clip, make intro faster, remove slow-mo
- All chat edits are undoable
- E2E test: full workflow import → analyze → generate → edit → export
- PROJECT_STATE.md updated

---

## Milestone 8: Beta & v1.0 Release

**Duration:** 3-4 weeks  
**Goal:** Beta with creators; polish; release v1.0.

### Features
| Feature | Priority |
|---------|----------|
| Thumbnail agent | P2 |
| Performance optimization | P0 |
| Error handling polish | P0 |
| E2E test suite (complete) | P0 |
| Beta distribution (macOS + Windows) | P0 |
| Beta feedback collection | P0 |
| Bug fixes from beta | P0 |
| App packaging (electron-builder) | P0 |
| Model download UI | P1 |
| User documentation | P1 |

### Exit Criteria
- Beta with 5-10 Albion creators
- NPS ≥ 30 from beta feedback
- Zero P0 bugs open
- All E2E tests pass
- macOS + Windows installers built
- v1.0 tagged and released
- PROJECT_STATE.md updated

---

## Milestone Dependency Chart

```
M0 ──→ M1 ──→ M2 ──→ M3 ──→ M5 ──→ M6 ──→ M7 ──→ M8
                 └──→ M4 ──→ M6
```

**Parallelization opportunities:**
- M3 (Clip/Albion) and M4 (Music/Style) can overlap after M2
- Frontend timeline UI (M5) can start during late M3
- Thumbnail agent (M8) can be developed during M7

---

## Milestone Review Process

1. Complete all exit criteria
2. Run test suite — all pass
3. Demo working application
4. Update PROJECT_STATE.md
5. Review open bugs and technical debt
6. Stakeholder approval to proceed
7. Begin next milestone
