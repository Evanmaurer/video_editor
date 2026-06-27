# API Design

**Product:** MontageAI  
**Base URL:** `http://127.0.0.1:{port}/api/v1`  
**Auth:** Header `X-Montage-Token: {token}`  
**Version:** 1.0  
**Date:** 2026-06-26

---

## 1. Conventions

| Convention | Value |
|------------|-------|
| Format | JSON request/response bodies |
| IDs | UUID v4 strings |
| Timestamps | ISO 8601 UTC |
| Time durations | Milliseconds (integer) in API; seconds in FFmpeg internals |
| Errors | `{ "error": "CODE", "message": "...", "details": {} }` |
| Pagination | `?offset=0&limit=50` → `{ "items": [], "total": 247 }` |
| WebSocket | `ws://127.0.0.1:{port}/ws?token={token}` |

## 2. Health & System

### GET /health

```json
// Response 200
{
  "status": "ok",
  "version": "1.0.0",
  "models_loaded": true,
  "queue_depth": 3,
  "gpu_available": true
}
```

### GET /ready

```json
// Response 200
{ "status": "ready" }

// Response 503
{ "status": "loading", "message": "Loading CLIP model..." }
```

---

## 3. Projects

### POST /projects

Create a new project.

```json
// Request
{
  "name": "ZvZ_Montage_June",
  "root_path": "/Users/creator/Videos/Montages/ZvZ_June",
  "width": 1920,
  "height": 1080,
  "frame_rate": 60.0,
  "target_game": "albion",
  "settings": {
    "auto_analyze_on_import": true,
    "auto_generate_timeline": false
  }
}

// Response 201
{
  "id": "proj-uuid",
  "name": "ZvZ_Montage_June",
  "root_path": "/Users/creator/Videos/Montages/ZvZ_June",
  "width": 1920,
  "height": 1080,
  "frame_rate": 60.0,
  "target_game": "albion",
  "created_at": "2026-06-26T12:00:00Z",
  "updated_at": "2026-06-26T12:00:00Z"
}
```

### GET /projects/{project_id}

### PUT /projects/{project_id}

Update project settings.

### POST /projects/open

```json
// Request
{ "path": "/Users/creator/Videos/Montages/ZvZ_June" }

// Response 200
{ /* full project object */ }
```

### GET /projects/recent

```json
// Response 200
{
  "items": [
    {
      "id": "proj-uuid",
      "name": "ZvZ_Montage_June",
      "path": "/Users/creator/...",
      "updated_at": "2026-06-26T14:00:00Z"
    }
  ]
}
```

---

## 4. Media

### POST /projects/{project_id}/media/import

```json
// Request
{
  "paths": ["/path/to/clip1.mp4", "/path/to/clip2.mp4"],
  "role": "clip"
}

// Response 202
{
  "imported_count": 247,
  "skipped_count": 3,
  "errors": [
    { "path": "/path/to/corrupt.mp4", "error": "CORRUPT_FILE" }
  ],
  "job_ids": ["job-uuid-1", "job-uuid-2"]
}
```

**Roles:** `clip`, `music`, `reference`, `voice`, `other`

### GET /projects/{project_id}/media

Query parameters: `role`, `status`, `sort_by` (score|date|duration|name), `order`, `offset`, `limit`, `event_type`, `min_score`

```json
// Response 200
{
  "items": [
    {
      "id": "media-uuid",
      "file_name": "ZvZ_Bomb_03.mp4",
      "media_type": "video",
      "role": "clip",
      "duration_ms": 12400,
      "width": 1920,
      "height": 1080,
      "frame_rate": 60.0,
      "import_status": "ready",
      "proxy_path": "/project/media/proxies/media-uuid.mp4",
      "thumbnail_path": "/project/thumbnails/media-uuid.jpg",
      "analysis": {
        "excitement_score": 8.2,
        "motion_score": 7.1,
        "rank_score": 9.5,
        "confidence": 0.96,
        "reasoning": "Highest kill density in batch."
      },
      "events": [
        {
          "event_type": "bomb",
          "start_ms": 4200,
          "end_ms": 6800,
          "confidence": 0.96,
          "intensity": 9.8
        }
      ]
    }
  ],
  "total": 247
}
```

### GET /media/{media_item_id}

### DELETE /media/{media_item_id}

### GET /media/{media_item_id}/analysis

Full analysis result including raw JSON.

### GET /media/{media_item_id}/events

Game events for a clip.

---

## 5. Analysis

### POST /projects/{project_id}/analysis/start

```json
// Request
{
  "scope": "all",
  "include_clip_analysis": true,
  "include_albion_analysis": true,
  "include_music_analysis": true,
  "include_style_analysis": true,
  "media_item_ids": null
}
```

