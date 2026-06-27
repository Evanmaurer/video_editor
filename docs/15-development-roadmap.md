# Development Roadmap

**Product:** MontageAI  
**Version:** 1.1  
**Date:** 2026-06-27 (revised milestone plan)  
**Target v1.0 Release:** Q1 2027

---

## Roadmap Overview

```
2026 Q3          2026 Q4          2027 Q1
────────────────────────────────────────────────────────────
 M0    M1    M2 (6 sub)    M3      M4       M5      M6    M7
 Design Shell  Media Eng.  AI      AI       Albion  AI    Polish
               Library     Analysis Montage Intel   Asst  Release
               Timeline
               Playback
               Export
               AI Metadata
```

---

## Phase 0: Design (Complete)

**Duration:** 2 weeks  
**Status:** Complete (2026-06-26)

- Complete software design package (20 documents)
- Architecture review and approval

---

## Phase 1: Foundation (Milestone 1 — Complete)

**Duration:** 3 weeks  
**Status:** Complete (2026-06-27)

- Electron app with dark theme UI
- Python backend spawns and connects
- Project create/open/save/close
- Panel layout shell, settings panel

**User can:** Launch app, create/open projects, configure settings.

---

## Phase 2: Media Processing Engine (Milestone 2)

**Duration:** 8–12 weeks  
**Goal:** Complete editing engine — import, library, timeline, playback, export, AI metadata cache

Milestone 2 is delivered as six sequential sub-milestones. Each sub-milestone must be complete, tested, documented, and committed before the next begins.

| Sub-milestone | Focus |
|---------------|-------|
| M2-001 | FFmpeg, import, metadata, proxy, waveform, job queue |
| M2-002 | Media library UI |
| M2-003 | Timeline engine + UI |
| M2-004 | Playback engine |
| M2-005 | Export engine |
| M2-006 | AI metadata cache |

**User can (after M2):** Import clips, browse library, edit timeline, preview, export video.

---

## Phase 3: AI Analysis (Milestone 3)

**Duration:** 4–6 weeks  
**Goal:** Clip analysis pipeline producing ranked, indexed media

- Clip analysis, OCR, object detection, scene understanding
- Motion analysis, audio analysis, CLIP embeddings, semantic indexing
- Analysis results flow into AI metadata cache

**User can:** Analyze imported clips; browse by score, tags, and semantic search.

---

## Phase 4: AI Montage Generation (Milestone 4)

**Duration:** 3–5 weeks  
**Goal:** AI-generated editable montages

- Highlight selection, music sync, beat detection, pacing
- Transitions, effects, camera shake detection
- "Generate Timeline" workflow with accept/reject suggestions

**User can:** Generate AI montage from analyzed clips and music; manually refine.

---

## Phase 5: Albion Intelligence (Milestone 5)

**Duration:** 4–5 weeks  
**Goal:** Game-specific Albion Online detection and scoring

- Albion OCR, kill/bomb/cooldown detection, party status
- Battle timeline extraction, engagement scoring
- Calibration wizard and UI templates

**User can:** Filter and rank Albion clips by game events (bombs, kills, wipes, etc.).

---

## Phase 6: AI Assistant (Milestone 6)

**Duration:** 3–4 weeks  
**Goal:** Natural language editing and montage creation

- Chat assistant with project context
- NL timeline edits (undoable)
- Generate complete montages from instructions

**User can:** Edit via chat; ask questions; generate montages from prompts.

---

## Phase 7: Polish & Production (Milestone 7)

**Duration:** 4–6 weeks  
**Goal:** v1.0 release

- Performance optimization, profiling
- Installers (macOS + Windows), updater, crash reporting
- E2E test suite, documentation, beta program
- v1.0 release

**User can:** Full production workflow with stable installers.

---

## Post-v1.0 Roadmap (Future)

| Version | Features | Target |
|---------|----------|--------|
| v1.1 | Additional game plugin framework + second game | Q2 2027 |
| v1.2 | Full-res preview; hardware render acceleration | Q2 2027 |
| v1.3 | Batch project processing; template system | Q3 2027 |
| v2.0 | Cloud collaboration; team features | Q4 2027 |

---

## Dependency Graph

```
M0 (Design)
 └── M1 (Shell) ✓
      └── M2-001 → M2-002 → M2-003 → M2-004 → M2-005 → M2-006
            └── M3 (AI Analysis)
                 └── M4 (AI Montage Generation)
                      └── M5 (Albion Intelligence)
                           └── M6 (AI Assistant)
                                └── M7 (Polish & Production)
```

---

## Milestone Gates

| Gate | Criteria | When |
|------|----------|------|
| G0 | Design package approved | End of M0 ✓ |
| G1 | App launches, project CRUD works | End of M1 ✓ |
| G2 | Import + library + timeline + playback + export | End of M2 |
| G3 | 100 clips analyzed with semantic index | End of M3 |
| G4 | AI montage generated in < 2 min | End of M4 |
| G5 | Albion bomb detection ≥ 70% precision | End of M5 |
| G6 | NL chat edits timeline; generates montage | End of M6 |
| G7 | Beta NPS ≥ 30; v1.0 released | End of M7 |

---

## Approval Workflow

At the completion of **each milestone** (M2–M7):

1. Stop implementation
2. Summarize completed work
3. Update `PROJECT_STATE.md`
4. **Wait for stakeholder approval** before starting the next milestone

Within Milestone 2, each **sub-milestone** (M2-001–M2-006) must be complete, tested, documented, and committed before the next sub-milestone begins.

---

## Resource Estimate

| Milestone | Engineering Weeks | Key Skills |
|-----------|-------------------|------------|
| M0 | 2 | Architecture, design |
| M1 | 3 | Electron, React, Python, FastAPI |
| M2 | 10 | FFmpeg, media, timeline, playback, export |
| M3 | 5 | OpenCV, ML, audio, CLIP |
| M4 | 4 | AI planning, music sync |
| M5 | 5 | Game analysis, OCR, Albion |
| M6 | 4 | LLM, NLP, editing agents |
| M7 | 5 | QA, packaging, optimization |
| **Total** | **~38 weeks** | |

Estimate assumes 1–2 full-time engineers.
