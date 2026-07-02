# PROJECT_STATE.md — MontageAI

> This file is the project's memory. Updated after every meaningful coding session.

---

## Current Milestone

**Milestone 5: Albion Online Intelligence — IN PROGRESS**

**Current sub-milestone:** M5-005 — Bomb Event Detection (not started)

**Completed this session:** M5-004 Combat Timeline

---

## Completed Work

### Milestone 3 — AI Analysis Pipeline (COMPLETE)
All 8 sub-milestones complete (scene, motion, audio, OCR, object, embedding, analysis DB, background queue).

### M4-000 — Montage Planning Framework (2026-06-27)
- [x] **`MontagePlan`** — core Edit Decision List representation (not direct timeline edits)
- [x] **`MontagePlanClip`** — selected clip with source/timeline range, score, speed, transitions, audio actions, effects, beat alignment, confidence, reasoning
- [x] **Supporting models** — `MontageTransition`, `MontageEffect`, `MontageAudioAction`, `BeatAlignment`, title/ending cards, music block
- [x] **`MontagePlannerModule` interface** — replaceable planning modules with cache keys and confidence
- [x] **`MontagePlannerRegistry`** — plugin registration for planning modules
- [x] **`MontagePlanState`** — mutable state + `module_cache` for intermediate AI results
- [x] **`montage_plans` table** — persisted plans with version, seed, status, full JSON payload
- [x] **`MontagePlanService`** — create, get, list, update (editable), delete with validation
- [x] **Reproducibility** — `random_seed` stored per plan; `metadata.module_outputs` for cached module results
- [x] **APIs:**
  - `GET .../montage/modules`
  - `GET/POST .../montage/plans`
  - `GET/PUT/DELETE .../montage/plans/{id}`
- [x] **Health feature flag:** `montage` added to backend + Electron required features
- [x] **Tests:** 6 unit tests + migration test + CRUD integration test

### M4-001 — Clip Scoring Engine (2026-06-27)
- [x] **`ClipScore` domain model** — 0–100 montage score, confidence, reasoning, weighted breakdown
- [x] **Pure scoring engine** — 8 weighted factors from M3 metadata
- [x] **`ClipScoringModule`** — registered planning module
- [x] **`clip_scores` table** + repository + cache-aware APIs

### M4-002 — Highlight Detection (2026-06-27)
- [x] **`HighlightSegment` domain model** — start/end, score, confidence, reasoning
- [x] **Pure detection engine** — motion, audio, OCR, object fusion
- [x] **`HighlightDetectionModule`** + `clip_highlights` persistence + APIs

### M4-003 — Music Synchronization (2026-06-27)
- [x] **`MusicSyncAnalysis`** — beats, BPM, chorus/drops, cut + transition timing suggestions
- [x] **`MusicSyncModule`** — updates plan music block with beat markers
- [x] **`music_sync_analyses` table** + repository + APIs

### M4-004 — Transition Engine (2026-06-27)
- [x] **`PlanTransitionAnalysis` domain model** — junction recommendations with in/out transitions
- [x] **Pure transition engine** — selects from all 8 transition types using pacing profile, clip scores, beat alignment, and reproducible seed
- [x] **`TransitionEngineModule`** — registered planning module; can apply recommendations to plan clips
- [x] **`plan_transition_analyses` table** — persisted per plan with cache key validation
- [x] **`PlanTransitionRepository`** — upsert, get by plan
- [x] **APIs:**
  - `GET .../montage/plans/{plan_id}/transitions`
  - `POST .../montage/plans/{plan_id}/transitions/refresh?apply=true|false`
- [x] **Tests:** unit transition tests + migration + integration API test

### M4-005 — Pacing Engine (2026-06-27)
- [x] **`PlanPacingAnalysis` domain model** — per-clip timeline duration recommendations with confidence
- [x] **Pure pacing engine** — profile configs (balanced, aggressive, cinematic, music_driven, story_driven), target duration scaling, beat snapping, reproducible seed
- [x] **`PacingEngineModule`** — registered planning module; can apply recommendations to plan clip timeline/source ranges
- [x] **`plan_pacing_analyses` table** — persisted per plan with cache key validation
- [x] **`PlanPacingRepository`** — upsert, get by plan
- [x] **APIs:**
  - `GET .../montage/plans/{plan_id}/pacing`
  - `POST .../montage/plans/{plan_id}/pacing/refresh?apply=true|false`
