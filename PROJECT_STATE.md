# PROJECT_STATE.md — MontageAI

> This file is the project's memory. Updated after every meaningful coding session.

---

## Current Milestone

**Milestone 3: AI Analysis Pipeline — COMPLETE**

**Completed this session:** M3-008 Background Processing System

**Next:** Milestone 4 — AI Montage Generation (await approval)

---

## Completed Work

### M3-001 … M3-004
- Scene, motion, audio, and OCR analysis modules with plugin architecture

### M3-005 — Object Detection (2026-06-27)
- [x] **`ObjectDetector` interface** — replaceable backends (YOLOv8 + UI heuristics composite)
- [x] **`YoloObjectDetector`** — COCO pre-trained model maps person→character, horse→mount
- [x] **`UiHeuristicObjectDetector`** — OpenCV heuristics for minimap, party frames, health bars, UI panels, spell effects
- [x] **`ObjectAnalyzer`** — samples frames, runs detection in thread pool, IoU deduplication
- [x] **Categories:** character, mount, spell_effect, party_frame, ui_panel, health_bar, minimap
- [x] **Timestamped detections** with bounding boxes, confidence, source model id
- [x] **Cache:** versioned keys include detector id, sample interval, max frames
- [x] **Auto-enqueue** on import
- [x] **API:** `GET .../analysis/object`
- [x] **Optional deps:** `pip install montage-backend[vision]` for YOLO + OpenCV
- [x] **Tests:** 6 object unit tests + object API integration test

### M3-006 — Embedding Engine (2026-06-27)
- [x] **`EmbeddingEngine` interface** — replaceable backends (CLIP + histogram fallback)
- [x] **`ClipEmbeddingEngine`** — sentence-transformers `clip-ViT-B-32` when available
- [x] **`HistogramEmbeddingEngine`** — deterministic 512-dim fallback when CLIP unavailable
- [x] **`EmbeddingAnalyzer`** — clip midpoint, scene midpoints (from scene cache), keyframes every 3s
- [x] **`analysis_embeddings` table** — vector storage per project DB with upsert/search/duplicate detection
- [x] **Cache:** vectors persisted to DB; cache payload stores metadata + embedding IDs only
- [x] **Auto-enqueue** on import (loads scene segments into analyzer context)
- [x] **APIs:** embedding, semantic search, similar clips/scenes, duplicate detection
- [x] **Optional deps:** `pip install montage-backend[embedding]` for CLIP
- [x] **Tests:** 7 embedding unit tests + repo test + embedding API integration test

### M3-007 — Analysis Database (2026-06-27)
- [x] **`clip_analysis_snapshots` table** — incremental per-clip analysis summaries
- [x] **`ClipAnalysisRecord`** — unified view aggregating M2 metadata + all M3 modules
- [x] **APIs:** full analysis, summary, refresh, project overview, invalidate all
- [x] **Tests:** 5 aggregation unit tests + clip analysis API integration test

### M3-008 — Background Processing System (2026-06-27)
- [x] **`AnalysisJobQueue`** — prioritized asyncio queue with worker pool concurrency limit
- [x] **Module priorities** — scene (100) > motion/audio/ocr/object (50) > embedding (10)
- [x] **Project pause/resume** — blocks dispatch without cancelling in-flight work abruptly
- [x] **Job pause/resume** — per-job control via `AnalysisRunContext.pause()`
- [x] **Retry** — configurable `max_retries` (default 2) with priority boost on retry
- [x] **Cancellation** — existing cancel flow integrated with queue
- [x] **Progress reporting** — WebSocket `analysis.progress` events (unchanged)
- [x] **DB:** `retry_count`, `max_retries` columns on `analysis_jobs`; `PAUSED` processing status
- [x] **APIs:**
  - `GET .../analysis/jobs` — list project jobs
  - `GET .../analysis/queue` — queue status
  - `POST .../analysis/queue/pause` / `resume`
  - `POST .../analysis/jobs/{id}/pause` / `resume` / `retry`
- [x] **Tests:** 3 queue unit tests + service/migration tests + queue API integration test

---

## Work In Progress

None — Milestone 3 complete.

---

## M3 Sub-Milestones (all complete)

| ID | Module | Status |
|----|--------|--------|
| M3-001 | Scene Analysis | **Complete** |
| M3-002 | Motion Analysis | **Complete** |
| M3-003 | Audio Analysis | **Complete** |
| M3-004 | OCR Engine | **Complete** |
| M3-005 | Object Detection | **Complete** |
| M3-006 | Embedding Engine | **Complete** |
| M3-007 | Analysis Database | **Complete** |
| M3-008 | Background Processing | **Complete** |

---

## Known Limitations (M3)

| Limitation | Target |
|------------|--------|
| YOLO uses generic COCO classes, not Albion-specific models | M5 / custom models |
| UI heuristics are resolution/layout approximate | Albion YAML templates M5 |
| CLIP is generic; histogram fallback is not semantic | Albion-specific models M5 |
| Vector search is brute-force cosine over project DB | Dedicated vector index later |
| Queue state is in-memory (pause/resume lost on restart) | Persistent queue M4+ |

---

## Next Priorities

1. **Milestone 4 — AI Montage Generation** (highlight selection, beat sync, pacing, transitions)
2. Frontend UI for analysis results and queue controls

---

## Metrics

| Metric | Value |
|--------|-------|
| Milestone | **M3 complete** (8/8 sub-milestones) |
| Backend tests | 135+ (65+ M3 tests total) |
| Open P0 bugs | 0 |

---

## Session Log

| Date | Milestone | Summary |
|------|-----------|---------|
| 2026-06-27 | M3-001 … M3-004 | Scene, motion, audio, OCR pipelines |
| 2026-06-27 | M3-005 | Object detection with YOLO + UI heuristic backends |
| 2026-06-27 | M3-006 | Embedding engine with CLIP/histogram backends and vector search APIs |
| 2026-06-27 | M3-007 | Central analysis database with unified clip view and project overview |
| 2026-06-27 | M3-008 | Prioritized background job queue with pause, resume, and retry |
