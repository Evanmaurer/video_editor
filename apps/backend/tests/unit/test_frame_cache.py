from __future__ import annotations

from montage_backend.playback.playback_service import FrameCache


def test_frame_cache_lru_eviction():
    cache = FrameCache(max_entries=2, max_bytes=1024 * 1024)
    cache.put("a", b"x" * 10)
    cache.put("b", b"y" * 10)
    cache.put("c", b"z" * 10)
    assert cache.get("a") is None
    assert cache.get("b") is not None
    assert cache.get("c") is not None


def test_frame_cache_hit_rate():
    cache = FrameCache(max_entries=10)
    cache.put("k", b"data")
    assert cache.get("k") is not None
    assert cache.get("missing") is None
    assert cache.cache_hit_rate == 0.5


def test_frame_cache_contains_without_stats():
    cache = FrameCache(max_entries=10)
    cache.put("k", b"data")
    assert cache.contains("k") is True
    assert cache.contains("other") is False
    assert cache.hits == 0
    assert cache.misses == 0