- [x] **Tests:** unit pacing tests + migration + integration API test

### M4-006 — Effects Engine (2026-06-27)
- [x] **`PlanEffectsAnalysis` domain model** — per-clip effect recommendations with confidence and parameters
- [x] **Pure effects engine** — selects from all 8 `MontageEffectType`s using pacing profile, clip scores, M3 motion signals (shake, intensity, fast ratio), beat alignment, and reproducible seed
- [x] **`EffectsEngineModule`** — registered planning module; can apply recommendations to plan clip `effects` lists
- [x] **`plan_effects_analyses` table** — persisted per plan with cache key validation (includes analysis fingerprints)
- [x] **`PlanEffectsRepository`** — upsert, get by plan
- [x] **APIs:**
  - `GET .../montage/plans/{plan_id}/effects`
  - `POST .../montage/plans/{plan_id}/effects/refresh?apply=true|false`
- [x] **Tests:** unit effects tests + migration + integration API test

### M4-007 — AI Draft Generator (2026-06-27)
- [x] **`PlanDraftAnalysis` domain model** — selected clip candidates, title/ending cards, music selection, confidence
- [x] **Pure draft generator** — fuses clip scores + highlight segments, excitement-arc ordering, pacing-aware clip counts, reproducible seed
- [x] **`DraftGeneratorModule`** — registered planning module
- [x] **Draft orchestration** — `generate_draft` runs music sync, pacing, transitions, and effects modules; sets plan status to `ready`
- [x] **`plan_draft_analyses` table** — persisted per plan with cache key validation
- [x] **`PlanDraftRepository`** — upsert, get by plan
- [x] **APIs:**
  - `GET .../montage/plans/{plan_id}/draft`
  - `POST .../montage/plans/{plan_id}/draft/generate?apply=true|false&refresh_sources=true|false`
- [x] **Tests:** unit draft tests + migration + integration API test

### M4-008 — Timeline Generator (2026-06-27)
- [x] **`PlanTimelineApplication` domain model** — timeline apply result with clip counts, overwrite flag, cache key
- [x] **Pure timeline generator** — maps Montage Plan clips to video/audio/music tracks with transitions, effects, AI metadata, markers, and beat markers
- [x] **Overwrite protection** — requires `confirm_overwrite=true` when timeline contains non-matching edits
- [x] **Partial regeneration** — optional `clip_ids` to replace selected plan clips only
- [x] **`plan_timeline_applications` table** — persisted per plan
- [x] **`PlanTimelineRepository`** — upsert, get by plan
- [x] **APIs:**
  - `GET .../montage/plans/{plan_id}/timeline-application`
  - `POST .../montage/plans/{plan_id}/timeline/apply?timeline_id=&confirm_overwrite=false&clip_ids=`
- [x] **Plan status** — sets `applied` and `applied_timeline_id` on successful apply
- [x] **Tests:** unit timeline generator tests + migration + integration API test

### M4-009 — AI Feedback Loop (2026-06-27)
- [x] **`PlanQualityAnalysis` domain model** — five quality dimensions (montage, pacing, transitions, excitement, viewer retention) with confidence scores
- [x] **`PlanFeedbackState` / `PlanFeedbackEvent`** — feedback history, preferences, and regeneration hints
- [x] **Pure feedback engine** — quality estimation from plan + module analyses; feedback actions update `metadata.feedback_preferences` and plan fields (pacing profile, target duration)
- [x] **`FeedbackLoopModule`** — registered planning module
- [x] **Draft bias** — `feedback_preferences` influence clip selection scores on regeneration
- [x] **`plan_quality_analyses` + `plan_feedback_events` tables** — persisted per plan
- [x] **`PlanQualityRepository` + `PlanFeedbackRepository`**
- [x] **APIs:**
  - `GET .../montage/plans/{plan_id}/feedback`
  - `POST .../montage/plans/{plan_id}/feedback/analyze`
  - `POST .../montage/plans/{plan_id}/feedback`
  - `POST .../montage/plans/{plan_id}/feedback/regenerate?action=`
