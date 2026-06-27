# Rendering Pipeline Design

**Product:** MontageAI  
**Version:** 1.0  
**Date:** 2026-06-26

---

## 1. Overview

The rendering pipeline converts a Timeline Document into a final video file using FFmpeg. It supports preview-quality proxy renders and export-quality final renders with configurable presets.

## 2. Pipeline Architecture

```
Timeline Document
       │
       ▼
┌──────────────────┐
│  Graph Builder   │  ← Parse timeline → FFmpeg filter graph
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Asset Resolver  │  ← Map media_item_id → file paths (original vs proxy)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Filter Compiler │  ← Effects, transitions, speed → filter strings
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  FFmpeg Executor │  ← Run FFmpeg with progress parsing
└────────┬─────────┘
         │
         ▼
   Output Video File
```

## 3. Render Modes

| Mode | Resolution | Source Media | Use Case |
|------|-----------|--------------|----------|
| `preview` | 720p | Proxies | Quick preview render |
| `draft` | 1080p | Proxies | Review before final |
| `export` | 1080p/4K | Originals | Final delivery |
| `thumbnail` | 1280x720 | Originals | YouTube thumbnail frame |

## 4. Export Presets

```python
RENDER_PRESETS = {
    "h264_1080p60": RenderPreset(
        codec="libx264",
        width=1920, height=1080,
        frame_rate=60.0,
        crf=18,
        preset="slow",
        audio_codec="aac",
        audio_bitrate="192k",
        pixel_format="yuv420p",
        container="mp4",
    ),
    "h264_1080p30": RenderPreset(...),
    "h265_1080p60": RenderPreset(
        codec="libx265",
        crf=22,
        ...
    ),
    "h264_4k30": RenderPreset(
        width=3840, height=2160,
        frame_rate=30.0,
        ...
    ),
}
```

## 5. Graph Builder

```python
class RenderGraphBuilder:
    def build(self, timeline: TimelineDocument, mode: RenderMode) -> FFmpegGraph:
        """Convert timeline to FFmpeg inputs + filter_complex."""
        ...

class FFmpegGraph:
    inputs: list[FFmpegInput]       # source files with seek ranges
    filter_complex: str             # full filter graph string
    output_mappings: list[str]      # output stream labels
    output_options: dict            # codec, bitrate, etc.
    estimated_duration_ms: int
```

### 5.1 Input Mapping

Each clip on the timeline maps to an FFmpeg input:

```python
@dataclass
class FFmpegInput:
    file_path: Path
    input_index: int
    seek_start_ms: int            # -ss before -i for fast seek
    duration_ms: int
    speed: float
```

For a timeline with 20 clips from 8 source files, FFmpeg receives 8 inputs (deduplicated by file), with trim filters per clip usage.

### 5.2 Video Track Composition

```
[0:v] trim=start=5.0:end=12.0, setpts=PTS-STARTPTS, setpts=PTS/0.5 [v0];
[0:v] trim=start=30.0:end=38.0, setpts=PTS-STARTPTS [v1];
[v0][v1] xfade=transition=fade:duration=0.5:offset=6.5 [vout01];
...
[vout_final] scale=1920:1080, format=yuv420p [video_out]
```

### 5.3 Audio Track Composition

```
[0:a] atrim=start=5.0:end=12.0, asetpts=PTS-STARTPTS, atempo=2.0 [a0];
[1:a] atrim=start=0:end=180.0, asetpts=PTS-STARTPTS, volume=0.8 [music];
[a0][a1]... amix=inputs=N:duration=longest [audio_out]
```

**Audio mixing rules:**
- Music track: volume 0.7-0.9 (configurable)
- Game audio: volume 1.0, ducked during music drops
- Voice/Discord: volume 1.2, high-pass filter at 80Hz
- Final mix: loudnorm target -14 LUFS (YouTube standard)

## 6. Effect Compilation

| Effect | FFmpeg Filter |
|--------|---------------|
| `speed_ramp` | `setpts` (video) + `atempo` chain (audio) |
| `zoom` | `zoompan` with keyframe interpolation |
| `color_grade` | `eq` + `colorbalance` from LUT parameters |
| `motion_blur` | `tmix` frames blending |
| `flash` | `fade` with white color |
| `shake` | `rotate` + `translate` with sine wave |
| `vignette` | `vignette` filter |
| `text_overlay` | `drawtext` with font/styling |

### 6.1 Transition Compilation

| Transition | FFmpeg Filter |
|------------|---------------|
| `cut` | Concat (no filter) |
| `fade` | `xfade=transition=fade:duration={ms}` |
| `dip_to_black` | `xfade=transition=fadeblack:duration={ms}` |
| `flash` | `xfade=transition=fadewhite:duration={ms}` |
| `zoom` | Custom zoompan + xfade |
| `wipe` | `xfade=transition=wiperight:duration={ms}` |

## 7. Render Job Lifecycle

```
1. User clicks Export (or render queue processes job)
2. RenderService.start_render()
   → Validate timeline
   → Build FFmpegGraph
   → Create render_jobs row (status: queued)
   → Enqueue render_export_handler
3. Worker picks up job
   → status: running
   → Execute FFmpeg subprocess
   → Parse stderr for progress (frame= N fps= ...)
   → Emit WebSocket progress events
4. On completion:
   → Verify output file (probe duration, size)
   → status: complete
   → Emit job.complete event
5. On failure:
   → Capture stderr log
   → status: failed
   → Emit job.failed event with error details
```

## 8. Progress Reporting

FFmpeg stderr parsing:

