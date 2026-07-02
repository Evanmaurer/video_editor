from __future__ import annotations

from montage_backend.models.domain import MontageError
from montage_backend.montage.base import MontageModuleId, MontagePlannerModule


from montage_backend.montage.modules.scoring import ClipScoringModule
from montage_backend.montage.modules.highlights import HighlightDetectionModule
from montage_backend.montage.modules.music_sync import MusicSyncModule
from montage_backend.montage.modules.transitions import TransitionEngineModule
from montage_backend.montage.modules.pacing import PacingEngineModule
from montage_backend.montage.modules.effects import EffectsEngineModule
from montage_backend.montage.modules.draft import DraftGeneratorModule
from montage_backend.montage.modules.feedback import FeedbackLoopModule


class MontageModuleNotFoundError(MontageError):
    code = "MONTAGE_MODULE_NOT_FOUND"


class MontagePlannerRegistry:
    def __init__(self) -> None:
        self._modules: dict[str, MontagePlannerModule] = {}

    def register(self, module: MontagePlannerModule) -> None:
        self._modules[module.module_id.value] = module

    def get(self, module_id: MontageModuleId | str) -> MontagePlannerModule:
        key = module_id.value if isinstance(module_id, MontageModuleId) else module_id
        module = self._modules.get(key)
        if module is None:
            raise MontageModuleNotFoundError(f"Montage module not registered: {key}")
        return module

    def list_modules(self) -> list[str]:
        return sorted(self._modules.keys())


def build_default_montage_registry() -> MontagePlannerRegistry:
    registry = MontagePlannerRegistry()
    registry.register(ClipScoringModule())
    registry.register(HighlightDetectionModule())
    registry.register(MusicSyncModule())
    registry.register(TransitionEngineModule())
    registry.register(PacingEngineModule())
    registry.register(EffectsEngineModule())
    registry.register(DraftGeneratorModule())
    registry.register(FeedbackLoopModule())
    return registry