- [x] **Regeneration orchestration** — pacing-only refresh vs full draft regen based on accumulated feedback signals
- [x] **Tests:** unit feedback tests + migration + integration API test

### M5-000 — Albion Detection Framework (2026-06-27)
- [x] **`AlbionDetector` plugin interface** — `initialize()`, `analyze()`, `cancel()`, `progress()`, `version()`, `cache_key()` with GPU-aware context
- [x] **`AlbionDetectorRegistry`** — hot-swappable detector registration and replacement
- [x] **`AlbionAnalysisEngine`** — orchestrates detectors with per-detector cache validation, incremental updates, and cancel support
- [x] **`AlbionAnalyzer` M3 module** — integrates Albion detectors into existing analysis job queue, cache, and progress pipeline
- [x] **`FrameworkProbeDetector`** — validates framework lifecycle (placeholder until game-specific detectors land in M5-001+)
- [x] **Dependency wiring** — Albion module receives M3 scene/motion/audio/OCR/object caches; enqueued only for `target_game=albion`
- [x] **APIs:**
  - `GET .../media/{media_id}/analysis/albion`
  - `GET .../analysis/albion/detectors`
- [x] **Tests:** 10 unit tests + integration API tests

### M5-001 — User Interface Recognition (2026-06-27)
- [x] **`AlbionUiTemplate` system** — configurable region presets for 1080p/1440p and UI scales (100%/125%/150%)
- [x] **Template loader** — built-in presets + external JSON/YAML from `ai/plugins/albion/templates/`
- [x] **`AlbionUiDetector` plugin** — template-guided OpenCV heuristics with per-frame-window caching
- [x] **M3 object reuse** — reclassifies cached M3 object detections when available (avoids duplicate frame sampling)
- [x] **UI element taxonomy** — `party_frame`, `minimap`, `health_bar`, `ability_bar`, `kill_feed`, `chat_panel`, `resource_bar`, etc.
- [x] **API:** `GET .../media/{media_id}/analysis/albion/ui`
- [x] **Tests:** 7 unit tests + integration API test

### M5-002 — OCR Pipeline (2026-06-27)
- [x] **`AlbionOcrCategory` taxonomy** — player names, guild/alliance tags, damage/healing numbers, zones, abilities, kill/death/loot messages
- [x] **Rule-based classifier** — configurable ability and zone lexicons (`lexicon.py`) replaceable by future ML models
- [x] **`AlbionOcrDetector` plugin** — reclassifies cached M3 OCR when available; otherwise runs live OCR with GPU-aware engine resolution
- [x] **Per-frame-window cache** — every sampled window stores `cache_key`, detections, and engine metadata in `frame_windows`
- [x] **M3 OCR reuse** — avoids duplicate OCR when `ocr_analysis` cache is present in Albion context
- [x] **API:** `GET .../media/{media_id}/analysis/albion/ocr`
- [x] **Tests:** 9 unit tests + integration API test

### M5-003 — Ability Recognition (2026-06-27)
- [x] **`AlbionAbilityCatalog`** — built-in ability lexicon + external JSON/YAML from `ai/plugins/albion/abilities/`
- [x] **`AlbionAbilityDetector` plugin** — matches OCR ability mentions to catalog entries; emits activation, cooldown, and ultimate events
- [x] **M3 / Albion OCR reuse** — prefers same-run Albion OCR payload; falls back to M3 OCR reclassification
- [x] **Per-frame-window cache** — `frame_windows[].cache_key` per sampled window
- [x] **Configurable abilities** — add abilities via `ai/plugins/albion/abilities/*.json` without code changes
- [x] **API:** `GET .../media/{media_id}/analysis/albion/abilities`
- [x] **Tests:** 8 unit tests + integration API test