```python
PROGRESS_PATTERN = re.compile(
    r"frame=\s*(?P<frame>\d+).*?"
    r"time=\s*(?P<time>[\d:.]+).*?"
    r"speed=\s*(?P<speed>[\d.]+x)"
)

def parse_progress(line: str, total_duration_ms: int) -> float | None:
    match = PROGRESS_PATTERN.search(line)
    if match:
        time_str = match.group("time")
        current_ms = parse_ffmpeg_time(time_str)
        return min(current_ms / total_duration_ms, 1.0)
    return None
```

## 9. Render Service API

```python
class RenderService:
    async def start_render(self, request: RenderRequest) -> RenderJob: ...
    async def cancel_render(self, job_id: str) -> None: ...
    async def get_render_status(self, job_id: str) -> RenderJob: ...
    async def list_render_jobs(self, project_id: str) -> list[RenderJob]: ...
    async def get_presets(self) -> list[RenderPreset]: ...

class RenderRequest(BaseModel):
    timeline_id: str
    output_path: Path
    preset: str = "h264_1080p60"
    mode: RenderMode = RenderMode.EXPORT
    range_start_ms: int | None = None    # partial render
    range_end_ms: int | None = None
```

## 10. Render Queue (Frontend)

```
┌─────────────────────────────────────────────┐
│ Render Queue                          [—][×]│
├─────────────────────────────────────────────┤
│ ▶ Montage_v1.mp4                            │
│   h264_1080p60 · 3:00 · 67%                 │
│   ████████████░░░░░░  ETA 1:42              │
│   [Cancel]                                  │
├─────────────────────────────────────────────┤
│ ✓ Montage_draft.mp4                         │
│   h264_1080p60 · 3:00 · Complete            │
│   245 MB · [Reveal] [Play]                  │
├─────────────────────────────────────────────┤
│ ○ Montage_4k.mp4                            │
│   h265_4k30 · 3:00 · Queued                 │
└─────────────────────────────────────────────┘
```

Jobs processed sequentially (one FFmpeg at a time) to avoid resource contention.

## 11. Error Handling

| Error | Handling |
|-------|----------|
| Missing source file | Fail job; list missing files in error |
| FFmpeg crash | Capture full stderr; save to log file |
| Unsupported codec | Fail at graph build with clear message |
| Disk full | Fail job; check available space before start |
| User cancel | Send SIGTERM to FFmpeg; cleanup partial output |
| Corrupt output | Verify with FFprobe; re-render if invalid |

## 12. Performance Optimization

| Technique | When |
|-----------|------|
| `-ss` before `-i` | Input seeking (fast, keyframe-aligned) |
| Hardware encoding (`h264_videotoolbox`, `h264_nvenc`) | Export on supported hardware |
| Two-pass encoding | Optional for quality-critical exports |
| Parallel audio/video encode | When using separate output streams |
| Proxy source for draft | Skip full-res decode during iteration |

## 13. Thumbnail Rendering

Separate lightweight pipeline:

```python
class ThumbnailRenderer:
    async def render(self, candidate: ThumbnailCandidate, output: Path) -> Path:
        # Single frame extract + optional text overlay + border
        cmd = [
            "ffmpeg", "-ss", str(candidate.frame_timestamp_ms / 1000),
            "-i", str(source_path),
            "-frames:v", "1",
            "-vf", self._build_overlay_filter(candidate.layers),
            "-y", str(output),
        ]
        ...
```

## 14. Validation Before Render

```python
class RenderValidator:
    def validate(self, timeline: TimelineDocument, mode: RenderMode) -> ValidationResult:
        checks = [
            self._check_source_files_exist,
            self._check_no_empty_tracks,
            self._check_duration_reasonable,     # > 0, < 60 min
            self._check_disk_space,              # estimate output size
            self._check_codec_support,
        ]
        ...
```

## 15. Example FFmpeg Command (Generated)

For a simple 3-clip timeline with music:

```bash
ffmpeg \
  -ss 5.0 -i /path/to/clip1.mp4 \
  -ss 30.0 -i /path/to/clip2.mp4 \
  -ss 10.0 -i /path/to/clip3.mp4 \
  -i /path/to/music.mp3 \
  -filter_complex "
    [0:v] trim=duration=7.0, setpts=PTS-STARTPTS [v0];
    [1:v] trim=duration=8.0, setpts=PTS-STARTPTS [v1];
    [2:v] trim=duration=5.0, setpts=PTS-STARTPTS, setpts=PTS/0.5 [v2];
    [v0][v1] xfade=transition=fade:duration=0.3:offset=6.7 [v01];
    [v01][v2] xfade=transition=fade:duration=0.3:offset=14.4 [vout];
    [0:a] atrim=duration=7.0, asetpts=PTS-STARTPTS [a0];
    [1:a] atrim=duration=8.0, asetpts=PTS-STARTPTS [a1];
    [2:a] atrim=duration=5.0, asetpts=PTS-STARTPTS, atempo=2.0 [a2];
    [3:a] atrim=duration=25.0, volume=0.8 [music];
    [a0][a1][a2] concat=n=3:v=0:a=1 [game_audio];
    [game_audio][music] amix=inputs=2:duration=first:weights=1 0.7 [aout];
    [vout] scale=1920:1080, format=yuv420p [final_v]
  " \
  -map "[final_v]" -map "[aout]" \
  -c:v libx264 -crf 18 -preset slow \
  -c:a aac -b:a 192k \
  -y output.mp4
```

## 16. Future Enhancements

- GPU-accelerated filter graph (CUDA/OpenCL)
- Background render while editing continues
- Segment caching (re-render only changed portions)
- HDR export (HLG/PQ)
- Multi-format batch export
