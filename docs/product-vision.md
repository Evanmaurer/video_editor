# Product Vision — MontageAI

## One-Line Vision

MontageAI is a professional desktop video editor that uses transparent, editable AI to help gamers turn hundreds of raw clips into polished montages — starting with Albion Online.

## Problem Statement

Creating a high-quality gaming montage is labor-intensive:

- Hundreds of hours of gameplay must be reviewed manually.
- Exciting moments are easy to miss or hard to rank consistently.
- Music sync, pacing, and style require expert editing skills.
- Existing AI tools produce opaque, non-editable outputs (rendered videos, not timelines).
- Game-specific events (Albion bombs, wipes, loot explosions) require domain knowledge.

Creators want **speed without losing control**.

## Solution

MontageAI combines a professional NLE-style interface (timeline, preview, inspector) with a fleet of specialized AI agents that:

1. Analyze every clip and detect exciting, game-specific moments.
2. Analyze music structure (beats, drops, energy).
3. Learn editing style from reference montages.
4. Generate an **editable timeline** with confidence scores and reasoning.
5. Accept natural language edits without regenerating everything.
6. Export broadcast-quality video.

Every AI decision is transparent, scored, and reversible.

## Target Users

| Persona | Description | Primary Need |
|---------|-------------|--------------|
| **Competitive Albion Creator** | Publishes weekly ZvZ / gank montages | Fast highlight extraction, bomb sync |
| **Casual Streamer** | Has 50+ hours of footage, limited editing time | Auto-ranking, music sync |
| **Editor-for-Hire** | Professional editor serving gaming clients | Style transfer, editable AI drafts |
| **Content Team Lead** | Manages multiple creators | Batch import, render queue, consistency |

## Value Proposition

| Traditional Workflow | MontageAI Workflow |
|---------------------|-------------------|
| Manual scrubbing of every clip | AI ranks clips with explanations |
| Guesswork on music sync | Beat map + drop-aligned cuts |
| Copy reference montage by eye | Style profile extracted automatically |
| Fixed AI output video | Fully editable timeline |
| Opaque AI decisions | Confidence + reasoning on every suggestion |

## Design Principles

1. **Transparency** — Every AI output includes confidence, reasoning, and expected improvement.
2. **Editability** — AI generates timeline data structures, never locked renders.
3. **User Sovereignty** — The user always has final control; AI proposes, user disposes.
4. **Incremental Quality** — Each milestone ships a working application.
5. **Maintainability** — Clean module boundaries; no placeholder systems.
6. **Game Extensibility** — Albion Online first; architecture supports future games via analyzer plugins.

## Success Metrics (Year 1)

| Metric | Target |
|--------|--------|
| Time from import to first editable timeline | < 30 min for 100 clips |
| User acceptance rate of AI timeline suggestions | > 60% kept without major rework |
| Export success rate | > 99% |
| Crash-free sessions | > 99.5% |
| NPS from beta creators | > 40 |

## Non-Goals (v1)

- Cloud rendering farm
- Real-time multiplayer editing
- Mobile app
- Live stream clipping during broadcast
- Support for games beyond Albion Online (architecture ready, implementation deferred)

## Long-Term Vision

MontageAI becomes the default montage editor for competitive gaming communities — a tool where AI handles the tedious 80% and creators focus on the creative 20%, with full visibility into every automated decision.
