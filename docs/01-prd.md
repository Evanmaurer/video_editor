# Product Requirements Document (PRD)

**Product:** MontageAI  
**Version:** 1.0 (Milestone 0)  
**Date:** 2026-06-26  
**Status:** Draft — Awaiting Approval

---

## 1. Executive Summary

MontageAI is a professional desktop video editor for creating AI-assisted gaming montages. Unlike tools that output finished videos, MontageAI generates **editable timelines** where every AI decision includes a confidence score, reasoning, and expected improvement. Albion Online is the first supported game.

## 2. Goals & Objectives

### 2.1 Business Goals

- Reduce montage creation time by 70% for target creators.
- Establish MontageAI as the category leader in transparent AI video editing.
- Build an extensible platform for additional games post-v1.

### 2.2 Product Goals

- Ship a working desktop app at every milestone.
- Achieve creator trust through AI transparency.
- Match core NLE usability expectations (timeline, preview, export).

## 3. User Personas

### 3.1 Kael — Competitive Albion Creator

- **Age:** 24 | **Platform:** YouTube, Twitch clips
- **Pain:** 200+ clips per week; manual bomb identification takes hours
- **Goal:** Publish weekly ZvZ montage synced to music drops
- **Success:** First editable timeline in under 30 minutes

### 3.2 Morgan — Casual Streamer

- **Age:** 19 | **Platform:** TikTok, YouTube Shorts
- **Pain:** No editing experience; doesn't know what makes a good cut
- **Goal:** Turn VODs into montages with minimal learning curve
- **Success:** Accepts 60%+ of AI suggestions without manual rework

### 3.3 Riley — Professional Editor

- **Age:** 31 | **Platform:** Freelance for gaming orgs
- **Pain:** Clients send reference montages; replicating style is tedious
- **Goal:** Generate style-matched draft timelines for client refinement
- **Success:** Style profile captures pacing and transition patterns accurately

## 4. User Stories

### 4.1 Project Management

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-001 | As a creator, I want to create a new project so I can organize my montage work | Project wizard collects name, resolution, frame rate; creates folder structure |
| US-002 | As a creator, I want to open existing projects so I can continue editing | Recent projects list; full state restored |
| US-003 | As a creator, I want auto-save so I don't lose work | Saves every 60s; recovery on crash |

### 4.2 Media Import & Library

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-010 | As a creator, I want to import hundreds of clips at once | Drag-drop folder; progress bar; duplicate detection |
| US-011 | As a creator, I want to import reference montages | Tagged as reference; excluded from clip pool by default |
| US-012 | As a creator, I want to see clip thumbnails and scores | Grid/list view; sort by AI score, date, duration |
| US-013 | As a creator, I want to filter clips by event type | Filter: bomb, wipe, engagement, loot, high motion |

### 4.3 AI Analysis

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-020 | As a creator, I want clips analyzed automatically on import | Background queue; status per clip |
| US-021 | As a creator, I want Albion events detected with timestamps | Events listed per clip with confidence |
| US-022 | As a creator, I want music analyzed for beats and drops | Beat map visualized; BPM displayed |
| US-023 | As a creator, I want style learned from reference montages | Style profile generated with pacing metrics |
| US-024 | As a creator, I want to see why AI ranked a clip highly | Score breakdown with reasoning text |

### 4.4 Timeline & Editing

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-030 | As a creator, I want AI to generate an editable timeline | Multi-track timeline populated from ranked clips |
| US-031 | As a creator, I want to drag clips onto the timeline manually | Standard NLE drag-drop behavior |
| US-032 | As a creator, I want to trim, split, and move clips | Keyboard shortcuts; snap to beats |
| US-033 | As a creator, I want to preview the timeline in real time | Play/pause/seek; audio sync |
| US-034 | As a creator, I want to edit via natural language | Chat commands modify timeline; changes are undoable |
| US-035 | As a creator, I want undo/redo for all edits | Unlimited undo stack within session |

### 4.5 AI Suggestions

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-040 | As a creator, I want AI to suggest better clip placements | Suggestion card: confidence, reason, expected improvement |
| US-041 | As a creator, I want to accept or reject suggestions | One-click accept/reject; preview before apply |
| US-042 | As a creator, I want to see all pending suggestions | Panel lists suggestions sorted by confidence |

### 4.6 Export & Render

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-050 | As a creator, I want to export high-quality video | H.264/H.265; configurable resolution/bitrate |
| US-051 | As a creator, I want a render queue | Multiple jobs; progress; cancel |
| US-052 | As a creator, I want YouTube-ready thumbnails | Auto-generated; editable in inspector |

### 4.7 Audio

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-060 | As a creator, I want music synced to cuts | Cuts snap to beat map |
| US-061 | As a creator, I want balanced audio levels | Separate tracks for game, music, voice, Discord |

## 5. Feature Specifications

### 5.1 Clip Analyzer

**Input:** Video file (any supported codec)  
**Output:** Structured metadata JSON

| Field | Type | Description |
|-------|------|-------------|
| `scenes` | `Scene[]` | Scene boundaries with timestamps |
| `motion_score` | `float 0-10` | Aggregate motion intensity |
| `downtime_segments` | `Segment[]` | Low-activity periods |
| `camera_movement` | `enum` | static, pan, zoom, shake |
| `ocr_text` | `OCRResult[]` | Detected on-screen text |
| `excitement_score` | `float 0-10` | Composite excitement rating |
| `confidence` | `float 0-1` | Overall analysis confidence |
| `reasoning` | `string` | Human-readable summary |

### 5.2 Albion Event Analyzer

**Input:** Video file + clip metadata  
**Output:** Game event array