### M5-004 — Combat Timeline (2026-06-27)
- [x] **`AlbionCombatConfig`** — built-in thresholds + external JSON/YAML from `ai/plugins/albion/combat/`
- [x] **`AlbionCombatDetector` plugin** — fuses OCR kill/death messages, ability activations, UI health-bar activity, and M3 motion into searchable timeline entries
- [x] **Event taxonomy** — `fight_start`, `fight_end`, `kill`, `death`, `retreat` with `label` and `search_text` for future search
- [x] **Per-frame-window cache** — `frame_windows[].cache_key` per sampled window with activity scores
- [x] **Sibling detector reuse** — prefers same-run Albion OCR, ability, and UI payloads; uses cached M3 motion when available
- [x] **API:** `GET .../media/{media_id}/analysis/albion/combat-timeline`
- [x] **Tests:** 8 unit tests + integration API test

---

## Work In Progress

None — M5-004 complete; ready for M5-005.

---

## M5 Sub-Milestones

| ID | Module | Status |
|----|--------|--------|
| M5-000 | Albion Detection Framework | **Complete** |
| M5-001 | User Interface Recognition | **Complete** |
| M5-002 | OCR Pipeline | **Complete** |
| M5-003 | Ability Recognition | **Complete** |
| M5-004 | Combat Timeline | **Complete** |
| M5-005 | Bomb Event Detection | Not started |
| M5-006 | Engagement Classification | Not started |
| M5-007 | Highlight Ranking | Not started |
| M5-008 | Search Engine | Not started |
| M5-009 | Timeline Annotation | Not started |

---

## M4 Sub-Milestones

| ID | Module | Status |
|----|--------|--------|
| M4-000 | Montage Planning Framework | **Complete** |
| M4-001 | Clip Scoring Engine | **Complete** |
| M4-002 | Highlight Detection | **Complete** |
| M4-003 | Music Synchronization | **Complete** |
| M4-004 | Transition Engine | **Complete** |
| M4-005 | Pacing Engine | **Complete** |
| M4-006 | Effects Engine | **Complete** |
| M4-007 | AI Draft Generator | **Complete** |
| M4-008 | Timeline Generator | **Complete** |
| M4-009 | AI Feedback Loop | **Complete** |

---

## Known Limitations (M4 / current)

None for M4 scope — all planned montage generation sub-milestones are complete.

---

## Next Priorities

1. **M5-005 — Bomb Event Detection** (coordinated bomb moments from motion, audio, OCR, and ability fusion)

---

## Metrics

| Metric | Value |
|--------|-------|
| Milestone | **M5 in progress** (5/10 sub-milestones) |
| Backend tests | 250+ |
| Open P0 bugs | 0 |

---

## Session Log

| Date | Milestone | Summary |
|------|-----------|---------|
| 2026-06-27 | M3 complete | Full analysis pipeline through background queue |
| 2026-06-27 | M4-000 | Montage Plan framework, persistence, CRUD APIs |
| 2026-06-27 | M4-001 | Clip scoring engine, persistence, scoring APIs |
| 2026-06-27 | M4-002 | Highlight detection engine, persistence, highlight APIs |
| 2026-06-27 | M4-003 | Music sync engine, beat/section detection, music sync APIs |
| 2026-06-27 | M4-004 | Transition engine, plan junction recommendations, apply-to-plan APIs |
| 2026-06-27 | M4-005 | Pacing engine, clip duration recommendations, target scaling, beat snap, apply-to-plan APIs |
| 2026-06-27 | M4-006 | Effects engine, per-clip effect recommendations from motion/pacing, apply-to-plan APIs |
| 2026-06-27 | M4-007 | AI draft generator, clip selection from scores/highlights, full plan orchestration APIs |
| 2026-06-27 | M4-008 | Timeline generator, montage plan to editable timeline apply with overwrite protection |
| 2026-06-27 | M4-009 | AI feedback loop, quality estimates, user feedback actions, preference-driven regeneration |
| 2026-06-27 | M5-000 | Albion detection framework, plugin registry, M3 integration, framework probe detector |
| 2026-06-27 | M5-002 | Albion OCR pipeline, per-window cache, M3 OCR reclassification, typed OCR API |
| 2026-06-27 | M5-001 | Albion UI template system, HUD recognition detector, M3 object reuse, typed UI API |
