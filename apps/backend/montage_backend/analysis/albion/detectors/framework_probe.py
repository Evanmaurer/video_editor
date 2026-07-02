from __future__ import annotations

from montage_backend.analysis.albion.base import (
    AlbionDetector,
    AlbionDetectorContext,
    AlbionDetectorEvent,
    AlbionDetectorId,
    AlbionDetectorOutput,
)


class FrameworkProbeDetector(AlbionDetector):
    """Validates the Albion detector framework lifecycle without game-specific logic."""

    detector_id = AlbionDetectorId.FRAMEWORK_PROBE
    version = "framework-probe-v1.0"

    def __init__(self) -> None:
        self._initialized = False

    def cache_key(self, source_fingerprint: str, *, frame_rate: float | None = None) -> str:
        fps_part = f"{frame_rate:.3f}" if frame_rate is not None else "unknown"
        return f"{self.detector_id.value}:{self.version}:{source_fingerprint}:fps={fps_part}"

    async def initialize(self, ctx: AlbionDetectorContext) -> None:
        ctx.check_cancelled()
        self._initialized = True
        await ctx.report(0.0, "Framework probe initialized")

    async def analyze(
        self,
        ctx: AlbionDetectorContext,
        *,
        video_path: str,
        duration_ms: int | None,
        frame_rate: float | None,
    ) -> AlbionDetectorOutput:
        _ = video_path
        ctx.check_cancelled()
        if not self._initialized:
            await self.initialize(ctx)

        await ctx.report(0.5, "Running framework probe")
        event = AlbionDetectorEvent(
            event_type="framework_probe",
            timestamp_ms=0,
            confidence=1.0,
            reasoning="Albion detector framework is operational",
            metadata={
                "duration_ms": duration_ms or 0,
                "frame_rate": frame_rate or 0.0,
                "gpu_enabled": ctx.gpu_enabled,
            },
        )
        await ctx.report(1.0, "Framework probe complete")
        return AlbionDetectorOutput(
            detector_id=self.detector_id.value,
            detector_version=self.version,
            cache_key=self.cache_key(ctx.source_fingerprint, frame_rate=frame_rate),
            confidence=1.0,
            reasoning="Framework probe validated initialize/analyze/progress lifecycle",
            events=[event],
            payload={"initialized": True},
        )

    async def cancel(self, ctx: AlbionDetectorContext) -> None:
        await super().cancel(ctx)
        self._initialized = False