`scope`: `all` | `pending` | `selected` (requires `media_item_ids`)

```json
// Response 202
{
  "job_ids": ["job-uuid"],
  "estimated_duration_ms": 1800000
}
```

### GET /projects/{project_id}/analysis/rankings

```json
// Response 200
{
  "items": [
    {
      "media_item_id": "media-uuid",
      "file_name": "ZvZ_Bomb_03.mp4",
      "rank_score": 9.5,
      "excitement_score": 8.2,
      "bomb_score": 9.8,
      "confidence": 0.96,
      "reasoning": "...",
      "top_event": { "type": "bomb", "start_ms": 4200 }
    }
  ]
}
```

### GET /projects/{project_id}/music/analysis

Music analysis for primary track.

### GET /projects/{project_id}/style/profile

Style profile from reference montages.

---

## 6. Timelines

### POST /projects/{project_id}/timelines

Create empty timeline.

### GET /timelines/{timeline_id}

Returns full TimelineDocument JSON.

### PUT /timelines/{timeline_id}

Save timeline document.

```json
// Request: full TimelineDocument
// Response 200
{
  "id": "timeline-uuid",
  "version": 2,
  "updated_at": "2026-06-26T14:30:00Z"
}
```

### POST /timelines/generate

```json
// Request
{
  "project_id": "proj-uuid",
  "music_track_id": "music-uuid",
  "style_profile_id": "style-uuid",
  "target_duration_ms": 180000,
  "preferences": {
    "prioritize_bombs": true,
    "min_clip_duration_ms": 2000,
    "max_clip_duration_ms": 12000,
    "snap_to_beats": true,
    "include_slow_motion": false
  }
}

// Response 201
{
  "timeline": { /* TimelineDocument */ },
  "placements": [
    {
      "clip_id": "clip-uuid",
      "start_ms": 45000,
      "confidence": 0.96,
      "reasoning": "Highest kill density synchronized with music drop.",
      "expected_improvement": "+12% engagement score"
    }
  ],
  "overall_confidence": 0.89,
  "reasoning": "Generated 24-clip timeline synced to 4 music drops.",
  "job_id": "job-uuid"
}
```

### POST /timelines/{timeline_id}/edit

Apply structured edit commands (from chat or programmatic).

```json
// Request
{
  "commands": [
    {
      "type": "swap_clip",
      "target_clip_id": "clip-uuid",
      "new_media_item_id": "media-uuid",
      "snap_to_beat": true
    }
  ]
}

// Response 200
{
  "timeline": { /* updated TimelineDocument */ },
  "diff": {
    "moved": [],
    "added": [],
    "removed": [],
    "modified": [{ "clip_id": "clip-uuid", "changes": ["media_item_id"] }]
  }
}
```

---

## 7. AI Suggestions

### GET /projects/{project_id}/suggestions

Query: `status=pending`, `timeline_id`, `sort_by=confidence`

```json
// Response 200
{
  "items": [
    {
      "id": "sugg-uuid",
      "suggestion_type": "clip_swap",
      "confidence": 0.96,
      "reasoning": "Highest estimated kill density synchronized with the music drop.",
      "expected_improvement": "+12% engagement score vs current cut",
      "payload": {
        "target_time_ms": 45000,
        "recommended_media_item_id": "media-uuid",
        "bomb_score": 9.8
      },
      "status": "pending",
      "agent_id": "timeline-planner",
      "created_at": "2026-06-26T14:00:00Z"
    }
  ]
}
```

### POST /suggestions/{suggestion_id}/accept

### POST /suggestions/{suggestion_id}/reject

---

## 8. AI Chat

### POST /ai/chat

```json
// Request
{
  "project_id": "proj-uuid",
  "timeline_id": "timeline-uuid",
  "message": "Replace the clip at 0:45 with a better bomb",
  "context": {
    "playhead_ms": 45000,
    "selected_clip_id": null
  }
}

// Response 200
{
  "response": "Replaced clip at 0:45 with ZvZ_Bomb_03.mp4 (Bomb Score: 9.8, 96% confidence).",
  "commands": [
    { "type": "swap_clip", "target_time_ms": 45000, "new_media_item_id": "media-uuid" }
  ],
  "timeline": { /* updated TimelineDocument */ },
  "suggestions": [],
  "confidence": 0.96
}
```

### GET /projects/{project_id}/chat/history

Query: `timeline_id`, `limit=50`

---

## 9. Render

### POST /render

