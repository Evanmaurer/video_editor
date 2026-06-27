# Database Schema

**Product:** MontageAI  
**Engine:** SQLite 3 (one database per project: `project.db`)  
**Version:** 1.0  
**Date:** 2026-06-26

---

## 1. Design Principles

- One SQLite file per project for portability and backup simplicity.
- Normalized relational schema for queryable metadata.
- Large JSON blobs (beat maps, style profiles) stored in TEXT columns with JSON validation.
- Immutable analysis results versioned by `analysis_version`.
- Foreign keys enforced (`PRAGMA foreign_keys = ON`).
- Timestamps in UTC ISO 8601.

## 2. Entity Relationship Diagram

```
┌─────────────┐       ┌──────────────┐       ┌─────────────────┐
│  projects   │───1:N─│  media_items │───1:N─│ clip_analysis   │
└─────────────┘       └──────────────┘       └─────────────────┘
       │                      │                       │
       │                      │                       │
       │               ┌──────▼───────┐       ┌───────▼────────┐
       │               │ game_events  │       │ analysis_jobs  │
       │               └──────────────┘       └────────────────┘
       │
       ├──1:N──┌──────────────┐
       │       │ music_tracks │
       │       └──────┬───────┘
       │              │
       │       ┌──────▼───────┐
       │       │music_analysis│
       │       └──────────────┘
       │
       ├──1:N──┌──────────────────┐
       │       │reference_montages│
       │       └────────┬─────────┘
       │                │
       │         ┌──────▼────────┐
       │         │ style_profiles│
       │         └───────────────┘
       │
       ├──1:N──┌──────────────┐       ┌─────────────────┐
       │       │  timelines   │───1:N─│ timeline_clips  │
       │       └──────────────┘       └─────────────────┘
       │
       ├──1:N──┌─────────────────┐
       │       │ ai_suggestions  │
       │       └─────────────────┘
       │
       └──1:N──┌─────────────┐
               │ render_jobs │
               └─────────────┘
```

## 3. Table Definitions

### 3.1 `projects`

Project-level metadata. One row per open project file.

```sql
CREATE TABLE projects (
    id              TEXT PRIMARY KEY,          -- UUID
    name            TEXT NOT NULL,
    description     TEXT,
    root_path       TEXT NOT NULL UNIQUE,
    width           INTEGER NOT NULL DEFAULT 1920,
    height          INTEGER NOT NULL DEFAULT 1080,
    frame_rate      REAL NOT NULL DEFAULT 60.0,
    target_game     TEXT NOT NULL DEFAULT 'albion',
    settings_json   TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
```

### 3.2 `media_items`

All imported media files (gameplay clips, music, references).

```sql
CREATE TABLE media_items (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    file_path       TEXT NOT NULL,
    file_name       TEXT NOT NULL,
    media_type      TEXT NOT NULL CHECK (media_type IN ('video', 'audio', 'image')),
    role            TEXT NOT NULL CHECK (role IN ('clip', 'music', 'reference', 'voice', 'other')),
    duration_ms     INTEGER,
    width           INTEGER,
    height          INTEGER,
    frame_rate      REAL,
    codec           TEXT,
    file_size_bytes INTEGER,
    proxy_path      TEXT,
    thumbnail_path  TEXT,
    import_status   TEXT NOT NULL DEFAULT 'pending'
                    CHECK (import_status IN ('pending', 'processing', 'ready', 'error')),
    error_message   TEXT,
    metadata_json   TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    UNIQUE (project_id, file_path)
);

CREATE INDEX idx_media_items_project ON media_items(project_id);
CREATE INDEX idx_media_items_role ON media_items(project_id, role);
CREATE INDEX idx_media_items_status ON media_items(import_status);
```

### 3.3 `clip_analysis`

Results from Clip Analyzer agent. One row per analysis run.

```sql
CREATE TABLE clip_analysis (
    id                  TEXT PRIMARY KEY,
    media_item_id       TEXT NOT NULL REFERENCES media_items(id) ON DELETE CASCADE,
    analysis_version    TEXT NOT NULL,           -- e.g. "clip-analyzer-v1.0"
    excitement_score    REAL CHECK (excitement_score BETWEEN 0 AND 10),
    motion_score        REAL CHECK (motion_score BETWEEN 0 AND 10),
    rank_score          REAL CHECK (rank_score BETWEEN 0 AND 10),
    confidence          REAL CHECK (confidence BETWEEN 0 AND 1),
    reasoning           TEXT,
    scenes_json         TEXT NOT NULL DEFAULT '[]',
    downtime_json       TEXT NOT NULL DEFAULT '[]',
    camera_movement     TEXT,
    ocr_results_json    TEXT NOT NULL DEFAULT '[]',
    raw_output_json     TEXT NOT NULL DEFAULT '{}',
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'running', 'complete', 'failed')),
    error_message       TEXT,
    created_at          TEXT NOT NULL,
    completed_at        TEXT
);

CREATE INDEX idx_clip_analysis_media ON clip_analysis(media_item_id);
CREATE INDEX idx_clip_analysis_rank ON clip_analysis(rank_score DESC);
```

