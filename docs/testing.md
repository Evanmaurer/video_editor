# Testing Guide

**Product:** MontageAI  
**Purpose:** Practical steps to verify features work — run these after every sub-milestone.

For testing philosophy, coverage targets, and CI expectations, see [19-testing-strategy.md](./19-testing-strategy.md).

---

## Quick start

```bash
# Backend (from repo root)
cd apps/backend
python3 -m pytest tests/unit -q          # fast unit tests
python3 -m pytest tests/integration -q # API + service integration

# Frontend (when applicable)
cd apps/desktop
pnpm test
```

**Backend health check** (with server running):

```bash
curl http://127.0.0.1:8000/health
```

---

## How to test any sub-milestone

Use this checklist every time a feature lands:

| Step | What to do | Pass if |
|------|------------|---------|
| 1. Unit tests | `pytest tests/unit/test_<feature>.py -v` | All green |
| 2. Integration tests | `pytest tests/integration/test_<area>_api.py -v` | All green |
| 3. Module registered | `GET /api/v1/projects/{id}/.../modules` | New module appears |
| 4. Manual API smoke | `curl` the new endpoints (see below) | Expected JSON shape |
| 5. Cache behavior | Run twice on same clip without `force` | Second run is fast / cache hit |
| 6. Project state | Read `PROJECT_STATE.md` | Sub-milestone marked complete |

### Start the backend manually

```bash
cd apps/backend
python3 -m uvicorn montage_backend.main:app --reload --port 8000
```

API docs: `http://127.0.0.1:8000/docs`

### Create a test project

```bash
curl -X POST http://127.0.0.1:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Project",
    "root_path": "/tmp/montage-test-project",
    "width": 1920,
    "height": 1080,
    "frame_rate": 60,
    "target_game": "albion"
  }'
```

Save the returned `id` as `PROJECT_ID`.

---

## Milestone 3 — Analysis pipeline

```bash
cd apps/backend
python3 -m pytest tests/unit/test_analysis_framework.py tests/integration/test_analysis_api.py -q
```

**Manual checks:**

```bash
# List analysis modules
curl http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/analysis/modules

# Run scene analysis on a clip
curl -X POST "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/media/$MEDIA_ID/analysis/scene/run"

# Poll status
curl "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/media/$MEDIA_ID/analysis/scene/status"

# Get typed result
curl "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/media/$MEDIA_ID/analysis/scenes"
```

**Broken if:** job stuck in `processing`, 404 on typed routes, or empty `segments`/`detections` on a real gameplay clip.

---

## Milestone 4 — Montage generation

```bash
cd apps/backend
python3 -m pytest tests/integration/test_montage_api.py tests/unit/test_montage_plan.py -q
```

**Manual flow:**

```bash
# List montage modules
curl http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/montage/modules

# Create a plan
curl -X POST http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/montage/plans \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Montage", "random_seed": 42, "target_duration_ms": 15000, "pacing_profile": "balanced"}'

# Generate draft (apply=true runs full pipeline)
curl -X POST "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/montage/plans/$PLAN_ID/draft/generate?apply=true&refresh_sources=true"

# Apply to timeline
curl -X POST "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/montage/plans/$PLAN_ID/timeline/apply"
```

**Broken if:** plan has no clips after generate, status not `ready`, or timeline apply returns 409 without `confirm_overwrite=true` when expected.

---

## Milestone 5 — Albion Online Intelligence

### M5-000 — Albion Detection Framework

**Automated:**

```bash
cd apps/backend
python3 -m pytest tests/unit/test_albion_framework.py -v
python3 -m pytest tests/integration/test_analysis_api.py::test_analysis_modules_list -v
python3 -m pytest tests/integration/test_analysis_api.py::test_albion_detectors_list -v
python3 -m pytest tests/integration/test_analysis_api.py::test_albion_analysis_query -v
```

**Manual:**

```bash
# 1. Albion module registered
curl http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/analysis/modules
# → look for: { "module_id": "albion", "version": "albion-framework-v1.0" }

# 2. Detector plugins listed
curl http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/analysis/albion/detectors
# → expect: [{ "detector_id": "framework_probe", "version": "framework-probe-v1.0" }]

# 3. Run albion analysis (after importing a clip)
curl -X POST "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/media/$MEDIA_ID/analysis/albion/run"
curl "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/media/$MEDIA_ID/analysis/albion/status"
curl "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/media/$MEDIA_ID/analysis/albion"
```

**Expected result shape:**

```json
{
  "analyzer_version": "albion-framework-v1.0",
  "summary": {
    "detector_count": 1,
    "event_count": 1,
    "detector_ids": ["framework_probe"]
  },
  "detector_results": {
    "framework_probe": {
      "confidence": 1.0,
      "events": [{ "event_type": "framework_probe", "timestamp_ms": 0 }]
    }
  }
}
```

**Cache check:** run albion twice on the same clip. The second run should complete quickly (cache hit in job message).

**Albion-only enqueue:** projects with `"target_game": "albion"` auto-enqueue albion on import. Other games should not.

```bash
curl http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/analysis/queue
```

**Broken if:**
- `albion` missing from modules list
- `GET .../analysis/albion` returns raw cache wrapper instead of typed result (missing `summary`)
- analysis stuck in `processing` forever
- albion enqueued for non-albion projects

---

### M5-001 — User Interface Recognition *(complete)*

```bash
python3 -m pytest tests/unit/test_albion_ui_detection.py -v
curl "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/media/$MEDIA_ID/analysis/albion/ui"
```

