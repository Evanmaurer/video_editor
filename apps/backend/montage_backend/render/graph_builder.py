from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from montage_backend.models.domain.timeline import TimelineDocument
from montage_backend.render.presets import RenderPreset


@dataclass(frozen=True)
class GapSegment:
    duration_ms: int


@dataclass(frozen=True)
class ClipSegment:
    media_item_id: str
    source_start_ms: float
    duration_ms: float
    timeline_start_ms: int


ExportSegment = GapSegment | ClipSegment


def _visible_video_track(tracks: list[dict[str, Any]]) -> dict[str, Any] | None:
    video_tracks = [
        track
        for track in tracks
        if track.get("type") == "video" and track.get("visible", True)
    ]
    if not video_tracks:
        return None
    return sorted(video_tracks, key=lambda track: track.get("index", 0))[0]


def _first_audio_track(tracks: list[dict[str, Any]]) -> dict[str, Any] | None:
    audio_tracks = [
        track
        for track in tracks
        if track.get("type") == "audio" and not track.get("muted", False)
    ]
    if not audio_tracks:
        return None
    return sorted(audio_tracks, key=lambda track: track.get("index", 0))[0]


def _clip_media_id(clip: dict[str, Any]) -> str:
    media_id = clip.get("media_item_id") or clip.get("media_id")
    if not media_id:
        raise ValueError("Timeline clip is missing media_item_id")
    return str(media_id)


def collect_track_segments(
    track: dict[str, Any] | None,
    *,
    resume_from_ms: int = 0,
) -> list[ExportSegment]:
    if track is None:
        return []

    clips = sorted(track.get("clips", []), key=lambda clip: clip.get("start_ms", 0))
    segments: list[ExportSegment] = []
    cursor_ms = resume_from_ms

    for clip in clips:
        start_ms = int(clip.get("start_ms", 0))
        end_ms = int(clip.get("end_ms", 0))
        if end_ms <= resume_from_ms:
            continue

        if start_ms > cursor_ms:
            segments.append(GapSegment(duration_ms=start_ms - cursor_ms))
            cursor_ms = start_ms

        clip_start_ms = max(start_ms, resume_from_ms)
        offset_ms = clip_start_ms - start_ms
        speed = float(clip.get("speed", 1.0) or 1.0)
        source_in_ms = float(clip.get("source_in_ms", 0)) + offset_ms * speed
        duration_ms = float(end_ms - clip_start_ms)

        segments.append(
            ClipSegment(
                media_item_id=_clip_media_id(clip),
                source_start_ms=source_in_ms,
                duration_ms=duration_ms,
                timeline_start_ms=clip_start_ms,
            ),
        )
        cursor_ms = end_ms

    return segments


def collect_export_segments(
    timeline: TimelineDocument,
    *,
    resume_from_ms: int = 0,
) -> tuple[list[ExportSegment], list[ExportSegment]]:
    video_track = _visible_video_track(timeline.tracks)
    audio_track = _first_audio_track(timeline.tracks)
    video_segments = collect_track_segments(video_track, resume_from_ms=resume_from_ms)
    audio_segments = collect_track_segments(audio_track, resume_from_ms=resume_from_ms)
    return video_segments, audio_segments


def export_duration_ms(timeline: TimelineDocument, resume_from_ms: int = 0) -> int:
    duration = max(int(timeline.duration_ms), 0)
    return max(duration - resume_from_ms, 1)


def _scale_filter(width: int, height: int, fps: float, label_in: str, label_out: str) -> str:
    return (
        f"[{label_in}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps},"
        f"format=yuv420p,setpts=PTS-STARTPTS[{label_out}]"
    )


def _audio_filter(label_in: str, label_out: str) -> str:
    return (
        f"[{label_in}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
        f"asetpts=PTS-STARTPTS[{label_out}]"
    )


def _silence_filter(duration_s: float, label_out: str) -> str:
    return (
        f"anullsrc=channel_layout=stereo:sample_rate=48000:duration={duration_s:.3f}"
        f"[{label_out}]"
    )


