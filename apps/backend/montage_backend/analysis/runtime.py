from __future__ import annotations

from dataclasses import dataclass

from montage_backend.media.ffmpeg_tools import detect_ffmpeg
from montage_backend.services.project_service import ProjectService


@dataclass(frozen=True)
class AnalysisRuntime:
    gpu_available: bool
    gpu_name: str | None
    ffmpeg_available: bool
    prefer_gpu: bool

    @property
    def use_gpu(self) -> bool:
        return self.prefer_gpu and self.gpu_available


async def build_analysis_runtime(
    project_service: ProjectService,
    *,
    gpu_enabled: bool = True,
) -> AnalysisRuntime:
    gpu = project_service.get_gpu_info(gpu_enabled)
    ffmpeg = detect_ffmpeg()
    return AnalysisRuntime(
        gpu_available=gpu.available,
        gpu_name=gpu.name,
        ffmpeg_available=ffmpeg.available,
        prefer_gpu=gpu_enabled and gpu.available,
    )
