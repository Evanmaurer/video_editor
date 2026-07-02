# PROJECT_STATE.md — MontageAI

> This file is the project's memory. Updated after every meaningful coding session.

---

## Current Milestone

**Milestone 4: AI Montage Generation — COMPLETE**

**Current sub-milestone:** None (all M4 sub-milestones complete)

**Completed this session:** M4-009 AI Feedback Loop

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

---

## Work In Progress

None — Milestone 4 complete.

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

1. **Milestone 5** — TBD (UI integration, export pipeline, or next roadmap item)

---

## Metrics

| Metric | Value |
|--------|-------|
| Milestone | **M4 complete** (10/10 sub-milestones) |
| Backend tests | 230+ |
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
