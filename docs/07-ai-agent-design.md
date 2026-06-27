# AI Agent Design

**Product:** MontageAI  
**Version:** 1.0  
**Date:** 2026-06-26

---

## 1. Design Philosophy

Every AI agent in MontageAI follows these rules:

1. **Structured output** — All results are typed Pydantic models, never raw strings.
2. **Confidence + reasoning** — Every decision includes `confidence: float [0,1]` and `reasoning: str`.
3. **Independence** — Agents are loosely coupled; communicate via orchestrator, not directly.
4. **Idempotency** — Re-running analysis on the same input produces equivalent results (within model variance).
5. **Graceful degradation** — Low confidence results are returned, not discarded; user decides.
6. **No side effects** — Agents read media and metadata; persistence is the service layer's job.

## 2. Agent Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      AI Engine (Orchestrator)                │
│  - Agent registry                                            │
│  - Pipeline composition                                      │
│  - Model loading/unloading                                   │
│  - Resource management (GPU/CPU)                             │
└──────────┬──────────┬──────────┬──────────┬────────────────┘
           │          │          │          │
    ┌──────▼───┐ ┌────▼────┐ ┌───▼────┐ ┌───▼────────┐
    │  Clip    │ │ Albion  │ │ Music  │ │ Style      │
    │ Analyzer │ │ Analyzer│ │Analyzer│ │ Analyzer   │
    └──────────┘ └─────────┘ └────────┘ └────────────┘
           │                              │
    ┌──────▼──────────────────────────────▼────────┐
    │              Timeline Planner                 │
    └──────────────────┬───────────────────────────┘
                       │
    ┌──────────────────▼───────────────────────────┐
    │  Editing Agent │ Audio Agent │ Thumbnail Agent│
    └──────────────────┬───────────────────────────┘
                       │
              ┌────────▼────────┐
              │ Chat Assistant  │
              └─────────────────┘
```

## 3. Base Agent Interface

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel

class AgentResult(BaseModel):
    agent_id: str
    agent_version: str
    confidence: float          # 0.0 - 1.0
    reasoning: str
    data: dict                   # Agent-specific payload
    processing_time_ms: int

class BaseAgent(ABC):
    agent_id: str
    agent_version: str

    @abstractmethod
    async def analyze(self, input: AgentInput) -> AgentResult: ...

    @abstractmethod
    def get_required_models(self) -> list[str]: ...

    async def warmup(self) -> None: ...
    async def shutdown(self) -> None: ...
```

## 4. Agent Specifications

### 4.1 Clip Analyzer Agent

**ID:** `clip-analyzer`  
**Version:** `1.0.0`

**Purpose:** General-purpose video clip analysis — scenes, motion, downtime, camera movement, OCR, excitement scoring.

**Input:**
```python
class ClipAnalyzerInput(AgentInput):
    media_item_id: str
    video_path: Path          # proxy preferred
    sample_fps: float = 2.0   # frames per second to analyze
```

**Output (`ClipAnalyzerOutput`):**
```python
class Scene(BaseModel):
    start_ms: int
    end_ms: int
    label: str                # "combat", "travel", "menu", "unknown"

class ClipAnalyzerOutput(BaseModel):
    scenes: list[Scene]
    motion_score: float       # 0-10
    downtime_segments: list[Segment]
    camera_movement: Literal["static", "pan", "zoom", "shake", "mixed"]
    ocr_results: list[OCRResult]
    excitement_score: float   # 0-10
    rank_score: float         # 0-10 composite
```

**Pipeline stages:**
1. **Frame sampling** — Extract frames at `sample_fps` via PyAV
2. **Scene detection** — Histogram delta + CLIP embedding clustering
3. **Motion analysis** — OpenCV optical flow magnitude → motion score
4. **Downtime detection** — Segments where motion < threshold for > 3s
5. **Camera movement** — Classify from optical flow patterns
6. **OCR** — EasyOCR on sampled frames; deduplicate text
7. **Excitement scoring** — Weighted composite:
   - Motion score (30%)
   - Scene transition rate (20%)
   - Audio energy if available (20%)
   - OCR activity (kill feed text changes) (30%)

**Models:**
- CLIP ViT-B/32 (ONNX) — scene embedding
- EasyOCR — text detection

**Confidence calculation:**
```
confidence = min(scene_detection_confidence, motion_analysis_confidence, ocr_coverage)
```

---

### 4.2 Albion Event Analyzer Agent

