from __future__ import annotations

import asyncio
import shutil
from functools import lru_cache


async def detect_hardware_encoders(ffmpeg_bin: str) -> set[str]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _detect_hardware_encoders_sync, ffmpeg_bin)


@lru_cache(maxsize=4)
def _detect_hardware_encoders_sync(ffmpeg_bin: str) -> set[str]:
    ffmpeg_path = shutil.which(ffmpeg_bin) or ffmpeg_bin
    import subprocess

    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-encoders"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return set()

    encoders: set[str] = set()
    targets = {
        "h264_videotoolbox",
        "hevc_videotoolbox",
        "av1_videotoolbox",
        "h264_nvenc",
        "hevc_nvenc",
        "av1_nvenc",
        "h264_qsv",
        "hevc_qsv",
        "av1_qsv",
        "libx264",
        "libx265",
        "libsvtav1",
    }
    for line in result.stdout.splitlines():
        for name in targets:
            if f" {name} " in line or line.strip().endswith(name):
                encoders.add(name)
    return encoders
