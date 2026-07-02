from __future__ import annotations

from montage_backend.analysis.audio_analysis import AudioEventType, LoudnessWindow
from montage_backend.models.domain import new_uuid
from montage_backend.models.domain.clip_analysis import ClipAnalysisRecord
from montage_backend.models.domain.metadata import BeatMarker
from montage_backend.models.domain.montage_plan import TransitionType
from montage_backend.models.domain.music_sync import (
    MUSIC_SYNC_VERSION,
    CutSuggestion,
    MusicBeatMarker,
    MusicSection,
    MusicSyncAnalysis,
    TransitionTimingSuggestion,
)

CHORUS_MIN_MS = 4000
DROP_ENERGY_DELTA = 0.28
STRONG_BEAT_THRESHOLD = 0.55
MAX_CUT_SUGGESTIONS = 48
CHORUS_ENERGY_OFFSET = 0.06
CHORUS_MIN_MUSIC_PROB = 0.48


def _clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def build_cache_key(source_fingerprint: str | None) -> str:
    fingerprint = source_fingerprint or "unknown"
    return f"{MUSIC_SYNC_VERSION}:{fingerprint}"


def extract_beat_markers(record: ClipAnalysisRecord) -> tuple[list[MusicBeatMarker], float | None]:
    markers: list[MusicBeatMarker] = []
    tempo_bpm: float | None = None

    if record.audio is not None and record.audio.has_audio:
        tempo_bpm = record.audio.summary.tempo_bpm
        for event in record.audio.events:
            if event.event_type != AudioEventType.BEAT:
                continue
            markers.append(
                MusicBeatMarker(
                    timestamp_ms=event.timestamp_ms,
                    strength=min(event.value, 1.0),
                    confidence=min(event.confidence, 1.0),
                ),
            )

    if not markers and record.metadata is not None and record.metadata.audio is not None:
        for beat in record.metadata.audio.beat_markers:
            markers.append(
                MusicBeatMarker(
                    timestamp_ms=beat.timestamp_ms,
                    strength=beat.strength,
                    confidence=0.75,
                ),
            )

    markers.sort(key=lambda item: item.timestamp_ms)
    return markers, tempo_bpm


def _window_energy(window: LoudnessWindow) -> float:
    loudness = window.loudness_db
    normalized = min(max((loudness + 48.0) / 48.0, 0.0), 1.0)
    return min(normalized * 0.6 + window.music_probability * 0.4, 1.0)