**ID:** `albion-analyzer`  
**Version:** `1.0.0`  
**Plugin:** `ai/plugins/albion/`

**Purpose:** Detect Albion Online-specific gameplay events.

**Input:**
```python
class AlbionAnalyzerInput(AgentInput):
    media_item_id: str
    video_path: Path
    clip_analysis: ClipAnalyzerOutput  # from Clip Analyzer
    ui_template: AlbionUITemplate        # screen region definitions
```

**Output:**
```python
class GameEvent(BaseModel):
    event_type: Literal["bomb", "engagement", "wipe", "loot_explosion", "kill_feed_burst"]
    start_ms: int
    end_ms: int
    confidence: float
    intensity: float          # 0-10
    reasoning: str
    metadata: dict          # event-specific data

class AlbionAnalyzerOutput(BaseModel):
    events: list[GameEvent]
    bomb_score: float         # 0-10 highest bomb moment
    engagement_count: int
```

**Detectors:**

| Detector | Method | Key Features |
|----------|--------|--------------|
| `BombDetector` | Template match + kill feed OCR spike | AoE circle color, radial pattern, ≥3 kills in 2s |
| `EngagementDetector` | Sustained UI activity | Health bars visible, combat UI active ≥5s |
| `WipeDetector` | Kill feed mass death | ≥5 kill events in 3s window |
| `LootDetector` | Rare item UI template | Gold/rarity color detection, loot fan animation |
| `KillFeedDetector` | OCR on kill feed region | Count transitions, name parsing |

**UI Template (`config.yaml`):**
```yaml
regions:
  kill_feed:
    x: 0.78
    y: 0.05
    width: 0.20
    height: 0.40
  health_bar:
    x: 0.40
    y: 0.90
    width: 0.20
    height: 0.05
  ability_bar:
    x: 0.35
    y: 0.85
    width: 0.30
    height: 0.10
thresholds:
  bomb_min_kills: 3
  bomb_kill_window_ms: 2000
  wipe_min_deaths: 5
  wipe_window_ms: 3000
  engagement_min_duration_ms: 5000
```

**Models:**
- Custom bomb detector (fine-tuned on Albion screenshots) — future
- v1: Heuristic + OCR + motion spike

---

### 4.3 Music Analyzer Agent

**ID:** `music-analyzer`  
**Version:** `1.0.0`

**Purpose:** Analyze music tracks for BPM, beats, drops, choruses, and energy curves.

**Input:**
```python
class MusicAnalyzerInput(AgentInput):
    music_track_id: str
    audio_path: Path
```

**Output:**
```python
class Beat(BaseModel):
    time_ms: int
    strength: float           # 0-1

class Drop(BaseModel):
    time_ms: int
    intensity: float          # 0-1
    type: Literal["build", "drop", "breakdown"]

class MusicAnalyzerOutput(BaseModel):
    bpm: float
    bpm_confidence: float
    beats: list[Beat]
    drops: list[Drop]
    choruses: list[Segment]
    energy_curve: list[float]  # normalized 0-1, one value per 100ms
    beat_map: BeatMap
```

**Pipeline:**
1. **Load audio** — librosa or PyAV → mono float32
2. **BPM detection** — librosa beat tracking + autocorrelation validation
3. **Beat extraction** — Onset detection + beat grid alignment
4. **Energy curve** — RMS energy per 100ms window, normalized
5. **Drop detection** — Peak finding on energy curve + spectral flux
6. **Chorus detection** — Self-similarity matrix clustering (optional v1.1)

**Models:** None (signal processing only for v1)

**Confidence:**
```
bpm_confidence = agreement between two independent BPM estimators
```

---

### 4.4 Style Analyzer Agent

**ID:** `style-analyzer`  
**Version:** `1.0.0`

**Purpose:** Extract editing style patterns from reference montage videos.

**Input:**
```python
class StyleAnalyzerInput(AgentInput):
    reference_montage_id: str
    video_path: Path
```

**Output:**
```python
class StyleProfile(BaseModel):
    avg_clip_duration_ms: float
    cuts_per_minute: float
    transition_types: dict[str, float]   # {"cut": 0.7, "fade": 0.1, "flash": 0.15, "zoom": 0.05}
    slow_motion_pct: float
    replay_pct: float
    zoom_usage_pct: float
    color_grade: ColorGradeParams
    pacing_curve: list[float]            # normalized energy over timeline
    intro_duration_ms: int
    outro_duration_ms: int
```

