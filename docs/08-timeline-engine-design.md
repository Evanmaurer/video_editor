# Timeline Engine Design

**Product:** MontageAI  
**Version:** 1.0  
**Date:** 2026-06-26

---

## 1. Overview

The Timeline Engine is the core data structure and mutation system for MontageAI. It manages the editable timeline document — the central artifact that AI generates and users edit. The engine runs primarily in the frontend (for responsive interactions) with backend persistence.

**Key principle:** The timeline is a JSON document, not a rendered video. All AI output targets this document.

## 2. Timeline Document Schema

```json
{
  "$schema": "timeline.schema.json",
  "id": "uuid",
  "project_id": "uuid",
  "name": "Main",
  "version": 1,
  "settings": {
    "width": 1920,
    "height": 1080,
    "frame_rate": 60.0,
    "sample_rate": 48000
  },
  "duration_ms": 180000,
  "tracks": [],
  "markers": [],
  "beat_markers": [],
  "metadata": {
    "ai_generated": true,
    "generator": "timeline-planner-v1.0.0",
    "generated_at": "2026-06-26T12:00:00Z"
  }
}
```

## 3. Track Model

```typescript
interface Track {
  id: string;
  type: 'video' | 'audio' | 'overlay' | 'subtitle';
  name: string;
  index: number;
  muted: boolean;
  locked: boolean;
  visible: boolean;
  clips: Clip[];
  volume: number;           // 0.0 - 1.0 (audio tracks)
}
```

**Default track layout (AI-generated):**

| Index | Type | Name | Content |
|-------|------|------|---------|
| 0 | video | Video 1 | Gameplay clips |
| 1 | audio | Music | Background music |
| 2 | audio | Game Audio | In-game sounds from clips |
| 3 | audio | Voice | Discord/voice comms |
| 4 | overlay | Effects | Text, borders, flashes |
| 5 | subtitle | Subtitles | Auto-generated captions |

## 4. Clip Model

```typescript
interface Clip {
  id: string;
  media_item_id: string;
  track_id: string;

  // Timeline position
  start_ms: number;         // position on timeline
  end_ms: number;           // end position on timeline (computed from duration / speed)

  // Source media range
  source_in_ms: number;     // in-point in source media
  source_out_ms: number;    // out-point in source media

  // Playback
  speed: number;            // 1.0 = normal, 0.5 = half speed, 2.0 = double

  // Visual
  opacity: number;          // 0.0 - 1.0
  scale: number;            // 1.0 = full frame
  position: { x: number; y: number };
  rotation: number;         // degrees

  // Effects & keyframes
  effects: Effect[];
  keyframes: Keyframe[];

  // Transitions
  transition_in: Transition | null;
  transition_out: Transition | null;

  // AI metadata
  ai: AIMetadata | null;
}

interface AIMetadata {
  generated: boolean;
  confidence: number;
  reasoning: string;
  expected_improvement: string | null;
  agent_id: string;
  agent_version: string;
}
```

## 5. Effect Model

```typescript
interface Effect {
  id: string;
  type: EffectType;
  enabled: boolean;
  parameters: Record<string, number | string | boolean>;
}

type EffectType =
  | 'speed_ramp'
  | 'zoom'
  | 'color_grade'
  | 'motion_blur'
  | 'flash'
  | 'shake'
  | 'vignette'
  | 'text_overlay';

interface Keyframe {
  time_ms: number;          // relative to clip start
  property: string;         // "scale", "opacity", "position.x", etc.
  value: number;
  easing: 'linear' | 'ease_in' | 'ease_out' | 'ease_in_out';
}
```

## 6. Transition Model

```typescript
interface Transition {
  type: 'cut' | 'fade' | 'dip_to_black' | 'flash' | 'zoom' | 'wipe';
  duration_ms: number;
  parameters: Record<string, unknown>;
}
```

## 7. Marker Model

```typescript
interface Marker {
  id: string;
  time_ms: number;
  label: string;
  color: string;
  type: 'user' | 'beat' | 'drop' | 'event';
}

interface BeatMarker extends Marker {
  type: 'beat';
  strength: number;
}
```

## 8. Timeline Engine API

```typescript
class TimelineEngine {
  constructor(document: TimelineDocument);

  // --- Queries ---
  getDocument(): TimelineDocument;
  getDuration(): number;
  getTrack(trackId: string): Track | undefined;
  getClip(clipId: string): Clip | undefined;
  getClipsAtTime(timeMs: number): Clip[];
  getClipAtTrackTime(trackId: string, timeMs: number): Clip | undefined;

  // --- Mutations (via Command pattern) ---
  execute(command: TimelineCommand): void;
  undo(): boolean;
  redo(): boolean;
  canUndo(): boolean;
  canRedo(): boolean;

  // --- Serialization ---
  toJSON(): TimelineDocument;
  static fromJSON(json: TimelineDocument): TimelineEngine;

  // --- Validation ---
  validate(): ValidationResult;

  // --- Listeners ---
  onChange(callback: (event: TimelineChangeEvent) => void): () => void;
}
```