```json
// Request
{
  "timeline_id": "timeline-uuid",
  "output_path": "/Users/creator/Videos/exports/Montage_v1.mp4",
  "preset": "h264_1080p60",
  "mode": "export",
  "range_start_ms": null,
  "range_end_ms": null
}

// Response 202
{
  "job_id": "render-uuid",
  "status": "queued",
  "estimated_duration_ms": 300000
}
```

### GET /render/{job_id}

```json
// Response 200
{
  "id": "render-uuid",
  "status": "running",
  "progress": 0.67,
  "preset": "h264_1080p60",
  "output_path": "/Users/creator/Videos/exports/Montage_v1.mp4",
  "started_at": "2026-06-26T15:00:00Z"
}
```

### POST /render/{job_id}/cancel

### GET /render/presets

```json
// Response 200
{
  "presets": [
    {
      "id": "h264_1080p60",
      "label": "H.264 1080p 60fps",
      "codec": "libx264",
      "width": 1920,
      "height": 1080,
      "frame_rate": 60.0
    }
  ]
}
```

### GET /projects/{project_id}/render/jobs

List all render jobs for project.

---

## 10. Thumbnails

### POST /timelines/{timeline_id}/thumbnails/generate

```json
// Response 202
{
  "candidates": [
    {
      "id": "thumb-uuid",
      "frame_timestamp_ms": 45200,
      "source_clip_id": "clip-uuid",
      "score": 9.2,
      "confidence": 0.91,
      "reasoning": "Peak action frame with high contrast.",
      "preview_path": "/project/cache/thumb-uuid.jpg"
    }
  ]
}
```

### POST /thumbnails/{candidate_id}/render

```json
// Request
{ "output_path": "/path/to/thumbnail.jpg", "layers": [] }
```

---

## 11. Jobs

### GET /jobs/{job_id}

Generic job status endpoint.

```json
// Response 200
{
  "id": "job-uuid",
  "job_type": "clip_analyze",
  "status": "running",
  "progress": 0.78,
  "message": "Analyzing motion: frame 1350/3000",
  "created_at": "2026-06-26T14:00:00Z"
}
```

### POST /jobs/{job_id}/cancel

### GET /projects/{project_id}/jobs

Query: `status=running`, `job_type`

---

## 12. Settings

### GET /settings

App-level settings.

### PUT /settings

```json
// Request
{
  "default_project_path": "/Users/creator/Videos",
  "auto_save_interval_ms": 60000,
  "worker_count": 2,
  "gpu_enabled": true,
  "llm_provider": null,
  "llm_api_key": null
}
```

---

## 13. WebSocket Events

### Connection

```
ws://127.0.0.1:48291/ws?token=abc123
```

### Event Types

```typescript
// Job progress
{
  "type": "job.progress",
  "job_id": "job-uuid",
  "progress": 0.45,
  "message": "Analyzing motion: frame 1350/3000",
  "correlation_id": "corr-uuid"
}

// Job complete
{
  "type": "job.complete",
  "job_id": "job-uuid",
  "result": { /* job-specific result summary */ }
}

// Job failed
{
  "type": "job.failed",
  "job_id": "job-uuid",
  "error": "Analysis failed: out of memory",
  "correlation_id": "corr-uuid"
}

// Clip analysis complete
{
  "type": "analysis.clip_complete",
  "media_item_id": "media-uuid",
  "rank_score": 9.5
}

// New AI suggestion
{
  "type": "suggestion.new",
  "suggestion": { /* AISuggestion object */ }
}

// Render progress
{
  "type": "render.progress",
  "job_id": "render-uuid",
  "progress": 0.67,
  "eta_ms": 102000
}
```

---

## 14. Error Codes

| Code | HTTP | Description |
|------|------|-------------|
| `PROJECT_NOT_FOUND` | 404 | Project ID does not exist |
| `MEDIA_NOT_FOUND` | 404 | Media item not found |
| `TIMELINE_NOT_FOUND` | 404 | Timeline not found |
| `INVALID_MEDIA` | 400 | Unsupported codec or corrupt file |
| `ANALYSIS_FAILED` | 500 | Agent analysis error |
| `RENDER_FAILED` | 500 | FFmpeg render error |
| `JOB_NOT_FOUND` | 404 | Job ID not found |
| `JOB_CANCELLED` | 409 | Job was cancelled |
| `VALIDATION_ERROR` | 422 | Request validation failed |
| `UNAUTHORIZED` | 401 | Invalid or missing token |
| `DISK_FULL` | 507 | Insufficient disk space |
| `MODEL_NOT_LOADED` | 503 | Required AI model not available |

---

## 15. OpenAPI

Full OpenAPI 3.1 spec will be auto-generated from FastAPI at `/docs` (Swagger UI) and `/openapi.json` during Milestone 1 implementation.
