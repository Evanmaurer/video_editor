# Requirements Summary

This document consolidates functional and non-functional requirements. The authoritative detailed specification is in [01-prd.md](./01-prd.md).

## Functional Requirements (FR)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-001 | Create, open, save, and close projects | P0 |
| FR-002 | Import hundreds of gameplay video clips | P0 |
| FR-003 | Import one or more reference montage videos | P0 |
| FR-004 | Display media library with thumbnails and metadata | P0 |
| FR-005 | Analyze clips for scenes, motion, excitement | P0 |
| FR-006 | Detect Albion-specific events (bombs, wipes, loot, engagements) | P0 |
| FR-007 | Rank clips automatically with scores and explanations | P0 |
| FR-008 | Analyze music (BPM, beats, drops, energy curve) | P0 |
| FR-009 | Learn editing style from reference montages | P1 |
| FR-010 | Generate editable timeline (not fixed render) | P0 |
| FR-011 | Multi-track timeline with video, audio, effects | P0 |
| FR-012 | Real-time preview of timeline | P0 |
| FR-013 | Natural language timeline editing via AI chat | P1 |
| FR-014 | Export high-quality video (H.264/H.265) | P0 |
| FR-015 | AI suggestions panel with confidence + reasoning | P0 |
| FR-016 | Render queue with progress and cancellation | P1 |
| FR-017 | Settings (paths, AI models, export presets) | P1 |
| FR-018 | Auto-generate editable YouTube thumbnails | P2 |
| FR-019 | Audio mixing (game, music, voice, Discord) | P1 |
| FR-020 | Undo/redo for all timeline operations | P0 |

## Non-Functional Requirements (NFR)

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-001 | Desktop platform support | macOS 13+, Windows 10+ |
| NFR-002 | Import batch size | 500+ clips per project |
| NFR-003 | Timeline responsiveness | < 16ms UI frame budget for interactions |
| NFR-004 | Preview latency | < 200ms seek on proxy media |
| NFR-005 | Analysis throughput | Background; non-blocking UI |
| NFR-006 | Data durability | Auto-save every 60s; crash recovery |
| NFR-007 | AI transparency | 100% of suggestions include confidence + reason |
| NFR-008 | Offline capability | Core editing works offline; LLM optional local/cloud |
| NFR-009 | Test coverage (new code) | ≥ 80% unit; critical paths integration tested |
| NFR-0010 | Logging | Structured JSON logs with correlation IDs |

## Albion Online — Game-Specific Events

| Event | Detection Signals | Output |
|-------|-------------------|--------|
| Bomb | AoE visual, kill feed spike, ability UI | Timestamp, confidence, kill density estimate |
| Engagement | Sustained combat UI, health bar activity | Start/end, intensity score |
| Wipe | Mass death feed, grey screen | Timestamp, party size estimate |
| Loot explosion | Rare drop UI, gold counter animation | Timestamp, rarity estimate |
| Kill feed burst | OCR on kill feed region | Count, duration, confidence |

## Constraints

- Electron + React + TypeScript frontend
- Python backend for AI and media processing
- SQLite for project metadata
- FFmpeg for rendering
- No placeholder implementations in shipped milestones
