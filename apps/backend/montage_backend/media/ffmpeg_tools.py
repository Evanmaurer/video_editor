from __future__ import annotations

import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class FFmpegAvailability:
    available: bool
    ffmpeg_bin: str
    ffprobe_bin: str
    message: str | None = None


def detect_ffmpeg(
    ffmpeg_bin: str = "ffmpeg",
    ffprobe_bin: str = "ffprobe",
) -> FFmpegAvailability:
    ffmpeg_path = shutil.which(ffmpeg_bin)
    ffprobe_path = shutil.which(ffprobe_bin)
    if ffmpeg_path and ffprobe_path:
        return FFmpegAvailability(
            available=True,
            ffmpeg_bin=ffmpeg_path,
            ffprobe_bin=ffprobe_path,
        )

    missing = []
    if not ffmpeg_path:
        missing.append(ffmpeg_bin)
    if not ffprobe_path:
        missing.append(ffprobe_bin)
    return FFmpegAvailability(
        available=False,
        ffmpeg_bin=ffmpeg_bin,
        ffprobe_bin=ffprobe_bin,
        message=(
            f"FFmpeg is not installed ({', '.join(missing)} not found on PATH). "
            "Install with: brew install ffmpeg"
        ),
    )


def require_ffmpeg(
    ffmpeg_bin: str = "ffmpeg",
    ffprobe_bin: str = "ffprobe",
) -> None:
    from montage_backend.models.domain.media import MediaProcessingError

    info = detect_ffmpeg(ffmpeg_bin, ffprobe_bin)
    if not info.available:
        raise MediaProcessingError(info.message or "FFmpeg is not installed")