**Pipeline:**
1. **Scene/cut detection** — PySceneDetect or histogram-based
2. **Clip duration stats** — Mean, median, std of detected segments
3. **Transition classification** — Frame diff patterns: hard cut vs fade vs flash
4. **Speed analysis** — Optical flow vs playback rate → detect slow-mo
5. **Color analysis** — Average LAB values per segment → grade approximation
6. **Pacing curve** — Cut frequency over sliding 10s windows

**Models:**
- CLIP (optional) — transition type classification enhancement

---

### 4.5 Timeline Planner Agent

**ID:** `timeline-planner`  
**Version:** `1.0.0`

**Purpose:** Generate an editable timeline from ranked clips, music analysis, and style profile.

**Input:**
```python
class TimelinePlannerInput(AgentInput):
    project_id: str
    ranked_clips: list[RankedClip]
    game_events: list[GameEvent]
    music_analysis: MusicAnalyzerOutput
    style_profile: StyleProfile | None
    target_duration_ms: int | None
    preferences: TimelinePreferences
```

**Output:**
```python
class TimelinePlannerOutput(BaseModel):
    timeline: TimelineDocument
    placements: list[ClipPlacementReasoning]
    overall_confidence: float
    reasoning: str
    expected_improvement: str
```

**Algorithm (v1 heuristic + scoring):**

1. **Select clips** — Top N by rank_score; ensure bomb events represented
2. **Determine clip order** — Sort by excitement arc (build → peak → cooldown)
3. **Assign durations** — Match style profile avg_clip_duration; shorten downtime
4. **Align to beats** — Snap cut points to nearest beat; prioritize drops for bomb clips
5. **Assign tracks** — Video track 1, music track 2, game audio track 3
6. **Add transitions** — Apply style profile transition distribution
7. **Score result** — Composite confidence based on sync quality + clip diversity

**Placement reasoning example:**
```json
{
  "clip_id": "abc-123",
  "start_ms": 45000,
  "confidence": 0.96,
  "reasoning": "Highest estimated kill density synchronized with the music drop at 45.2s.",
  "expected_improvement": "+12% engagement score vs random placement"
}
```

---

### 4.6 Editing Agent

**ID:** `editing-agent`  
**Version:** `1.0.0`

**Purpose:** Apply specific edits to timeline — cuts, transitions, speed ramps, zooms, effects.

**Input:**
```python
class EditingAgentInput(AgentInput):
    timeline: TimelineDocument
    edit_request: EditRequest   # structured edit specification
```

**Output:**
```python
class EditingAgentOutput(BaseModel):
    timeline: TimelineDocument
    edits_applied: list[EditRecord]
    confidence: float
    reasoning: str
```

**Capabilities:**
- Trim/extend clips
- Apply speed ramps (ease in/out)
- Add zoom keyframes
- Insert transitions (cut, fade, flash, dip-to-black)
- Add text overlays
- Apply motion blur filter

Invoked by Chat Assistant after NL command parsing.

---

### 4.7 Audio Agent

**ID:** `audio-agent`  
**Version:** `1.0.0`

**Purpose:** Balance and mix audio tracks — game audio, music, voice, Discord.

**Input:**
```python
class AudioAgentInput(AgentInput):
    timeline: TimelineDocument
    mix_settings: MixSettings
```

**Output:**
```python
class AudioAgentOutput(BaseModel):
    timeline: TimelineDocument     # with updated audio levels/keyframes
    mix_report: MixReport
    confidence: float
    reasoning: str
```

**Processing:**
1. Analyze peak/RMS levels per track
2. Apply normalization targets (music: -14 LUFS, game: -20 LUFS)
3. Duck music during high game audio (bombs, callouts)
4. Detect and boost voice/Discord segments (Whisper speech detection)
5. Apply crossfade at clip boundaries

---

### 4.8 Thumbnail Agent

**ID:** `thumbnail-agent`  
**Version:** `1.0.0`

**Purpose:** Generate editable YouTube thumbnail candidates.

**Input:**
```python
class ThumbnailAgentInput(AgentInput):
    timeline: TimelineDocument
    ranked_clips: list[RankedClip]
    style_preferences: ThumbnailPreferences
```

**Output:**
```python
class ThumbnailCandidate(BaseModel):
    id: str
    frame_timestamp_ms: int
    source_clip_id: str
    score: float
    confidence: float
    reasoning: str
    preview_path: Path
    editable_layers: list[ThumbnailLayer]  # text, borders, effects
```

