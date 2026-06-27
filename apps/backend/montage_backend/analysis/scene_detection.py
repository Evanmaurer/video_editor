from __future__ import annotations

import re

from montage_backend.models.domain.analysis import (
    SceneAnalysisResult,
    SceneEvent,
    SceneSegment,
    SceneTransitionType,
)

_SCENE_PTS_RE = re.compile(r"pts_time:([0-9.]+)")
_SCENE_SCORE_RE = re.compile(r"scene_score:([0-9.]+)")
_BLACK_START_RE = re.compile(r"black_start:([0-9.]+)")
_BLACK_END_RE = re.compile(r"black_end:([0-9.]+)")
_BLACK_DURATION_RE = re.compile(r"black_duration:([0-9.]+)")
_FREEZE_START_RE = re.compile(r"freeze_start:([0-9.]+)")
_FREEZE_END_RE = re.compile(r"freeze_end:([0-9.]+)")
_FREEZE_DURATION_RE = re.compile(r"freeze_duration:([0-9.]+)")

HARD_CUT_MIN_SCORE = 0.3
SHOT_BOUNDARY_MIN_SCORE = 0.15
FADE_MIN_SCORE = 0.05
FADE_MAX_SCORE = 0.15


def ms_to_frame(timestamp_ms: int, frame_rate: float) -> int:
    return max(0, int(round(timestamp_ms * frame_rate / 1000.0)))


def frame_to_ms(frame: int, frame_rate: float) -> int:
    return max(0, int(round(frame * 1000.0 / frame_rate)))


def parse_scene_markers(stderr: str) -> list[tuple[int, float]]:
    markers: list[tuple[int, float]] = []
    for line in stderr.splitlines():
        if "pts_time:" not in line:
            continue
        try:
            pts_match = _SCENE_PTS_RE.search(line)
            if pts_match is None:
                continue
            score_match = _SCENE_SCORE_RE.search(line)
            score = float(score_match.group(1)) if score_match else 0.0
            timestamp_ms = int(float(pts_match.group(1)) * 1000)
            markers.append((timestamp_ms, score))
        except (TypeError, ValueError):
            continue
    return markers


def parse_black_regions(stderr: str) -> list[tuple[int, int, float]]:
    regions: list[tuple[int, int, float]] = []
    pending_start: float | None = None
    for line in stderr.splitlines():
        start_match = _BLACK_START_RE.search(line)
        end_match = _BLACK_END_RE.search(line)
        duration_match = _BLACK_DURATION_RE.search(line)
        if start_match is not None and end_match is not None:
            start_s = float(start_match.group(1))
            end_s = float(end_match.group(1))
            duration_s = float(duration_match.group(1)) if duration_match else end_s - start_s
            regions.append((int(start_s * 1000), int(end_s * 1000), min(1.0, max(0.5, duration_s / 0.08))))
            pending_start = None
            continue
        if start_match is not None:
            pending_start = float(start_match.group(1))
            continue
        if end_match is not None and pending_start is not None:
            end_s = float(end_match.group(1))
            duration_s = float(duration_match.group(1)) if duration_match else end_s - pending_start
            start_ms = int(pending_start * 1000)
            end_ms = int(end_s * 1000)
            confidence = min(1.0, max(0.5, duration_s / 0.08))
            regions.append((start_ms, end_ms, confidence))
            pending_start = None
    return regions


def parse_freeze_regions(stderr: str) -> list[tuple[int, int, float]]:
    regions: list[tuple[int, int, float]] = []
    pending_start: float | None = None
    for line in stderr.splitlines():
        start_match = _FREEZE_START_RE.search(line)
        end_match = _FREEZE_END_RE.search(line)
        duration_match = _FREEZE_DURATION_RE.search(line)
        if start_match is not None and end_match is not None:
            start_s = float(start_match.group(1))
            end_s = float(end_match.group(1))
            duration_s = float(duration_match.group(1)) if duration_match else end_s - start_s
            regions.append((int(start_s * 1000), int(end_s * 1000), min(1.0, max(0.5, duration_s / 0.5))))
            pending_start = None
            continue
        if start_match is not None:
            pending_start = float(start_match.group(1))
            continue
        if end_match is not None and pending_start is not None:
            end_s = float(end_match.group(1))
            duration_s = float(duration_match.group(1)) if duration_match else end_s - pending_start
            start_ms = int(pending_start * 1000)
            end_ms = int(end_s * 1000)
            confidence = min(1.0, max(0.5, duration_s / 0.5))
            regions.append((start_ms, end_ms, confidence))
            pending_start = None
    return regions


def classify_scene_score(score: float) -> SceneTransitionType:
    if score >= HARD_CUT_MIN_SCORE:
        return SceneTransitionType.HARD_CUT
    if score >= SHOT_BOUNDARY_MIN_SCORE:
        return SceneTransitionType.SHOT_BOUNDARY
    if score >= FADE_MIN_SCORE:
        return SceneTransitionType.FADE
    return SceneTransitionType.FADE