def build_ffmpeg_command(
    *,
    ffmpeg_bin: str,
    preset: RenderPreset,
    video_segments: list[ExportSegment],
    audio_segments: list[ExportSegment],
    media_paths: dict[str, str],
    output_path: str,
    video_encoder: str,
    encoder_options: dict[str, str],
    include_audio: bool = True,
) -> tuple[list[str], float]:
    if not video_segments:
        raise ValueError("Timeline has no video clips to export")

    args: list[str] = [ffmpeg_bin, "-hide_banner", "-y", "-progress", "pipe:2"]
    filter_parts: list[str] = []
    video_labels: list[str] = []
    audio_labels: list[str] = []
    input_index = 0
    total_duration_s = 0.0

    def add_video_gap(duration_ms: int) -> None:
        nonlocal input_index, total_duration_s
        duration_s = duration_ms / 1000.0
        total_duration_s += duration_s
        args.extend(
            [
                "-f",
                "lavfi",
                "-i",
                f"color=c=black:s={preset.width}x{preset.height}:d={duration_s:.3f}:r={preset.frame_rate}",
            ],
        )
        out_label = f"v{input_index}"
        filter_parts.append(_scale_filter(preset.width, preset.height, preset.frame_rate, str(input_index), out_label))
        video_labels.append(f"[{out_label}]")
        if include_audio:
            silence_label = f"a{input_index}"
            filter_parts.append(_silence_filter(duration_s, silence_label))
            audio_labels.append(f"[{silence_label}]")
        input_index += 1

    def add_clip(segment: ClipSegment, *, with_audio: bool) -> None:
        nonlocal input_index, total_duration_s
        path = media_paths.get(segment.media_item_id)
        if not path:
            raise ValueError(f"Missing media path for clip {segment.media_item_id}")

        duration_s = segment.duration_ms / 1000.0
        source_start_s = segment.source_start_ms / 1000.0
        total_duration_s += duration_s

        args.extend(
            [
                "-ss",
                f"{source_start_s:.3f}",
                "-i",
                path,
                "-t",
                f"{duration_s:.3f}",
            ],
        )
        out_label = f"v{input_index}"
        filter_parts.append(_scale_filter(preset.width, preset.height, preset.frame_rate, str(input_index), out_label))
        video_labels.append(f"[{out_label}]")
        if with_audio:
            audio_out = f"a{input_index}"
            filter_parts.append(_audio_filter(str(input_index), audio_out))
            audio_labels.append(f"[{audio_out}]")
        input_index += 1

    for segment in video_segments:
        if isinstance(segment, GapSegment):
            add_video_gap(segment.duration_ms)
        else:
            add_clip(segment, with_audio=False)

    use_dedicated_audio = bool(audio_segments)
    if include_audio and use_dedicated_audio:
        for segment in audio_segments:
            if isinstance(segment, GapSegment):
                duration_s = segment.duration_ms / 1000.0
                silence_label = f"ax{len(audio_labels)}"
                filter_parts.append(_silence_filter(duration_s, silence_label))
                audio_labels.append(f"[{silence_label}]")
            else:
                path = media_paths.get(segment.media_item_id)
                if not path:
                    raise ValueError(f"Missing media path for audio clip {segment.media_item_id}")
                duration_s = segment.duration_ms / 1000.0
                source_start_s = segment.source_start_ms / 1000.0
                args.extend(
                    [
                        "-ss",
                        f"{source_start_s:.3f}",
                        "-i",
                        path,
                        "-t",
                        f"{duration_s:.3f}",
                    ],
                )
                audio_out = f"ax{input_index}"
                filter_parts.append(_audio_filter(str(input_index), audio_out))
                audio_labels.append(f"[{audio_out}]")
                input_index += 1
    elif include_audio:
        audio_labels = []
        input_index_audio = 0
        for segment in video_segments:
            if isinstance(segment, GapSegment):
                duration_s = segment.duration_ms / 1000.0
                silence_label = f"a{input_index_audio}"
                filter_parts.append(_silence_filter(duration_s, silence_label))
                audio_labels.append(f"[{silence_label}]")
            else:
                audio_out = f"a{input_index_audio}"
                filter_parts.append(_audio_filter(str(input_index_audio), audio_out))
                audio_labels.append(f"[{audio_out}]")
            input_index_audio += 1

    concat_count = len(video_labels)
    filter_parts.append("".join(video_labels) + f"concat=n={concat_count}:v=1:a=0[vout]")

    maps = ["-map", "[vout]"]
    if include_audio and audio_labels:
        filter_parts.append("".join(audio_labels) + f"concat=n={len(audio_labels)}:v=0:a=1[aout]")
        maps.extend(["-map", "[aout]"])

    args.extend(["-filter_complex", ";".join(filter_parts), *maps])
    args.extend(["-c:v", video_encoder])
    for key, value in encoder_options.items():
        args.extend([f"-{key}", value])
    args.extend(["-pix_fmt", preset.pixel_format])
    if include_audio and audio_labels:
        args.extend(["-c:a", preset.audio_codec, "-b:a", preset.audio_bitrate])
    args.extend(["-movflags", "+faststart", output_path])

    return args, total_duration_s


def command_preview(args: list[str]) -> str:
    return " ".join(_shell_quote(part) for part in args)


def _shell_quote(value: str) -> str:
    if not value:
        return '""'
    if any(char in value for char in " \t\n\"'"):
        return '"' + value.replace('"', '\\"') + '"'
    return value
