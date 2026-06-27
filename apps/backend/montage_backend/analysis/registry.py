from __future__ import annotations

from montage_backend.analysis.base import AnalysisModuleId, Analyzer
from montage_backend.models.domain import MontageError


class AnalyzerNotFoundError(MontageError):
    code = "ANALYZER_NOT_FOUND"


class AnalysisJobNotFoundError(MontageError):
    code = "ANALYSIS_JOB_NOT_FOUND"


class AnalysisCancelledError(MontageError):
    code = "ANALYSIS_CANCELLED"


class AnalysisError(MontageError):
    code = "ANALYSIS_ERROR"


class AnalyzerRegistry:
    def __init__(self) -> None:
        self._analyzers: dict[str, Analyzer] = {}

    def register(self, analyzer: Analyzer) -> None:
        self._analyzers[analyzer.module_id.value] = analyzer

    def get(self, module_id: AnalysisModuleId | str) -> Analyzer:
        key = module_id.value if isinstance(module_id, AnalysisModuleId) else module_id
        analyzer = self._analyzers.get(key)
        if analyzer is None:
            raise AnalyzerNotFoundError(f"Analysis module not registered: {key}")
        return analyzer

    def list_modules(self) -> list[str]:
        return sorted(self._analyzers.keys())


default_registry = AnalyzerRegistry()