**Pass if:** detections include UI elements (`party_frame`, `minimap`, `health_bar`, `ability_bar`, `kill_feed`, etc.) with `timestamp_ms`, bounding boxes, and `template_id`; `frame_windows[].cache_key` per window; `summary.reused_m3_object` is true when M3 object cache exists.

**Broken if:** empty `frame_windows`, missing bounding boxes, or live UI detection re-runs when M3 object cache is already available.

---

### M5-002 — OCR Pipeline *(complete)*

```bash
python3 -m pytest tests/unit/test_albion_ocr.py -v
curl "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/media/$MEDIA_ID/analysis/albion/ocr"
```

**Pass if:** detections include Albion categories (`kill_message`, `damage_number`, `guild_tag`, `ability_name`, etc.) with `frame_windows[].cache_key` per window; `summary.reused_m3_ocr` is true when M3 OCR cache exists.

**Broken if:** empty `frame_windows`, missing category classification, or live OCR re-runs when M3 cache is already available.

---

### M5-003 — Ability Recognition *(complete)*

```bash
python3 -m pytest tests/unit/test_albion_ability_recognition.py -v
curl -X POST "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/media/$MEDIA_ID/analysis/albion/run"
curl "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/media/$MEDIA_ID/analysis/albion/status"
curl "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/media/$MEDIA_ID/analysis/albion/abilities"
```

**Pass if:** ability activations, cooldowns, and ultimates appear as timestamped events when OCR finds `ability_name` detections; new abilities can be added via config without code changes. `summary.reused_albion_ocr` is true when Albion OCR ran in the same job.

**Broken if:** `null` after a successful albion run that includes the `ability` detector, empty `events` when OCR has `ability_name` mentions, missing `cooldown_ready` projections, or catalog changes require code edits.

**Note:** noisy OCR on real gameplay clips often yields `ability_name: 0` and an empty-but-valid abilities payload (`mention_count: 0`). That is expected for this milestone; ability recognition depends on OCR classifying spell names correctly.

---

### M5-004 — Combat Timeline *(complete)*

```bash
python3 -m pytest tests/unit/test_albion_combat_timeline.py -v
curl -X POST "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/media/$MEDIA_ID/analysis/albion/run"
curl "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/media/$MEDIA_ID/analysis/albion/combat-timeline"
```

**Pass if:** fight start/end, kills, deaths, and retreats appear as searchable timeline entries with `label`, `search_text`, and `timestamp_ms`; `frame_windows[].cache_key` per window.

**Broken if:** `null` after a successful albion run that includes the `combat` detector, missing `search_text` on entries, or fight boundaries when OCR has kill/death signals plus sustained activity.

**Note:** real ZvZ clips with noisy OCR may still produce kills without clean fight segmentation; empty `entries` with `summary.entry_count: 0` is valid when no combat OCR signals exist.

---

### M5-005 — Bomb Event Detection *(complete)*

```bash
python3 -m pytest tests/unit/test_albion_bomb_detection.py -v
curl -X POST "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/media/$MEDIA_ID/analysis/albion/run"
curl "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/media/$MEDIA_ID/analysis/albion/bombs"
```

**Pass if:** coordinated bomb moments detected with confidence scores from motion, audio, OCR, and ability fusion.

**Broken if:** `null` after a successful albion run that includes the `bomb` detector, missing `bomb_score`/`fusion` on events, or no bomb detected when combat timeline has `>= bomb_min_kills` kills in the configured window.

**Note:** on real clips, OCR-only kill spikes may produce bombs with high `fusion.ocr_score` but low motion/audio if M3 caches are missing — that is valid for this milestone.

---

### M5-006 — Engagement Classification *(not started)*

**Pass if:** clips tagged with engagement types (ZvZ, ganking, gathering, etc.); multiple tags per clip supported.

---

### M5-007 — Highlight Ranking *(not started)*

**Pass if:** each clip has an Albion-specific highlight score with a human-readable explanation.

---

### M5-008 — Search Engine *(not started)*

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/albion/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "bomb clips"}'
```

**Pass if:** search uses cached metadata only (no re-analysis); filters like engagement type, ability name, and kill count work.

---

### M5-009 — Timeline Annotation *(not started)*

**Pass if:** editor timeline shows bomb/kill/ability markers; clicking a marker seeks to that moment.

---

## Milestone template (copy for new work)

```markdown
### Mx-00y — Feature Name

**Automated:**
\`\`\`bash
cd apps/backend
python3 -m pytest tests/unit/test_<name>.py -v
python3 -m pytest tests/integration/test_<name>_api.py -v
\`\`\`

**Manual:**
\`\`\`bash
curl http://127.0.0.1:8000/api/v1/...
\`\`\`

**Pass if:** ...
**Broken if:** ...
```

---

## Common failures

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `command not found: python` | Python not on PATH | Use `python3` |
| Tests fail on `greenlet` | Missing SQLAlchemy async dep | `pip install greenlet` |
| 404 on typed analysis route | Generic `/{module_id}` route matched first | Use typed route (`/scenes`, `/albion`, etc.) |
| Job stuck `processing` | Fake/invalid video file in test | Use a real `.mp4` for manual tests |
| Cache never hits | File changed (mtime/size) | Same file → same fingerprint |
| Albion not enqueued | `target_game` not `"albion"` | Set `target_game` on project create |

---

## Related docs

- [19-testing-strategy.md](./19-testing-strategy.md) — philosophy, pyramid, CI
- [12-api-design.md](./12-api-design.md) — full API reference
- [development-guide.md](./development-guide.md) — setup and dev workflow
- [PROJECT_STATE.md](../PROJECT_STATE.md) — current milestone status