### 3.4 `game_events`

Albion-specific (and future game) events detected in clips.

```sql
CREATE TABLE game_events (
    id              TEXT PRIMARY KEY,
    media_item_id   TEXT NOT NULL REFERENCES media_items(id) ON DELETE CASCADE,
    analysis_id     TEXT REFERENCES clip_analysis(id) ON DELETE SET NULL,
    game_id         TEXT NOT NULL DEFAULT 'albion',
    event_type      TEXT NOT NULL,               -- bomb, wipe, engagement, loot_explosion, kill_feed_burst
    start_ms        INTEGER NOT NULL,
    end_ms          INTEGER NOT NULL,
    confidence      REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    intensity       REAL CHECK (intensity BETWEEN 0 AND 10),
    reasoning       TEXT,
    metadata_json   TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL
);

CREATE INDEX idx_game_events_media ON game_events(media_item_id);
CREATE INDEX idx_game_events_type ON game_events(event_type);
CREATE INDEX idx_game_events_confidence ON game_events(confidence DESC);
```

### 3.5 `music_tracks`

Imported music files linked to project.

```sql
CREATE TABLE music_tracks (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    media_item_id   TEXT NOT NULL REFERENCES media_items(id) ON DELETE CASCADE,
    is_primary      INTEGER NOT NULL DEFAULT 0,  -- boolean
    title           TEXT,
    artist          TEXT,
    created_at      TEXT NOT NULL
);
```

### 3.6 `music_analysis`

Results from Music Analyzer agent.

```sql
CREATE TABLE music_analysis (
    id                  TEXT PRIMARY KEY,
    music_track_id      TEXT NOT NULL REFERENCES music_tracks(id) ON DELETE CASCADE,
    analysis_version    TEXT NOT NULL,
    bpm                 REAL,
    bpm_confidence      REAL CHECK (bpm_confidence BETWEEN 0 AND 1),
    beats_json          TEXT NOT NULL DEFAULT '[]',      -- [{time_ms, strength}]
    drops_json          TEXT NOT NULL DEFAULT '[]',
    choruses_json       TEXT NOT NULL DEFAULT '[]',
    energy_curve_json   TEXT NOT NULL DEFAULT '[]',
    beat_map_json       TEXT NOT NULL DEFAULT '{}',
    raw_output_json     TEXT NOT NULL DEFAULT '{}',
    status              TEXT NOT NULL DEFAULT 'pending',
    created_at          TEXT NOT NULL,
    completed_at        TEXT
);
```

### 3.7 `reference_montages`

Reference videos for style learning.

```sql
CREATE TABLE reference_montages (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    media_item_id   TEXT NOT NULL REFERENCES media_items(id) ON DELETE CASCADE,
    label           TEXT,
    created_at      TEXT NOT NULL
);
```

### 3.8 `style_profiles`

Aggregated style extracted from reference montage(s).

```sql
CREATE TABLE style_profiles (
    id                      TEXT PRIMARY KEY,
    project_id              TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    reference_montage_id    TEXT REFERENCES reference_montages(id) ON DELETE SET NULL,
    analysis_version        TEXT NOT NULL,
    avg_clip_duration_ms    REAL,
    cuts_per_minute         REAL,
    slow_motion_pct         REAL,
    replay_pct              REAL,
    transition_distribution_json TEXT NOT NULL DEFAULT '{}',
    pacing_curve_json       TEXT NOT NULL DEFAULT '[]',
    color_grade_json        TEXT NOT NULL DEFAULT '{}',
    confidence              REAL,
    reasoning               TEXT,
    raw_output_json         TEXT NOT NULL DEFAULT '{}',
    created_at              TEXT NOT NULL
);
```

### 3.9 `timelines`

Timeline documents. Full JSON also stored on disk; DB holds metadata + active pointer.

```sql
CREATE TABLE timelines (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name            TEXT NOT NULL DEFAULT 'Main',
    file_path       TEXT NOT NULL,               -- path to .timeline.json
    duration_ms     INTEGER,
    is_active       INTEGER NOT NULL DEFAULT 0,
    version         INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
```

### 3.10 `timeline_clips`

Denormalized index of clips on timeline for fast queries (source of truth is JSON file).

```sql
CREATE TABLE timeline_clips (
    id              TEXT PRIMARY KEY,
    timeline_id     TEXT NOT NULL REFERENCES timelines(id) ON DELETE CASCADE,
    media_item_id   TEXT REFERENCES media_items(id) ON DELETE SET NULL,
    track_index     INTEGER NOT NULL,
    start_ms        INTEGER NOT NULL,
    end_ms          INTEGER NOT NULL,
    source_in_ms    INTEGER NOT NULL,
    source_out_ms   INTEGER NOT NULL,
    speed           REAL NOT NULL DEFAULT 1.0,
    ai_generated    INTEGER NOT NULL DEFAULT 0,
    ai_confidence   REAL,
    ai_reasoning    TEXT,
    created_at      TEXT NOT NULL
);

CREATE INDEX idx_timeline_clips_timeline ON timeline_clips(timeline_id);
```