def scene_events_from_markers(
    markers: list[tuple[int, float]],
    *,
    frame_rate: float,
) -> list[SceneEvent]:
    events: list[SceneEvent] = []
    for timestamp_ms, score in markers:
        if score < FADE_MIN_SCORE:
            continue
        event_type = classify_scene_score(score)
        confidence = min(1.0, max(score, 0.1))
        events.append(
            SceneEvent(
                timestamp_ms=timestamp_ms,
                frame=ms_to_frame(timestamp_ms, frame_rate),
                event_type=event_type,
                confidence=confidence,
                metadata={"scene_score": score},
            ),
        )
    return events


def scene_events_from_black_regions(
    regions: list[tuple[int, int, float]],
    *,
    frame_rate: float,
) -> list[SceneEvent]:
    events: list[SceneEvent] = []
    for start_ms, end_ms, confidence in regions:
        events.append(
            SceneEvent(
                timestamp_ms=start_ms,
                frame=ms_to_frame(start_ms, frame_rate),
                event_type=SceneTransitionType.BLACK_FRAME,
                confidence=confidence,
                metadata={"end_ms": end_ms},
            ),
        )
    return events


def scene_events_from_freeze_regions(
    regions: list[tuple[int, int, float]],
    *,
    frame_rate: float,
) -> list[SceneEvent]:
    events: list[SceneEvent] = []
    for start_ms, end_ms, confidence in regions:
        events.append(
            SceneEvent(
                timestamp_ms=start_ms,
                frame=ms_to_frame(start_ms, frame_rate),
                event_type=SceneTransitionType.FREEZE_FRAME,
                confidence=confidence,
                metadata={"end_ms": end_ms},
            ),
        )
    return events


def dedupe_events(events: list[SceneEvent], *, frame_rate: float, min_gap_ms: int = 33) -> list[SceneEvent]:
    if not events:
        return []
    ordered = sorted(events, key=lambda event: event.timestamp_ms)
    deduped: list[SceneEvent] = [ordered[0]]
    for event in ordered[1:]:
        last = deduped[-1]
        if event.timestamp_ms - last.timestamp_ms < min_gap_ms:
            if event.confidence > last.confidence:
                deduped[-1] = event
            continue
        deduped.append(event)
    return deduped


def build_scene_segments(
    events: list[SceneEvent],
    *,
    duration_ms: int,
    frame_rate: float,
    frame_count: int,
) -> list[SceneSegment]:
    if duration_ms <= 0:
        return []

    boundaries = dedupe_events(events, frame_rate=frame_rate)
    cut_points = [0]
    transition_by_start: dict[int, SceneTransitionType | None] = {0: None}

    for event in boundaries:
        if event.timestamp_ms <= 0 or event.timestamp_ms >= duration_ms:
            continue
        if event.timestamp_ms in cut_points:
            continue
        cut_points.append(event.timestamp_ms)
        transition_by_start[event.timestamp_ms] = event.event_type

    cut_points.append(duration_ms)
    cut_points = sorted(set(cut_points))

    segments: list[SceneSegment] = []
    for index in range(len(cut_points) - 1):
        start_ms = cut_points[index]
        end_ms = cut_points[index + 1]
        start_frame = ms_to_frame(start_ms, frame_rate)
        end_frame = max(start_frame, ms_to_frame(end_ms, frame_rate) - 1)
        if frame_count > 0:
            end_frame = min(end_frame, frame_count - 1)
        segment_duration = max(0, end_ms - start_ms)
        if segment_duration <= 0:
            continue
        transition_in = transition_by_start.get(start_ms)
        confidence = 1.0
        if transition_in is not None:
            matching = [event for event in boundaries if event.timestamp_ms == start_ms]
            if matching:
                confidence = matching[0].confidence
        segments.append(
            SceneSegment(
                start_frame=start_frame,
                end_frame=end_frame,
                start_ms=start_ms,
                end_ms=end_ms,
                duration_ms=segment_duration,
                transition_in=transition_in,
                confidence=confidence,
            ),
        )

    if not segments:
        segments.append(
            SceneSegment(
                start_frame=0,
                end_frame=max(0, frame_count - 1),
                start_ms=0,
                end_ms=duration_ms,
                duration_ms=duration_ms,
                transition_in=None,
                confidence=1.0,
            ),
        )
    return segments


def build_scene_analysis_result(
    *,
    analyzer_version: str,
    cache_key: str,
    frame_rate: float,
    frame_count: int,
    duration_ms: int,
    scene_stderr: str,
    black_stderr: str,
    freeze_stderr: str,
) -> SceneAnalysisResult:
    markers = parse_scene_markers(scene_stderr)
    black_regions = parse_black_regions(black_stderr)
    freeze_regions = parse_freeze_regions(freeze_stderr)

    events: list[SceneEvent] = []
    events.extend(scene_events_from_markers(markers, frame_rate=frame_rate))
    events.extend(scene_events_from_black_regions(black_regions, frame_rate=frame_rate))
    events.extend(scene_events_from_freeze_regions(freeze_regions, frame_rate=frame_rate))
    events = dedupe_events(events, frame_rate=frame_rate)

    segments = build_scene_segments(
        events,
        duration_ms=duration_ms,
        frame_rate=frame_rate,
        frame_count=frame_count,
    )

    return SceneAnalysisResult(
        analyzer_version=analyzer_version,
        cache_key=cache_key,
        frame_rate=frame_rate,
        frame_count=frame_count,
        duration_ms=duration_ms,
        events=events,
        segments=segments,
    )