def detect_chorus_sections(
    windows: list[LoudnessWindow],
    duration_ms: int,
) -> list[MusicSection]:
    if not windows:
        return []

    energies = [_window_energy(window) for window in windows]
    median_energy = sorted(energies)[len(energies) // 2]
    threshold = max(median_energy + CHORUS_ENERGY_OFFSET, 0.42)

    sections: list[MusicSection] = []
    run_start: LoudnessWindow | None = None
    run_end: LoudnessWindow | None = None

    for window, energy in zip(windows, energies, strict=True):
        is_chorus = energy >= threshold and window.music_probability >= CHORUS_MIN_MUSIC_PROB
        if is_chorus:
            if run_start is None:
                run_start = window
            run_end = window
            continue
        if run_start is not None and run_end is not None:
            duration = run_end.end_ms - run_start.start_ms
            if duration >= CHORUS_MIN_MS:
                sections.append(
                    MusicSection(
                        id=new_uuid(),
                        section_type="chorus",
                        start_ms=run_start.start_ms,
                        end_ms=run_end.end_ms,
                        confidence=round(min(0.55 + duration / 20_000.0, 0.95), 2),
                        reasoning=(
                            f"Sustained high-energy section "
                            f"({run_start.start_ms}-{run_end.end_ms}ms)"
                        ),
                    ),
                )
            run_start = None
            run_end = None

    if run_start is not None and run_end is not None:
        duration = run_end.end_ms - run_start.start_ms
        if duration >= CHORUS_MIN_MS:
            sections.append(
                MusicSection(
                    id=new_uuid(),
                    section_type="chorus",
                    start_ms=run_start.start_ms,
                    end_ms=run_end.end_ms,
                    confidence=round(min(0.55 + duration / 20_000.0, 0.95), 2),
                    reasoning=(
                        f"Sustained high-energy section "
                        f"({run_start.start_ms}-{run_end.end_ms}ms)"
                    ),
                ),
            )

    if duration_ms > 0:
        sections = [
            section
            for section in sections
            if section.end_ms <= duration_ms and section.start_ms < duration_ms
        ]
    return sections


def detect_drop_sections(windows: list[LoudnessWindow]) -> list[MusicSection]:
    if len(windows) < 2:
        return []

    sections: list[MusicSection] = []
    for index in range(1, len(windows)):
        previous = windows[index - 1]
        current = windows[index]
        prev_energy = _window_energy(previous)
        curr_energy = _window_energy(current)
        delta = curr_energy - prev_energy
        if delta < DROP_ENERGY_DELTA:
            continue
        if curr_energy < 0.5:
            continue
        sections.append(
            MusicSection(
                id=new_uuid(),
                section_type="drop",
                start_ms=current.start_ms,
                end_ms=min(current.end_ms, current.start_ms + 2000),
                confidence=round(min(0.5 + delta, 0.95), 2),
                reasoning=(
                    f"Energy spike at {current.start_ms}ms "
                    f"(+{delta:.2f} from prior window)"
                ),
            ),
        )
    return sections


def build_cut_suggestions(
    beat_markers: list[MusicBeatMarker],
    sections: list[MusicSection],
) -> list[CutSuggestion]:
    suggestions: dict[int, CutSuggestion] = {}

    for beat in beat_markers:
        if beat.strength < STRONG_BEAT_THRESHOLD:
            continue
        score = _clamp_score(beat.strength * 100.0)
        suggestions[beat.timestamp_ms] = CutSuggestion(
            timestamp_ms=beat.timestamp_ms,
            score=score,
            confidence=beat.confidence,
            reasoning=f"Strong beat at {beat.timestamp_ms}ms (strength {beat.strength:.2f})",
            beat_aligned=True,
        )

    for section in sections:
        timestamp_ms = section.start_ms
        base_score = 88.0 if section.section_type == "drop" else 78.0
        existing = suggestions.get(timestamp_ms)
        if existing is not None and existing.score >= base_score:
            continue
        suggestions[timestamp_ms] = CutSuggestion(
            timestamp_ms=timestamp_ms,
            score=base_score,
            confidence=section.confidence,
            reasoning=f"{section.section_type.title()} entry: {section.reasoning}",
            beat_aligned=section.section_type == "drop",
        )

    ranked = sorted(
        suggestions.values(),
        key=lambda item: (item.score, item.timestamp_ms),
        reverse=True,
    )
    return ranked[:MAX_CUT_SUGGESTIONS]


def build_transition_suggestions(
    sections: list[MusicSection],
    beat_markers: list[MusicBeatMarker],
) -> list[TransitionTimingSuggestion]:
    suggestions: list[TransitionTimingSuggestion] = []

    for section in sections:
        if section.section_type == "drop":
            suggestions.append(
                TransitionTimingSuggestion(
                    timestamp_ms=section.start_ms,
                    transition_type=TransitionType.FLASH.value,
                    duration_ms=100,
                    confidence=section.confidence,
                    reasoning="Flash transition on energy drop",
                ),
            )
        elif section.section_type == "chorus":
            suggestions.append(
                TransitionTimingSuggestion(
                    timestamp_ms=section.start_ms,
                    transition_type=TransitionType.CROSSFADE.value,
                    duration_ms=300,
                    confidence=section.confidence,
                    reasoning="Crossfade into chorus section",
                ),
            )

    for beat in beat_markers:
        if beat.strength < 0.75:
            continue
        suggestions.append(
            TransitionTimingSuggestion(
                timestamp_ms=beat.timestamp_ms,
                transition_type=TransitionType.HARD_CUT.value,
                duration_ms=0,
                confidence=beat.confidence,
                reasoning=f"Hard cut on strong beat at {beat.timestamp_ms}ms",
            ),
        )

    suggestions.sort(key=lambda item: item.timestamp_ms)
    return suggestions[:MAX_CUT_SUGGESTIONS]


def compute_overall_confidence(
    beat_markers: list[MusicBeatMarker],
    sections: list[MusicSection],
    tempo_bpm: float | None,
) -> float:
    score = 0.2
    if beat_markers:
        score += 0.35
    if tempo_bpm is not None:
        score += 0.15
    if sections:
        score += min(0.3, len(sections) * 0.08)
    return round(min(score, 1.0), 2)


def build_reasoning(
    tempo_bpm: float | None,
    beat_count: int,
    sections: list[MusicSection],
    cut_count: int,
) -> str:
    chorus_count = sum(1 for section in sections if section.section_type == "chorus")
    drop_count = sum(1 for section in sections if section.section_type == "drop")
    tempo_label = f"{tempo_bpm:.1f} BPM" if tempo_bpm is not None else "unknown tempo"
    return (
        f"Music sync at {tempo_label}: {beat_count} beats, "
        f"{chorus_count} chorus sections, {drop_count} drops, "
        f"{cut_count} cut suggestions."
    )


def analyze_music_sync(
    *,
    project_id: str,
    media_id: str,
    record: ClipAnalysisRecord,
    file_name: str | None = None,
    updated_at: str,
) -> MusicSyncAnalysis:
    duration_ms = record.video.duration_ms or (
        record.audio.duration_ms if record.audio is not None else 0
    )
    beat_markers, tempo_bpm = extract_beat_markers(record)

    windows: list[LoudnessWindow] = []
    if record.audio is not None:
        windows = record.audio.loudness_windows

    chorus_sections = detect_chorus_sections(windows, duration_ms)
    drop_sections = detect_drop_sections(windows)
    sections = sorted([*chorus_sections, *drop_sections], key=lambda item: item.start_ms)

    cut_suggestions = build_cut_suggestions(beat_markers, sections)
    transition_suggestions = build_transition_suggestions(sections, beat_markers)
    confidence = compute_overall_confidence(beat_markers, sections, tempo_bpm)
    reasoning = build_reasoning(tempo_bpm, len(beat_markers), sections, len(cut_suggestions))

    if not beat_markers and not sections:
        reasoning = "No beat or section data available; run audio analysis first."
        confidence = 0.1

    return MusicSyncAnalysis(
        media_id=media_id,
        project_id=project_id,
        file_name=file_name,
        tempo_bpm=tempo_bpm,
        beat_markers=beat_markers,
        sections=sections,
        cut_suggestions=cut_suggestions,
        transition_suggestions=transition_suggestions,
        confidence=confidence,
        reasoning=reasoning,
        cache_key=build_cache_key(record.source_fingerprint),
        source_fingerprint=record.source_fingerprint,
        duration_ms=duration_ms or None,
        updated_at=updated_at,
    )