### 3.11 `ai_suggestions`

Pending and historical AI recommendations.

```sql
CREATE TABLE ai_suggestions (
    id                      TEXT PRIMARY KEY,
    project_id              TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    timeline_id             TEXT REFERENCES timelines(id) ON DELETE CASCADE,
    suggestion_type         TEXT NOT NULL,       -- clip_swap, cut_align, speed_change, etc.
    target_entity_id        TEXT,                -- clip or segment ID
    payload_json            TEXT NOT NULL,
    confidence              REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    reasoning               TEXT NOT NULL,
    expected_improvement    TEXT,
    status                  TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'accepted', 'rejected', 'expired')),
    agent_id                TEXT NOT NULL,
    created_at              TEXT NOT NULL,
    resolved_at             TEXT
);

CREATE INDEX idx_ai_suggestions_status ON ai_suggestions(project_id, status);
```

### 3.12 `analysis_jobs`

Background job tracking for all async work.

```sql
CREATE TABLE analysis_jobs (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    job_type        TEXT NOT NULL,               -- clip_analyze, music_analyze, style_analyze, timeline_generate, render
    target_id       TEXT,                        -- media_item_id, timeline_id, etc.
    status          TEXT NOT NULL DEFAULT 'queued'
                    CHECK (status IN ('queued', 'running', 'complete', 'failed', 'cancelled')),
    progress        REAL NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 1),
    message         TEXT,
    result_json     TEXT,
    error_message   TEXT,
    correlation_id  TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    started_at      TEXT,
    completed_at    TEXT
);

CREATE INDEX idx_analysis_jobs_status ON analysis_jobs(project_id, status);
```

### 3.13 `render_jobs`

Export/render job tracking.

```sql
CREATE TABLE render_jobs (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    timeline_id     TEXT NOT NULL REFERENCES timelines(id) ON DELETE CASCADE,
    output_path     TEXT NOT NULL,
    preset          TEXT NOT NULL DEFAULT 'h264_1080p60',
    status          TEXT NOT NULL DEFAULT 'queued',
    progress        REAL NOT NULL DEFAULT 0,
    ffmpeg_command  TEXT,
    stderr_log_path TEXT,
    output_duration_ms INTEGER,
    file_size_bytes INTEGER,
    error_message   TEXT,
    correlation_id  TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    started_at      TEXT,
    completed_at    TEXT
);
```

### 3.14 `chat_messages`

AI chat history for natural language editing.

```sql
CREATE TABLE chat_messages (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    timeline_id     TEXT REFERENCES timelines(id) ON DELETE SET NULL,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content         TEXT NOT NULL,
    commands_json   TEXT,                        -- parsed timeline commands executed
    created_at      TEXT NOT NULL
);

CREATE INDEX idx_chat_messages_project ON chat_messages(project_id, created_at);
```

### 3.15 `app_settings`

Global app settings (stored in separate `settings.db` at app data dir).

```sql
CREATE TABLE app_settings (
    key             TEXT PRIMARY KEY,
    value_json      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
```

## 4. JSON Schema References

| Column | Schema File |
|--------|-------------|
| `scenes_json` | `packages/shared-types/schemas/analysis.schema.json#/Scene` |
| `beat_map_json` | `packages/shared-types/schemas/analysis.schema.json#/BeatMap` |
| `payload_json` (suggestions) | `packages/shared-types/schemas/ai-suggestion.schema.json` |
| Timeline file | `packages/shared-types/schemas/timeline.schema.json` |

## 5. Migration Strategy

- Use **Alembic** (Python) for schema migrations.
- Migration files in `apps/backend/montage_backend/migrations/`.
- App checks `schema_version` in `projects.settings_json` on open.
- Forward-only migrations; backup prompt before destructive changes.

## 6. Query Patterns

| Use Case | Query |
|----------|-------|
| Top ranked clips | `SELECT * FROM clip_analysis JOIN media_items ... ORDER BY rank_score DESC LIMIT 50` |
| Clips with bombs | `SELECT DISTINCT media_item_id FROM game_events WHERE event_type='bomb' AND confidence > 0.75` |
| Pending suggestions | `SELECT * FROM ai_suggestions WHERE status='pending' ORDER BY confidence DESC` |
| Active jobs | `SELECT * FROM analysis_jobs WHERE status IN ('queued','running')` |

## 7. Backup & Recovery

- Auto-save writes both `project.db` and `main.timeline.json`
- WAL mode enabled: `PRAGMA journal_mode=WAL`
- Crash recovery: replay last WAL checkpoint + validate timeline JSON checksum
