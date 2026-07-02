from montage_backend.analysis.base import AnalysisModuleId, AnalysisOutput, AnalysisProgress, AnalysisRunContext, Analyzer
from montage_backend.analysis.registry import AnalyzerRegistry, AnalyzerNotFoundError, default_registry
from montage_backend.analysis.modules.albion import AlbionAnalyzer
from montage_backend.analysis.modules.audio import AudioAnalyzer
from montage_backend.analysis.modules.motion import MotionAnalyzer
from montage_backend.analysis.modules.embedding import EmbeddingAnalyzer
from montage_backend.analysis.modules.object import ObjectAnalyzer
from montage_backend.analysis.modules.ocr import OcrAnalyzer
from montage_backend.analysis.modules.scene import SceneAnalyzer

__all__ = [
    "AnalysisModuleId",
    "AnalysisOutput",
    "AnalysisProgress",
    "AnalysisRunContext",
    "Analyzer",
    "AnalyzerNotFoundError",
    "AnalyzerRegistry",
    "SceneAnalyzer",
    "MotionAnalyzer",
    "AudioAnalyzer",
    "OcrAnalyzer",
    "ObjectAnalyzer",
    "EmbeddingAnalyzer",
    "AlbionAnalyzer",
    "default_registry",
]

default_registry.register(SceneAnalyzer())
default_registry.register(MotionAnalyzer())
default_registry.register(AudioAnalyzer())
default_registry.register(OcrAnalyzer())
default_registry.register(ObjectAnalyzer())
default_registry.register(EmbeddingAnalyzer())
default_registry.register(AlbionAnalyzer())