**Selection criteria:**
- Highest excitement frames
- Faces/action centered (future: face detection)
- High contrast and color pop
- Bomb/event moments preferred

---

### 4.9 AI Chat Assistant

**ID:** `chat-assistant`  
**Version:** `1.0.0`

**Purpose:** Parse natural language commands and apply timeline edits.

**Input:**
```python
class ChatAssistantInput(AgentInput):
    message: str
    timeline: TimelineDocument
    context: ChatContext          # recent messages, selected clip, playhead position
```

**Output:**
```python
class ChatAssistantOutput(BaseModel):
    response: str                 # natural language reply
    commands: list[EditCommand]   # structured commands executed
    timeline: TimelineDocument    # updated timeline
    suggestions: list[AISuggestion]
    confidence: float
```

**NL → Command pipeline:**
1. **Intent classification** — Replace, remove, speed change, sync, add, shorten
2. **Entity extraction** — Clip references, time ranges, event types
3. **Command generation** — Map to `EditCommand` objects
4. **Execute via Editing Agent** — Apply changes
5. **Generate response** — Explain what was done

**Example:**
```
User: "Replace the clip at 0:45 with a better bomb"
→ Intent: replace
→ Entity: time=45000ms, criteria=bomb, rank=highest
→ Command: ClipSwapCommand(target_time=45000, new_clip=top_bomb_clip)
→ Response: "Replaced clip at 0:45 with 'ZvZ_Bomb_03.mp4' (Bomb Score: 9.8, 96% confidence)."
```

**LLM backend:**
- v1: Local small model (Llama 3.2 3B or Phi-3) for intent parsing
- Fallback: Rule-based parser for common commands
- Optional: Cloud API (OpenAI/Anthropic) with user opt-in

## 5. Orchestrator

```python
class AIEngine:
    def __init__(self):
        self.agents: dict[str, BaseAgent] = {}
        self.model_registry = ModelRegistry()

    def register_agent(self, agent: BaseAgent) -> None: ...

    async def run_pipeline(self, pipeline: AgentPipeline) -> PipelineResult:
        """Run agents in sequence, passing outputs as inputs."""
        ...

    async def run_agent(self, agent_id: str, input: AgentInput) -> AgentResult:
        """Run a single agent."""
        ...

# Example pipeline: full clip analysis
clip_pipeline = AgentPipeline([
    ("clip-analyzer", ClipAnalyzerInput),
    ("albion-analyzer", AlbionAnalyzerInput),  # receives clip analysis output
])
```

## 6. Model Registry

```python
class ModelRegistry:
    models: dict[str, ModelHandle]

    async def load(self, model_id: str) -> ModelHandle: ...
    async def unload(self, model_id: str) -> None: ...
    def get(self, model_id: str) -> ModelHandle: ...

# Registered models (v1)
MODELS = {
    "clip-vit-b32": {"path": "ai/models/clip-vit-b32.onnx", "runtime": "onnx"},
    "easyocr-en": {"path": "auto", "runtime": "easyocr"},
    "whisper-base": {"path": "ai/models/whisper-base.pt", "runtime": "torch"},
}
```

## 7. Agent Result → AI Suggestion Mapping

When an agent produces a recommendation (not just analysis), the service layer converts it:

```python
def agent_result_to_suggestion(result: AgentResult, context: SuggestionContext) -> AISuggestion:
    return AISuggestion(
        suggestion_type=map_agent_to_type(result.agent_id),
        confidence=result.confidence,
        reasoning=result.reasoning,
        expected_improvement=result.data.get("expected_improvement"),
        payload=result.data,
        agent_id=result.agent_id,
    )
```

## 8. Agent Testing Strategy

| Agent | Unit Test | Integration Test | Validation Set |
|-------|-----------|------------------|----------------|
| Clip Analyzer | Mock frames → expected scores | Real 30s clip | 50 labeled clips |
| Albion Analyzer | Mock OCR + frames | Real Albion clips | 30 labeled events |
| Music Analyzer | Synthetic beat track | Real EDM/hip-hop tracks | 20 tracks with known BPM |
| Style Analyzer | Synthetic cuts | Real reference montages | 5 reference montages |
| Timeline Planner | Mock inputs → valid timeline | Full pipeline | Creator review |
| Chat Assistant | NL → command parsing | End-to-end edit | 50 command phrases |

## 9. Versioning

Agent versions tracked in analysis results (`analysis_version` column). When agent logic changes:
1. Bump `agent_version`
2. Re-analysis optional (user prompted: "Updated analyzer available")
