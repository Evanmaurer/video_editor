from __future__ import annotations

from dataclasses import dataclass

from montage_backend.models.domain.render import RenderCodec, RenderPresetInfo


@dataclass(frozen=True)
class RenderPreset:
    id: str
    label: str
    codec: RenderCodec
    width: int
    height: int
    frame_rate: float
    video_codec: str
    crf: int
    preset: str
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    pixel_format: str = "yuv420p"
    container: str = "mp4"


RENDER_PRESETS: dict[str, RenderPreset] = {
    "h264_1080p60": RenderPreset(
        id="h264_1080p60",
        label="H.264 · 1080p · 60 FPS",
        codec=RenderCodec.H264,
        width=1920,
        height=1080,
        frame_rate=60.0,
        video_codec="libx264",
        crf=18,
        preset="medium",
    ),
    "h264_1440p60": RenderPreset(
        id="h264_1440p60",
        label="H.264 · 1440p · 60 FPS",
        codec=RenderCodec.H264,
        width=2560,
        height=1440,
        frame_rate=60.0,
        video_codec="libx264",
        crf=20,
        preset="medium",
    ),
    "h264_4k60": RenderPreset(
        id="h264_4k60",
        label="H.264 · 4K · 60 FPS",
        codec=RenderCodec.H264,
        width=3840,
        height=2160,
        frame_rate=60.0,
        video_codec="libx264",
        crf=22,
        preset="medium",
    ),
}


def list_preset_infos(hw_encoders: set[str]) -> list[RenderPresetInfo]:
    items: list[RenderPresetInfo] = []
    for preset in RENDER_PRESETS.values():
        hw = _hardware_encoder_for_preset(preset, hw_encoders)
        items.append(
            RenderPresetInfo(
                id=preset.id,
                label=preset.label,
                codec=preset.codec,
                width=preset.width,
                height=preset.height,
                frame_rate=preset.frame_rate,
                hardware_available=hw is not None,
            ),
        )
    return items


def get_preset(preset_id: str) -> RenderPreset:
    preset = RENDER_PRESETS.get(preset_id)
    if preset is None:
        raise KeyError(preset_id)
    return preset


def _hardware_encoder_for_preset(preset: RenderPreset, hw_encoders: set[str]) -> str | None:
    if preset.codec == RenderCodec.H264:
        for name in ("h264_videotoolbox", "h264_nvenc", "h264_qsv"):
            if name in hw_encoders:
                return name
    return None


def resolve_video_encoder(
    preset: RenderPreset,
    hw_encoders: set[str],
    *,
    use_hardware: bool,
) -> tuple[str, dict[str, str]]:
    if use_hardware:
        hw = _hardware_encoder_for_preset(preset, hw_encoders)
        if hw:
            if hw.endswith("_videotoolbox"):
                return hw, {"q:v": str(preset.crf)}
            if hw.endswith("_nvenc"):
                return hw, {"preset": "p4", "cq": str(preset.crf)}
            return hw, {"global_quality": str(preset.crf)}

    return preset.video_codec, {"crf": str(preset.crf), "preset": preset.preset}
