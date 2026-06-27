# PROJECT_STATE.md — MontageAI

> This file is the project's memory. Updated after every meaningful coding session.

---

## Current Milestone

**Milestone 2: Media Processing Engine — COMPLETE** (awaiting approval)

**Next milestone:** M3 — AI Analysis Pipeline (do not start until Milestone 2 approved)

### Milestone plan (M2–M7)

| Milestone | Name |
|-----------|------|
| M2 | Media Processing Engine (M2-001 … M2-006) |
| M3 | AI Analysis Pipeline |
| M4 | AI Montage Generation |
| M5 | Albion Online Intelligence |
| M6 | AI Assistant |
| M7 | Polish & Production |

**Rules:** Complete each milestone (tested, documented, committed) before the next. At each milestone completion, summarize, update this file, and **wait for approval** before proceeding.

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
- [x] **Backend API:** active timeline, list/create/get/save; JSON on disk + SQLite index
- [x] **Timeline UI:** multi-track editing, ruler, playhead, zoom, snap/ripple, keyboard shortcuts

### M2-004 — Playback Engine (2026-06-27)
- [x] **`@montage/playback-engine`** + GPU decode, frame cache, preview transport
- [x] HTML5 proxy playback + canvas scrubbing; metrics in status bar

### M2-005 — Export Engine (2026-06-27)
- [x] **`RenderService`** — background queue, pause/resume/cancel, ETA, FFmpeg logs
- [x] **Presets:** H.264 · 1080p/1440p/4K · 60 FPS
- [x] **Export UI:** dialog + render queue panel; WebSocket progress

### M2-006 — AI Metadata Engine (2026-06-27)
- [x] **`MetadataExtractor`** — FFmpeg visual/audio feature extraction on import
- [x] **Visual cache:** scenes, motion, camera movement, brightness, color histogram, blur/sharpness, keyframes
- [x] **Audio cache:** loudness, peaks, silence regions, beat timing, speech heuristics
- [x] **AI cache schema:** OCR, embeddings, detections, optical flow, CLIP slots (null until M3)
- [x] **SQLite storage:** `media_metadata_features` table per project + `metadata_status` on media items
- [x] **Background processing:** auto-enqueued after import; fingerprint invalidation on source change
- [x] **API:** GET/PUT metadata, analyze, invalidate — clean contract for M3 AI modules
- [x] **Inspector UI:** clip metadata summary (scenes, motion, speech, beats)
- [x] **Tests:** 6 extractor unit tests + 2 metadata API integration tests

---

## Work In Progress

None — **Milestone 2 complete**, awaiting approval before M3.

---

## Known Bugs

No open P0 bugs for M2-006.

---

## Known Limitations (M2 / end of Milestone 2)

| Limitation | Target |
|------------|--------|
| AI cache slots empty until M3 analysis agents | M3 |
| Speech/beat detection uses FFmpeg heuristics, not ML | M3 |
| Multi-track video compositing on export | M3+ |
| Render jobs in-memory (not persisted across restart) | Future |
| Alembic migrations (using create_all + column helper) | Tech debt |

---

## Technical Debt

| Item | Priority | Notes |
|------|----------|-------|
| Alembic migrations | Medium | Column migration helper exists |
| Real FFmpeg integration tests in CI | Low | Local tests mock subprocess |
| Electron E2E smoke tests | Medium | M2–M7 |
| Persist render job state to project DB | Low | In-memory queue for M2-005 |

---

## Next Priorities (M3 — AI Analysis Pipeline)

1. Clip analysis agents (OCR, object detection, CLIP embeddings)
2. Write results into AI metadata cache via existing API
3. Do **not** start until Milestone 2 is approved

---

## Metrics

| Metric | Value |
|--------|-------|
| Milestone | **M2 complete** (6/6 sub-milestones) |
| Backend tests | 68+ passing |
| Frontend + engine tests | 43+ passing |
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
| 2026-06-27 | M2-003 | Timeline engine, commands, UI, persistence |
| 2026-06-27 | M2-004 | Playback engine, preview, decode cache |
| 2026-06-27 | M2-005 | Export engine, render queue, H.264 presets |
| 2026-06-27 | M2-006 | AI metadata cache, extractor, API, inspector — **M2 complete** |