| Event Type | Min Confidence Threshold | Key Signals |
|------------|-------------------------|-------------|
| `bomb` | 0.75 | AoE circle, kill feed spike ≥ 3 |
| `engagement` | 0.70 | Sustained combat UI ≥ 5s |
| `wipe` | 0.80 | ≥ 5 deaths in 3s window |
| `loot_explosion` | 0.65 | Rare item UI, loot fan animation |
| `kill_feed_burst` | 0.70 | OCR kill count ≥ 4 in 2s |

### 5.3 Music Analyzer

**Input:** Audio file (mp3, wav, flac, aac)  
**Output:** Beat map + energy curve

| Field | Type | Description |
|-------|------|-------------|
| `bpm` | `float` | Detected tempo |
| `beats` | `Timestamp[]` | Beat positions in seconds |
| `drops` | `Timestamp[]` | Energy drop/peak positions |
| `choruses` | `Segment[]` | Chorus sections |
| `energy_curve` | `float[]` | Normalized energy per 100ms |
| `confidence` | `float 0-1` | BPM detection confidence |

### 5.4 Style Analyzer

**Input:** Reference montage video(s)  
**Output:** Style profile

| Metric | Description |
|--------|-------------|
| `avg_clip_duration` | Mean clip length in seconds |
| `cut_frequency` | Cuts per minute |
| `transition_types` | Distribution: cut, fade, flash, zoom |
| `slow_motion_usage` | Percentage of timeline at < 1x speed |
| `replay_usage` | Percentage of clips shown as replay |
| `color_grade` | LUT approximation parameters |
| `pacing_curve` | Energy over timeline duration |

### 5.5 Timeline Planner

**Input:** Ranked clips, beat map, style profile, target duration  
**Output:** Timeline document (editable JSON)

Each clip placement includes:
- Source clip ID and in/out points
- Track assignment
- Transition to next clip
- Speed multiplier
- AI confidence, reasoning, expected improvement

### 5.6 AI Chat Assistant

**Supported commands (v1):**

| Command Pattern | Action |
|----------------|--------|
| "Replace [clip/time] with [clip]" | Swap clip on timeline |
| "Make the intro faster" | Reduce intro segment durations |
| "Remove slow motion" | Reset speed to 1x on affected clips |
| "Add more bombs" | Insert highest-scored bomb clips |
| "Sync cuts to drops" | Realign cuts to music drops |
| "Shorten to [duration]" | Trim timeline to target length |

All commands produce undoable timeline mutations with explanation.

## 6. UI Requirements

See [10-ui-wireframes.md](./10-ui-wireframes.md) and [ui-ux-design.md](./ui-ux-design.md).

**Layout regions (fixed):**

1. Menu Bar
2. Toolbar
3. Media Library (left panel)
4. Preview Window (center-top)
5. Timeline (center-bottom)
6. Inspector (right-top)
7. AI Suggestions Panel (right-bottom)
8. AI Chat (dockable)
9. Render Queue (dockable)

**Theme:** Dark professional (inspired by DaVinci Resolve / Premiere Pro)

## 7. Data Requirements

- Project files stored locally in user-chosen directory
- SQLite database per project for metadata and analysis results
- Proxy media generated for smooth preview
- Original media never modified

## 8. Performance Requirements

| Operation | Target |
|-----------|--------|
| App cold start | < 5s |
| Import 100 clips (metadata only) | < 60s |
| Clip analysis (1 min footage, GPU) | < 30s |
| Timeline generation (100 clips) | < 2 min |
| Preview seek (proxy) | < 200ms |
| Export 3 min 1080p60 | < 5 min (hardware dependent) |

## 9. Security & Privacy

- All processing local by default
- Optional cloud LLM requires explicit opt-in
- No telemetry without consent
- Project media never uploaded unless user initiates cloud feature

## 10. Platform Support

| Platform | Version | Priority |
|----------|---------|----------|
| macOS | 13 Ventura+ | P0 |
| Windows | 10/11 | P0 |
| Linux | — | Out of scope v1 |

## 11. Out of Scope (v1)

- Cloud collaboration
- Mobile companion app
- Live clipping during stream
- Games other than Albion Online
- Motion graphics / After Effects integration
- Stock footage library

## 12. Release Criteria (v1.0)

- [ ] All P0 user stories complete
- [ ] Albion event detection ≥ 80% precision on validation set
- [ ] Timeline export produces valid H.264 MP4
- [ ] Zero P0 bugs open
- [ ] E2E test: import → analyze → generate timeline → export passes
- [ ] Documentation complete and reviewed

## 13. Open Questions

| # | Question | Resolution |
|---|----------|------------|
| OQ-1 | Local LLM vs cloud API for chat assistant? | **Resolved:** Provider abstraction supporting Ollama (default), OpenAI, and none. Model selectable in Settings. Default local: Qwen3 8B Instruct; fallback: Llama 3.2 3B on low-end hardware. |
| OQ-2 | GPU requirement for analysis? | **Resolved:** GPU optional. Auto-detect hardware; CPU fallback with performance warning. App fully functional in CPU-only mode. |
| OQ-3 | Albion UI region templates for OCR? | **Resolved:** Data-driven template system with multiple resolution/scale presets, calibration wizard, and extensible YAML configs. See `ai/plugins/albion/`. |

## 14. Appendix: AI Suggestion Card Format

```
┌─────────────────────────────────────────┐
│ Bomb Score: 9.8                         │
│ Confidence: 96%                         │
│                                         │
│ Reason:                                 │
│ Highest estimated kill density          │
│ synchronized with the music drop.       │
│                                         │
│ Expected Improvement:                   │
│ +12% engagement score vs current cut    │
│                                         │
│ [Preview]  [Accept]  [Reject]           │
└─────────────────────────────────────────┘
```
