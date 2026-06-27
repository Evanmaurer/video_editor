# Development Roadmap

**Product:** MontageAI  
**Version:** 1.0  
**Date:** 2026-06-26  
**Target v1.0 Release:** Q1 2027

---

## Roadmap Overview

```
2026 Q3          2026 Q4          2027 Q1
─────────────────────────────────────────────
 M0    M1    M2    M3    M4    M5    M6    M7    M8
 Design Shell  Media AI    AI    Time- NL    Render Beta  v1.0
              Import Clip  Music line  Edit        Release
                    Analysis      Planner
```

---

## Phase 0: Design (Current)

**Duration:** 2 weeks  
**Status:** In Progress

- Complete software design package (20 documents)
- Architecture review and approval
- No application code

**Exit criteria:** All Milestone 0 deliverables approved.

---

## Phase 1: Foundation (Milestones 1-2)

**Duration:** 6-8 weeks  
**Goal:** Working desktop app with media import and basic timeline

### Milestone 1: Application Shell (3 weeks)
- Electron app launches with dark theme UI
- Python backend spawns and connects
- Project create/open/save
- Panel layout (empty panels)
- Settings panel

### Milestone 2: Media Pipeline (3-5 weeks)
- Import clips, music, references
- Proxy and thumbnail generation
- Media library with grid/list views
- Basic metadata display
- Background job queue with progress

**User can:** Create project, import clips, browse media library.

---

## Phase 2: Intelligence (Milestones 3-4)

**Duration:** 6-8 weeks  
**Goal:** AI analysis pipeline producing ranked, annotated clips

### Milestone 3: Clip & Albion Analysis (4-5 weeks)
- Clip Analyzer agent (motion, scenes, excitement)
- Albion Event Analyzer (bombs, wipes, engagements)
- Analysis results in media library (scores, events)
- Filter and sort by score/event type
- AI suggestion card UI (display only)

### Milestone 4: Music & Style Analysis (2-3 weeks)
- Music Analyzer (BPM, beats, drops, energy)
- Style Analyzer (reference montage profiling)
- Beat markers on timeline ruler
- Music analysis visualization

**User can:** Import clips + music + references, analyze all, browse ranked clips with AI scores and event tags.

---

## Phase 3: Creation (Milestones 5-6)

**Duration:** 6-8 weeks  
**Goal:** AI-generated editable timeline with manual editing

### Milestone 5: Timeline Engine (4-5 weeks)
- Full timeline engine (tracks, clips, effects)
- Timeline UI (multi-track, drag-drop, trim, split)
- Preview playback (proxy)
- Undo/redo
- Snap to beats

### Milestone 6: AI Timeline Generation (2-3 weeks)
- Timeline Planner agent
- "Generate Timeline" workflow
- AI suggestions panel (accept/reject)
- AI metadata on clips (confidence, reasoning)

**User can:** Generate AI timeline, manually edit, accept/reject AI suggestions, preview montage.

---

## Phase 4: Polish (Milestones 7-8)

**Duration:** 6-8 weeks  
**Goal:** Export, NL editing, beta release

### Milestone 7: Export & AI Chat (3-4 weeks)
- FFmpeg render pipeline
- Export presets (H.264/H.265)
- Render queue
- AI Chat Assistant (NL timeline editing)
- Audio mixing basics

### Milestone 8: Beta & Release (3-4 weeks)
- Thumbnail agent
- Performance optimization
- E2E test suite
- Beta program with 5-10 creators
- Bug fixes from beta feedback
- v1.0 release

**User can:** Full workflow — import → analyze → generate → edit → chat → export.

---

## Post-v1.0 Roadmap (Future)

| Version | Features | Target |
|---------|----------|--------|
| v1.1 | Additional game plugin framework + second game | Q2 2027 |
| v1.2 | Full-res preview; hardware render acceleration | Q2 2027 |
| v1.3 | Batch project processing; template system | Q3 2027 |
| v2.0 | Cloud collaboration; team features | Q4 2027 |
| v2.1 | Motion graphics; text animation engine | Q1 2028 |

---

## Dependency Graph

```
M0 (Design)
 └── M1 (Shell)
      └── M2 (Media)
           ├── M3 (Clip/Albion AI)
           │    └── M5 (Timeline Engine)
           │         └── M6 (AI Timeline)
           │              └── M7 (Export/Chat)
           │                   └── M8 (Beta/Release)
           └── M4 (Music/Style AI)
                └── M6 (AI Timeline)
```

M3 and M4 can partially overlap after M2 is complete.

---

## Resource Estimate

| Milestone | Engineering Weeks | Key Skills |
|-----------|-------------------|------------|
| M0 | 2 | Architecture, design |
| M1 | 3 | Electron, React, Python, FastAPI |
| M2 | 4 | FFmpeg, media processing |
| M3 | 5 | OpenCV, OCR, game analysis |
| M4 | 3 | Audio signal processing |
| M5 | 5 | Timeline engine, complex UI |
| M6 | 3 | AI planning, algorithm design |
| M7 | 4 | FFmpeg rendering, NLP |
| M8 | 4 | QA, optimization, beta |
| **Total** | **~33 weeks** | |

Estimate assumes 1-2 full-time engineers.

---

## Success Gates

| Gate | Criteria | When |
|------|----------|------|
| G0 | Design package approved | End of M0 |
| G1 | App launches, project CRUD works | End of M1 |
| G2 | 100 clips imported with proxies in < 2 min | End of M2 |
| G3 | Albion bomb detection ≥ 70% precision | End of M3 |
| G4 | BPM detection within ±2 BPM on test tracks | End of M4 |
| G5 | Timeline editing with undo/redo, 50+ clips | End of M5 |
| G6 | AI timeline generated in < 2 min for 100 clips | End of M6 |
| G7 | Export 3-min 1080p60 in < 5 min; NL edit works | End of M7 |
| G8 | Beta NPS ≥ 30; zero P0 bugs | End of M8 |
