# PROJECT_STATE.md — MontageAI

> This file is the project's memory. Updated after every meaningful coding session.

---

## Current Milestone

**Milestone 2: Media Processing Engine**

**Current sub-milestone:** M2-003 — Timeline Engine — **Complete** (awaiting approval)

**Next sub-milestone:** M2-004 — Playback Engine (not started)

### Milestone plan (M2–M7)

| Milestone | Name |
|-----------|------|
| M2 | Media Processing Engine (M2-001 … M2-006) |
| M3 | AI Analysis Pipeline |
| M4 | AI Montage Generation |
| M5 | Albion Online Intelligence |
| M6 | AI Assistant |
| M7 | Polish & Production |

**Rules:** Complete each M2 sub-milestone (tested, documented, committed) before the next. At each milestone completion, summarize, update this file, and **wait for approval** before proceeding.

---

## Completed Work

### Milestone 0 (2026-06-26)
- Complete software design package (20 documents)

### Milestone 1 (2026-06-27)
- [x] Monorepo, Electron shell, FastAPI backend, project CRUD, settings, IPC API proxy
- [x] 32 tests passing; tag `milestone-1`

### M2-001 — Media Processing Engine (2026-06-27)
- [x] `MediaProcessor`, FFmpeg integration, cache, async import pipeline
- [x] 41 backend tests at completion

### M2-002 — Media Library (2026-06-27)
- [x] Media import API, Electron import flows, Media Library UI, thumbnails
- [x] 43 backend + 25 frontend tests at completion

### M2-003 — Timeline Engine (2026-06-27)
- [x] **`@montage/timeline-engine`** — command-based mutations, undo/redo (100 steps), snap, clipboard
- [x] **Commands:** add/remove/move/trim/split/ripple delete/paste/batch (AI-automation ready)
- [x] **Backend API:** active timeline, list/create/get/save; JSON on disk + SQLite index
- [x] **Timeline UI:** multi-track (2 video + 2 audio), ruler, playhead, zoom, snap/ripple toggles
- [x] **Editing:** drag from media library, trim handles, move, split, delete, ripple mode
- [x] **Inspector:** playhead position + selected clip properties
- [x] **Keyboard:** ⌘Z/⌘⇧Z undo/redo, ⌘C/X/V clipboard, S split, Delete remove
- [x] **Autosave:** 2s debounced save to backend
- [x] **Tests:** 7 engine unit tests + 3 timeline API integration tests

---

## Work In Progress

None — M2-003 complete, awaiting approval before M2-004.

---

## Known Bugs

No open P0 bugs for M2-003.

---

## Known Limitations (M2-003)

| Limitation | Target |
|------------|--------|
| No preview playback of timeline | M2-004 |
| Beat snap requires beat_markers data | M3+ |
| Drag preview is handle-based (commits on mouseup) | Polish |
| Alembic migrations (using create_all) | Tech debt |

---

## Technical Debt

| Item | Priority | Notes |
|------|----------|-------|
| Alembic migrations | Medium | Column migration helper exists |
| Real FFmpeg integration tests in CI | Low | Local tests mock subprocess |
| Electron E2E smoke tests | Medium | M2–M7 |

---

## Next Priorities (M2-004 — Playback)

1. PreviewController + proxy-based sequential playback
2. Transport controls (play/pause/seek)
3. Do **not** start until M2-003 is approved

---

## Metrics

| Metric | Value |
|--------|-------|
| Milestone | M2-003 complete (3/6 sub-milestones) |
| Backend tests | 46+ passing |
| Frontend + engine tests | 32+ passing |
| Open P0 bugs | 0 |
| Git tag | `milestone-1` (M1) |

---

## Session Log

| Date | Milestone | Summary |
|------|-----------|---------|
| 2026-06-26 | M0 | Design package (20 documents) |
| 2026-06-27 | M1 | Application shell; tag `milestone-1` |
| 2026-06-27 | M2-001 | MediaProcessor, import pipeline |
| 2026-06-27 | M2-002 | Media library API, UI, Electron import |
| 2026-06-27 | M2-003 | Timeline engine, commands, UI, persistence, tests |
