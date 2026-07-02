from __future__ import annotations

import pytest

from montage_backend.analysis.albion.ability.albion_ability_analysis import AlbionAbilityEventType
from montage_backend.analysis.albion.base import AlbionDetectorContext, AlbionDetectorId
from montage_backend.analysis.albion.detectors.highlight_detector import AlbionHighlightDetector
from montage_backend.analysis.albion.highlight.config import get_highlight_config
from montage_backend.analysis.albion.highlight.pipeline import (
    build_detector_cache_key,
    build_highlight_factors,
    compute_highlight_score,
    dedupe_highlight_moments,
    resolve_highlight_signals,
    run_albion_highlight_pipeline,
)
from montage_backend.analysis.albion.highlight.albion_highlight_analysis import AlbionHighlightMoment
from montage_backend.analysis.albion.runtime import build_default_albion_registry


def test_highlight_config_loads_builtin_and_external_default():
    builtin = get_highlight_config("albion-highlight-default")
    assert builtin.id == "albion-highlight-default"
    assert builtin.bomb_quality_weight > 0

    external = get_highlight_config("default")
    assert external.id == "default"
    assert external.kill_reference_count == 5


def test_build_highlight_factors_include_all_required_signals():
    config = get_highlight_config("default")
    signals = resolve_highlight_signals(
        combat_payload={"summary": {"kill_count": 5, "death_count": 0, "fight_count": 1}},
        bomb_payload={"summary": {"bomb_count": 1, "top_bomb_score": 8.4}},
        engagement_payload={
            "summary": {"primary_engagement": "zvz"},
            "tags": [{"score": 8.6}],
        },
        ability_payload={"summary": {"activation_count": 2, "ultimate_count": 1, "unique_ability_count": 2}},
        albion_ocr_payload={"mentions": [{"text": "Enemy killed"}]},
        m3_ocr_payload=None,
        ui_payload={"detections": [{"confidence": 0.8, "element_type": "kill_feed"}]},
        motion_payload={"windows": [{"motion_score": 0.7}]},
        audio_payload={"events": [{"event_type": "peak", "value": 0.8}]},
        config=config,
    )
    factors = build_highlight_factors(signals, config=config)
    factor_ids = {factor.factor_id for factor in factors}
    assert "bomb_quality" in factor_ids
    assert "kill_count" in factor_ids
    assert "team_fight_intensity" in factor_ids
    assert "ability_combinations" in factor_ids
    assert len(factors) == 12


def test_compute_highlight_score_returns_0_to_100():
    config = get_highlight_config("default")
    signals = resolve_highlight_signals(
        combat_payload={"summary": {"kill_count": 5, "death_count": 0, "fight_count": 0}},
        bomb_payload={"summary": {"bomb_count": 1, "top_bomb_score": 8.4}},
        engagement_payload={"summary": {"primary_engagement": "zvz"}, "tags": [{"score": 8.6}]},
        ability_payload=None,
        albion_ocr_payload=None,
        m3_ocr_payload=None,
        ui_payload=None,
        motion_payload=None,
        audio_payload=None,
        config=config,
    )
    factors = build_highlight_factors(signals, config=config)
    score = compute_highlight_score(factors)
    assert 0.0 <= score <= 100.0
    assert score >= 35.0


def test_run_albion_highlight_pipeline_builds_explanation_and_moments():
    result = run_albion_highlight_pipeline(
        source_fingerprint="fp-highlight",
        duration_ms=8000,
        frame_rate=60.0,
        combat_payload={
            "cache_key": "combat:test",
            "entries": [
                {
                    "event_type": "kill",
                    "timestamp_ms": 4000,
                    "window_start_ms": 3500,
                    "window_end_ms": 4500,
                    "confidence": 0.9,
                    "label": "Kill: Enemy",
                    "search_text": "kill enemy",
                    "metadata": {},
                },
            ],
            "summary": {"kill_count": 5, "death_count": 0, "fight_count": 0},
        },
        bomb_payload={
            "cache_key": "bomb:test",
            "summary": {"bomb_count": 1, "top_bomb_score": 8.4},
            "events": [
                {
                    "timestamp_ms": 4000,
                    "window_start_ms": 3500,
                    "window_end_ms": 4500,
                    "confidence": 0.86,
                    "bomb_score": 8.4,
                    "reasoning": "Bomb detected",
                    "search_text": "bomb",
                    "kill_count": 5,
                },
            ],
        },
        engagement_payload={
            "cache_key": "engagement:test",
            "summary": {"primary_engagement": "zvz"},
            "tags": [{"score": 8.6}],
        },
        ability_payload={
            "events": [
                {
                    "event_type": AlbionAbilityEventType.ULTIMATE_ACTIVATION.value,
                    "timestamp_ms": 3950,
                    "window_start_ms": 3500,
                    "window_end_ms": 4500,
                    "confidence": 0.8,
                    "ability_name": "Meteor",
                    "ability_id": "meteor",
                },
            ],
            "summary": {"activation_count": 1, "ultimate_count": 1, "unique_ability_count": 1},
        },
        albion_ocr_payload=None,
        m3_ocr_payload=None,
        ui_payload=None,
        motion_payload=None,
        audio_payload=None,
        config_id="default",
    )
    assert result.highlight_score > 0
    assert "Albion highlight score" in result.explanation
    assert result.summary.factor_count == 12
    assert result.summary.moment_count >= 1
    assert any(factor.contribution > 0 for factor in result.factors)
    assert result.summary.reused_albion_combat is True
    assert result.summary.reused_albion_bomb is True
    assert result.summary.reused_albion_engagement is True


