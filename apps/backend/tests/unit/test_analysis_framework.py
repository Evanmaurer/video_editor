from __future__ import annotations

import pytest

from montage_backend.analysis.base import AnalysisModuleId, AnalysisRunContext
from montage_backend.analysis.registry import AnalyzerNotFoundError, AnalyzerRegistry
from montage_backend.analysis.modules.scene import SceneAnalyzer


def test_registry_register_and_get():
    registry = AnalyzerRegistry()
    analyzer = SceneAnalyzer()
    registry.register(analyzer)
    assert registry.get(AnalysisModuleId.SCENE) is analyzer
    assert registry.list_modules() == ["scene"]


def test_registry_missing_module():
    registry = AnalyzerRegistry()
    with pytest.raises(AnalyzerNotFoundError):
        registry.get("motion")


def test_analysis_run_context_cancel():
    ctx = AnalysisRunContext(
        project_id="p1",
        media_id="m1",
        source_fingerprint="fp",
    )
    assert not ctx.cancel_requested
    ctx.cancel()
    assert ctx.cancel_requested