## 9. Command Pattern

All mutations are commands for undo/redo support.

```typescript
interface TimelineCommand {
  execute(engine: TimelineEngine): void;
  undo(engine: TimelineEngine): void;
  description: string;
}

// Built-in commands
class AddClipCommand implements TimelineCommand { ... }
class RemoveClipCommand implements TimelineCommand { ... }
class MoveClipCommand implements TimelineCommand { ... }
class TrimClipCommand implements TimelineCommand { ... }
class SplitClipCommand implements TimelineCommand { ... }
class SetClipSpeedCommand implements TimelineCommand { ... }
class AddEffectCommand implements TimelineCommand { ... }
class SwapClipCommand implements TimelineCommand { ... }
class ApplyTransitionCommand implements TimelineCommand { ... }
class BatchCommand implements TimelineCommand { ... }  // atomic multi-command
```

**Example:**
```typescript
engine.execute(new MoveClipCommand({
  clipId: 'clip-abc',
  newStartMs: 45000,
  snapToBeat: true,
  beatMap: musicAnalysis.beat_map,
}));
```

## 10. Snap System

```typescript
class SnapEngine {
  constructor(beatMap: BeatMap | null, markers: Marker[]);

  snap(timeMs: number, options: SnapOptions): number;

  interface SnapOptions {
    threshold_ms: number;     // default 50ms
    snapToBeats: boolean;
    snapToMarkers: boolean;
    snapToClips: boolean;       // snap to adjacent clip edges
  }
}
```

When `snapToBeats` is enabled, clip boundaries snap to nearest beat within threshold. Drop markers have stronger snap (2x threshold).

## 11. Conflict Detection

```typescript
interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
}

// Rules:
// - Clips on same track must not overlap (error)
// - source_out_ms must not exceed media duration (error)
// - speed must be > 0 (error)
// - clip extending past timeline duration (warning)
// - gap between clips on same track (warning, optional auto-close)
```

## 12. AI Timeline Generation Flow

```
TimelinePlannerAgent output
    → TimelineDocument JSON
    → Backend TimelineService.save()
    → Frontend TimelineEngine.fromJSON()
    → timelineStore sync
    → UI renders tracks/clips
```

Each AI-placed clip has populated `ai` metadata:

```json
{
  "ai": {
    "generated": true,
    "confidence": 0.96,
    "reasoning": "Highest estimated kill density synchronized with the music drop.",
    "expected_improvement": "+12% engagement score vs random placement",
    "agent_id": "timeline-planner",
    "agent_version": "1.0.0"
  }
}
```

## 13. Natural Language Edit Flow

```
User message → ChatAssistant → EditCommand[] → TimelineEngine.execute(BatchCommand)
```

Chat assistant produces structured commands, not raw timeline JSON. This ensures:
- Individual edits are undoable
- Changes are auditable
- Partial edits don't corrupt the timeline

## 14. Auto-Save

```typescript
// Debounced save (2s after last change)
const debouncedSave = debounce(async (doc: TimelineDocument) => {
  await apiClient.saveTimeline(doc.id, doc);
}, 2000);

engine.onChange(() => {
  debouncedSave(engine.toJSON());
});
```

## 15. Timeline ↔ Render Graph

The render pipeline reads the timeline document and builds an FFmpeg filter graph. See [09-rendering-pipeline-design.md](./09-rendering-pipeline-design.md).

Mapping:
- Each video clip → FFmpeg input segment with trim + speed
- Transitions → xfade filter between segments
- Effects → per-clip filter chains
- Audio clips → amix with volume/keyframe automation

## 16. Performance Considerations

| Concern | Strategy |
|---------|----------|
| 500+ clips | Lazy track rendering; virtualize off-screen clips |
| Undo stack memory | Store command diffs, not full snapshots; limit to 100 entries |
| Validation | Run on save, not every keystroke |
| Beat markers | Pre-computed; stored in timeline document |

## 17. Timeline Diff (for AI Chat)

When AI modifies the timeline, generate a human-readable diff:

```typescript
interface TimelineDiff {
  added: Clip[];
  removed: Clip[];
  moved: { clip: Clip; oldStart: number; newStart: number }[];
  modified: { clip: Clip; changes: PropertyChange[] }[];
}
```

Displayed in chat response: "Moved 3 clips, replaced 1 clip, adjusted speed on 2 clips."

## 18. Future Extensions

- **Nested sequences** — Clips containing sub-timelines (v2)
- **Multi-cam** — Sync multiple POV tracks (v2)
- **Compound clips** — Group clips into reusable units (v2)
- **Real-time collaboration** — CRDT-based timeline sync (v3)
