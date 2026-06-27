from __future__ import annotations

from montage_backend.models.domain.timeline import TimelineDocument, default_timeline_document
from montage_backend.render.graph_builder import (
    ClipSegment,
    GapSegment,
    build_ffmpeg_command,
    collect_export_segments,
    collect_track_segments,
)
from montage_backend.render.presets import get_preset


def _timeline_with_clips() -> TimelineDocument:
    doc = default_timeline_document(
        project_id="proj-1",
        width=1920,
        height=1080,
        frame_rate=60.0,
    )
    video_track = doc.tracks[0]
    video_track["clips"] = [
        {
            "id": "clip-1",
            "media_item_id": "media-1",
            "track_id": video_track["id"],
            "start_ms": 0,
            "end_ms": 2000,
            "source_in_ms": 1000,
            "source_out_ms": 3000,
            "speed": 1.0,
            "opacity": 1.0,
        },
        {
            "id": "clip-2",
            "media_item_id": "media-2",
            "track_id": video_track["id"],
            "start_ms": 3000,
            "end_ms": 5000,
            "source_in_ms": 0,
            "source_out_ms": 2000,
            "speed": 1.0,
            "opacity": 1.0,
        },
    ]
    doc.duration_ms = 5000
    return doc


def test_collect_track_segments_inserts_gap():
    doc = _timeline_with_clips()
    video_track = doc.tracks[0]
    segments = collect_track_segments(video_track)

    assert len(segments) == 3
    assert isinstance(segments[0], ClipSegment)
    assert isinstance(segments[1], GapSegment)
    assert segments[1].duration_ms == 1000
    assert isinstance(segments[2], ClipSegment)


def test_collect_export_segments_resume_skips_completed_clips():
    doc = _timeline_with_clips()
    video_segments, _ = collect_export_segments(doc, resume_from_ms=2500)

    assert len(video_segments) == 2
    assert isinstance(video_segments[0], GapSegment)
    assert isinstance(video_segments[1], ClipSegment)
    assert video_segments[1].media_item_id == "media-2"


def test_build_ffmpeg_command_contains_scale_and_encoder():
    doc = _timeline_with_clips()
    video_segments, audio_segments = collect_export_segments(doc)
    preset = get_preset("h264_1080p60")
    args, duration_s = build_ffmpeg_command(
        ffmpeg_bin="ffmpeg",
        preset=preset,
        video_segments=video_segments,
        audio_segments=audio_segments,
        media_paths={
            "media-1": "/tmp/a.mp4",
            "media-2": "/tmp/b.mp4",
        },
        output_path="/tmp/out.mp4",
        video_encoder="libx264",
        encoder_options={"crf": "18", "preset": "medium"},
    )

    joined = " ".join(args)
    assert duration_s > 0
    assert "scale=1920:1080" in joined
    assert "-c:v libx264" in joined
    assert "/tmp/out.mp4" in args
    assert "-filter_complex" in args