def test_dedupe_highlight_moments_removes_nearby_duplicates():
    moments = [
        AlbionHighlightMoment(
            moment_id="a",
            timestamp_ms=4000,
            window_start_ms=3500,
            window_end_ms=4500,
            moment_score=80.0,
            confidence=0.8,
            moment_type="bomb",
            reasoning="bomb",
            search_text="bomb",
        ),
        AlbionHighlightMoment(
            moment_id="b",
            timestamp_ms=4100,
            window_start_ms=3600,
            window_end_ms=4600,
            moment_score=70.0,
            confidence=0.7,
            moment_type="kill",
            reasoning="kill",
            search_text="kill",
        ),
    ]
    deduped = dedupe_highlight_moments(moments)
    assert len(deduped) == 1
    assert deduped[0].moment_score == 80.0


@pytest.mark.asyncio
async def test_highlight_detector_reuses_upstream_payloads():
    detector = AlbionHighlightDetector(config_id="default")
    ctx = AlbionDetectorContext(
        project_id="p1",
        media_id="m1",
        source_fingerprint="fp-inline-highlight",
        gpu_enabled=False,
        extras={
            "detector_results": {
                "combat": {
                    "payload": {
                        "cache_key": "combat:inline",
                        "duration_ms": 8000,
                        "frame_rate": 60.0,
                        "summary": {"kill_count": 5, "death_count": 0, "fight_count": 0},
                        "entries": [
                            {
                                "event_type": "kill",
                                "timestamp_ms": 4000,
                                "window_start_ms": 3500,
                                "window_end_ms": 4500,
                                "confidence": 0.9,
                                "label": "Kill",
                                "search_text": "kill",
                                "metadata": {},
                            },
                        ],
                    },
                },
                "bomb": {
                    "payload": {
                        "cache_key": "bomb:inline",
                        "summary": {"bomb_count": 1, "top_bomb_score": 8.4},
                        "events": [
                            {
                                "timestamp_ms": 4000,
                                "window_start_ms": 3500,
                                "window_end_ms": 4500,
                                "confidence": 0.86,
                                "bomb_score": 8.4,
                                "reasoning": "Bomb detected",
                                "search_text": "bomb",
                                "kill_count": 5,
                            },
                        ],
                    },
                },
                "engagement": {
                    "payload": {
                        "cache_key": "engagement:inline",
                        "summary": {"primary_engagement": "zvz"},
                        "tags": [{"score": 8.6}],
                    },
                },
            },
        },
    )
    output = await detector.analyze(
        ctx,
        video_path="/tmp/fake.mp4",
        duration_ms=8000,
        frame_rate=60.0,
    )
    assert output.detector_id == AlbionDetectorId.HIGHLIGHT.value
    assert output.payload["highlight_score"] > 0
    assert output.payload["explanation"]
    assert output.payload["summary"]["reused_albion_bomb"] is True


def test_default_albion_registry_includes_highlight_detector():
    registry = build_default_albion_registry()
    assert registry.list_detectors() == [
        "framework_probe",
        "ui",
        "ocr",
        "ability",
        "combat",
        "bomb",
        "engagement",
        "highlight",
    ]
    assert registry.detector_versions()["highlight"] == "albion-highlight-v1.0"
    assert "config=" in build_detector_cache_key(
        "fp",
        frame_rate=60.0,
        config_id="albion-highlight-default",
        config_token="albion-highlight-default@1.0",
        sample_interval_ms=2000,
        window_ms=2000,
        source_flags="combat,bomb",
    )
