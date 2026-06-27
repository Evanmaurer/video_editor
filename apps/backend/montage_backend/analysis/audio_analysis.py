from __future__ import annotations

import math
import re
import struct
from enum import Enum

from pydantic import BaseModel, Field

_SILENCE_START_RE = re.compile(r"silence_start:\s*([0-9.]+)")
_SILENCE_END_RE = re.compile(r"silence_end:\s*([0-9.]+)")
_MEAN_VOLUME_RE = re.compile(r"mean_volume:\s*([-0-9.]+)\s*dB")
_MAX_VOLUME_RE = re.compile(r"max_volume:\s*([-0-9.]+)\s*dB")
_EBUR128_I_RE = re.compile(r"I:\s*([-0-9.]+)\s*LUFS")
_EBUR128_LRA_RE = re.compile(r"LRA:\s*([0-9.]+)\s*LU")

PEAK_THRESHOLD_RATIO = 0.55
BEAT_MIN_GAP_MS = 250
WINDOW_MS = 1000


class AudioEventType(str, Enum):
    PEAK = "peak"
    SILENCE = "silence"
    BEAT = "beat"


class TimestampedAudioEvent(BaseModel):
    timestamp_ms: int
    event_type: AudioEventType
    value: float = Field(ge=0.0)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    metadata: dict = Field(default_factory=dict)


class LoudnessWindow(BaseModel):
    start_ms: int
    end_ms: int
    duration_ms: int
    loudness_db: float
    dynamic_range_db: float
    music_probability: float = Field(ge=0.0, le=1.0)
    voice_probability: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class AudioAnalysisSummary(BaseModel):
    loudness_lufs: float | None = None
    mean_volume_db: float | None = None
    max_volume_db: float | None = None
    dynamic_range_db: float = Field(ge=0.0, default=0.0)
    tempo_bpm: float | None = None
    music_probability: float = Field(ge=0.0, le=1.0, default=0.0)
    voice_probability: float = Field(ge=0.0, le=1.0, default=0.0)
    silence_ratio: float = Field(ge=0.0, le=1.0, default=0.0)
    beat_count: int = Field(ge=0, default=0)
    peak_count: int = Field(ge=0, default=0)


class AudioAnalysisResult(BaseModel):
    analyzer_version: str
    cache_key: str
    duration_ms: int
    sample_count: int
    window_ms: int
    has_audio: bool = True
    summary: AudioAnalysisSummary
    events: list[TimestampedAudioEvent] = Field(default_factory=list)
    loudness_windows: list[LoudnessWindow] = Field(default_factory=list)
    peaks: list[float] = Field(default_factory=list)


def first_regex_match(pattern: re.Pattern[str], text: str) -> float | None:
    match = pattern.search(text)
    if match is None:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def parse_volume_stats(stderr: str) -> tuple[float | None, float | None]:
    return first_regex_match(_MEAN_VOLUME_RE, stderr), first_regex_match(_MAX_VOLUME_RE, stderr)


def parse_ebur128_stats(stderr: str) -> tuple[float | None, float | None]:
    return first_regex_match(_EBUR128_I_RE, stderr), first_regex_match(_EBUR128_LRA_RE, stderr)


def parse_silence_regions(stderr: str, duration_ms: int) -> list[tuple[int, int]]:
    regions: list[tuple[int, int]] = []
    open_start: float | None = None
    for line in stderr.splitlines():
        start_match = _SILENCE_START_RE.search(line)
        end_match = _SILENCE_END_RE.search(line)
        if start_match is not None and end_match is not None:
            start_s = float(start_match.group(1))
            end_s = float(end_match.group(1))
            regions.append((int(start_s * 1000), int(end_s * 1000)))
            open_start = None
            continue
        if start_match is not None:
            open_start = float(start_match.group(1))
            continue
        if end_match is not None and open_start is not None:
            end_s = float(end_match.group(1))
            regions.append((int(open_start * 1000), int(end_s * 1000)))
            open_start = None
    if open_start is not None:
        regions.append((int(open_start * 1000), duration_ms))
    return regions


def silence_events_from_regions(regions: list[tuple[int, int]]) -> list[TimestampedAudioEvent]:
    events: list[TimestampedAudioEvent] = []
    for start_ms, end_ms in regions:
        duration = max(0, end_ms - start_ms)
        events.append(
            TimestampedAudioEvent(
                timestamp_ms=start_ms,
                event_type=AudioEventType.SILENCE,
                value=round(duration / 1000.0, 3),
                confidence=0.9,
                metadata={"end_ms": end_ms, "duration_ms": duration},
            ),
        )
    return events


def downsample_peaks(raw: bytes, target_samples: int) -> list[float]:
    if not raw:
        return [0.0] * target_samples

    count = len(raw) // 4
    if count == 0:
        return [0.0] * target_samples

    floats = struct.unpack(f"{count}f", raw[: count * 4])
    if count <= target_samples:
        peaks = [min(abs(value), 1.0) for value in floats]
        if len(peaks) < target_samples:
            peaks.extend([0.0] * (target_samples - len(peaks)))
        return peaks

    bucket = count / target_samples
    peaks: list[float] = []
    for index in range(target_samples):
        start = int(index * bucket)
        end = int((index + 1) * bucket)
        chunk = floats[start:end] or (floats[start],)
        peaks.append(min(max(abs(value) for value in chunk), 1.0))
    return peaks


def peak_to_db(value: float) -> float:
    return 20.0 * math.log10(max(value, 1e-6))


def detect_peak_events(peaks: list[float], duration_ms: int) -> list[TimestampedAudioEvent]:
    if not peaks:
        return []

    threshold = max(max(peaks) * PEAK_THRESHOLD_RATIO, 0.05)
    events: list[TimestampedAudioEvent] = []
    for index, value in enumerate(peaks):
        if value < threshold:
            continue
        left = peaks[index - 1] if index > 0 else 0.0
        right = peaks[index + 1] if index + 1 < len(peaks) else 0.0
        if value < left or value < right:
            continue
        timestamp_ms = int((index / max(len(peaks) - 1, 1)) * duration_ms)
        events.append(
            TimestampedAudioEvent(
                timestamp_ms=timestamp_ms,
                event_type=AudioEventType.PEAK,
                value=round(value, 3),
                confidence=round(min(1.0, value / max(threshold, 0.01)), 3),
                metadata={"amplitude": round(value, 3)},
            ),
        )
    return events


def detect_beat_events(peaks: list[float], duration_ms: int) -> list[TimestampedAudioEvent]:
    if not peaks:
        return []

    threshold = max(max(peaks) * PEAK_THRESHOLD_RATIO, 0.05)
    min_gap_ms = BEAT_MIN_GAP_MS
    events: list[TimestampedAudioEvent] = []
    last_ms = -min_gap_ms

    for index, value in enumerate(peaks):
        if value < threshold:
            continue
        left = peaks[index - 1] if index > 0 else 0.0
        right = peaks[index + 1] if index + 1 < len(peaks) else 0.0
        if value < left or value < right:
            continue
        timestamp_ms = int((index / max(len(peaks) - 1, 1)) * duration_ms)
        if timestamp_ms - last_ms < min_gap_ms:
            continue
        events.append(
            TimestampedAudioEvent(
                timestamp_ms=timestamp_ms,
                event_type=AudioEventType.BEAT,
                value=round(value, 3),
                confidence=round(min(1.0, value / max(threshold, 0.01)), 3),
                metadata={"strength": round(value, 3)},
            ),
        )
        last_ms = timestamp_ms

    return events


def estimate_tempo_bpm(beat_events: list[TimestampedAudioEvent]) -> float | None:
    if len(beat_events) < 2:
        return None
    intervals = [
        beat_events[index].timestamp_ms - beat_events[index - 1].timestamp_ms
        for index in range(1, len(beat_events))
        if beat_events[index].timestamp_ms > beat_events[index - 1].timestamp_ms
    ]
    if not intervals:
        return None
    intervals.sort()
    median_ms = intervals[len(intervals) // 2]
    if median_ms <= 0:
        return None
    return round(60_000.0 / median_ms, 1)


def silence_ratio_for_window(
    start_ms: int,
    end_ms: int,
    silence_regions: list[tuple[int, int]],
) -> float:
    overlap = 0
    for region_start, region_end in silence_regions:
        overlap_start = max(start_ms, region_start)
        overlap_end = min(end_ms, region_end)
        if overlap_end > overlap_start:
            overlap += overlap_end - overlap_start
    duration = max(end_ms - start_ms, 1)
    return min(1.0, overlap / duration)


def beat_density_for_window(
    start_ms: int,
    end_ms: int,
    beat_events: list[TimestampedAudioEvent],
) -> float:
    count = sum(1 for event in beat_events if start_ms <= event.timestamp_ms < end_ms)
    duration_s = max((end_ms - start_ms) / 1000.0, 0.1)
    return min(1.0, count / max(duration_s * 2.0, 0.1))


def estimate_content_probabilities(
    *,
    energy: float,
    beat_density: float,
    silence_ratio: float,
    mean_volume_db: float | None,
) -> tuple[float, float]:
    if silence_ratio > 0.8 or energy < 0.05:
        return 0.1, 0.1

    music = min(1.0, beat_density * 0.65 + energy * 0.35)
    voice = min(1.0, (1.0 - beat_density) * 0.45 + energy * 0.35)
    if mean_volume_db is not None and -45.0 < mean_volume_db < -18.0:
        voice = min(1.0, voice + 0.2)
    if beat_density > 0.35:
        music = min(1.0, music + 0.15)

    total = music + voice
    if total <= 0:
        return 0.5, 0.5
    return round(music / total, 3), round(voice / total, 3)


def build_loudness_windows(
    peaks: list[float],
    *,
    duration_ms: int,
    silence_regions: list[tuple[int, int]],
    beat_events: list[TimestampedAudioEvent],
    mean_volume_db: float | None,
    window_ms: int = WINDOW_MS,
) -> list[LoudnessWindow]:
    if duration_ms <= 0:
        return []

    windows: list[LoudnessWindow] = []
    start_ms = 0
    while start_ms < duration_ms:
        end_ms = min(start_ms + window_ms, duration_ms)
        start_index = int((start_ms / max(duration_ms, 1)) * max(len(peaks) - 1, 1))
        end_index = int((end_ms / max(duration_ms, 1)) * max(len(peaks) - 1, 1))
        window_peaks = peaks[start_index : end_index + 1] or peaks[start_index : start_index + 1]
        if not window_peaks:
            window_peaks = [0.0]

        max_peak = max(window_peaks)
        min_peak = min(value for value in window_peaks if value > 0.0) if any(window_peaks) else 0.0
        energy = sum(window_peaks) / len(window_peaks)
        loudness_db = round(peak_to_db(energy), 2)
        dynamic_range_db = round(max(0.0, peak_to_db(max_peak) - peak_to_db(min_peak)), 2)

        silence_ratio = silence_ratio_for_window(start_ms, end_ms, silence_regions)
        beat_density = beat_density_for_window(start_ms, end_ms, beat_events)
        music_probability, voice_probability = estimate_content_probabilities(
            energy=energy,
            beat_density=beat_density,
            silence_ratio=silence_ratio,
            mean_volume_db=mean_volume_db,
        )
        confidence = min(1.0, 0.5 + len(window_peaks) * 0.02)

        windows.append(
            LoudnessWindow(
                start_ms=start_ms,
                end_ms=end_ms,
                duration_ms=end_ms - start_ms,
                loudness_db=loudness_db,
                dynamic_range_db=dynamic_range_db,
                music_probability=music_probability,
                voice_probability=voice_probability,
                confidence=round(confidence, 3),
            ),
        )
        if end_ms >= duration_ms:
            break
        start_ms = end_ms

    return windows


def compute_dynamic_range_db(
    peaks: list[float],
    *,
    mean_volume_db: float | None,
    max_volume_db: float | None,
) -> float:
    if max_volume_db is not None and mean_volume_db is not None:
        return round(max(0.0, max_volume_db - mean_volume_db), 2)
    if not peaks:
        return 0.0
    max_peak = max(peaks)
    min_peak = min(value for value in peaks if value > 0.0) if any(peaks) else 0.0
    return round(max(0.0, peak_to_db(max_peak) - peak_to_db(min_peak)), 2)


def build_audio_analysis_result(
    *,
    analyzer_version: str,
    cache_key: str,
    duration_ms: int,
    volume_stderr: str,
    ebur128_stderr: str,
    peaks: list[float],
    window_ms: int,
    has_audio: bool = True,
) -> AudioAnalysisResult:
    if not has_audio:
        return AudioAnalysisResult(
            analyzer_version=analyzer_version,
            cache_key=cache_key,
            duration_ms=duration_ms,
            sample_count=len(peaks),
            window_ms=window_ms,
            has_audio=False,
            summary=AudioAnalysisSummary(),
            events=[],
            loudness_windows=[],
            peaks=[],
        )

    mean_volume_db, max_volume_db = parse_volume_stats(volume_stderr)
    loudness_lufs, lra = parse_ebur128_stats(ebur128_stderr)
    if loudness_lufs is None:
        loudness_lufs = mean_volume_db

    silence_regions = parse_silence_regions(volume_stderr, duration_ms)
    silence_events = silence_events_from_regions(silence_regions)
    peak_events = detect_peak_events(peaks, duration_ms)
    beat_events = detect_beat_events(peaks, duration_ms)
    tempo_bpm = estimate_tempo_bpm(beat_events)

    loudness_windows = build_loudness_windows(
        peaks,
        duration_ms=duration_ms,
        silence_regions=silence_regions,
        beat_events=beat_events,
        mean_volume_db=mean_volume_db,
        window_ms=window_ms,
    )

    silent_ms = sum(end - start for start, end in silence_regions)
    silence_ratio = round(min(1.0, silent_ms / max(duration_ms, 1)), 3)

    if loudness_windows:
        music_probability = round(
            sum(window.music_probability for window in loudness_windows) / len(loudness_windows),
            3,
        )
        voice_probability = round(
            sum(window.voice_probability for window in loudness_windows) / len(loudness_windows),
            3,
        )
    else:
        music_probability, voice_probability = estimate_content_probabilities(
            energy=sum(peaks) / max(len(peaks), 1),
            beat_density=min(1.0, len(beat_events) / max(duration_ms / 1000.0, 1.0)),
            silence_ratio=silence_ratio,
            mean_volume_db=mean_volume_db,
        )

    dynamic_range_db = compute_dynamic_range_db(
        peaks,
        mean_volume_db=mean_volume_db,
        max_volume_db=max_volume_db,
    )
    if lra is not None:
        dynamic_range_db = round(max(dynamic_range_db, lra), 2)

    summary = AudioAnalysisSummary(
        loudness_lufs=round(loudness_lufs, 2) if loudness_lufs is not None else None,
        mean_volume_db=round(mean_volume_db, 2) if mean_volume_db is not None else None,
        max_volume_db=round(max_volume_db, 2) if max_volume_db is not None else None,
        dynamic_range_db=dynamic_range_db,
        tempo_bpm=tempo_bpm,
        music_probability=music_probability,
        voice_probability=voice_probability,
        silence_ratio=silence_ratio,
        beat_count=len(beat_events),
        peak_count=len(peak_events),
    )

    events = sorted(
        [*silence_events, *peak_events, *beat_events],
        key=lambda event: event.timestamp_ms,
    )

    return AudioAnalysisResult(
        analyzer_version=analyzer_version,
        cache_key=cache_key,
        duration_ms=duration_ms,
        sample_count=len(peaks),
        window_ms=window_ms,
        has_audio=True,
        summary=summary,
        events=events,
        loudness_windows=loudness_windows,
        peaks=[round(value, 4) for value in peaks],
    )
