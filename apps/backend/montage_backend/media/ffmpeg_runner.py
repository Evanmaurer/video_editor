from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from montage_backend.media.ffmpeg_tools import require_ffmpeg

ProgressCallback = Callable[[str, float, str], Awaitable[None] | None]
LogLineCallback = Callable[[str], Awaitable[None] | None]

_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")


@dataclass
class ProcessingContext:
    """Cancellation and progress reporting for media operations."""

    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    pause_event: asyncio.Event = field(default_factory=asyncio.Event)
    on_progress: ProgressCallback | None = None
    on_log_line: LogLineCallback | None = None

    def check_cancelled(self) -> None:
        from montage_backend.models.domain.media import (
            ProcessingCancelledError,
            ProcessingPausedError,
        )

        if self.cancel_event.is_set():
            raise ProcessingCancelledError("Media processing was cancelled")
        if self.pause_event.is_set():
            raise ProcessingPausedError("Media processing was paused")

    async def report(self, operation: str, progress: float, message: str) -> None:
        if self.on_progress is None:
            return
        result = self.on_progress(operation, progress, message)
        if asyncio.iscoroutine(result):
            await result


def parse_ffmpeg_time_seconds(line: str) -> float | None:
    match = _TIME_RE.search(line)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


class FFmpegRunner:
    """Async FFmpeg/ffprobe subprocess runner with cancel and progress support."""

    def __init__(
        self,
        ffmpeg_bin: str = "ffmpeg",
        ffprobe_bin: str = "ffprobe",
    ) -> None:
        self._ffmpeg_bin = ffmpeg_bin
        self._ffprobe_bin = ffprobe_bin
        self._active_processes: dict[int, asyncio.subprocess.Process] = {}

    async def run(
        self,
        args: list[str],
        *,
        ctx: ProcessingContext | None = None,
        operation: str = "ffmpeg",
        duration_seconds: float | None = None,
    ) -> str:
        ctx = ctx or ProcessingContext()
        ctx.check_cancelled()
        require_ffmpeg(self._ffmpeg_bin, self._ffprobe_bin)

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            from montage_backend.models.domain.media import MediaProcessingError

            raise MediaProcessingError(
                f"FFmpeg is not installed ({args[0]} not found on PATH). "
                "Install with: brew install ffmpeg",
            ) from exc
        self._active_processes[id(proc)] = proc

        stderr_chunks: list[bytes] = []

        async def read_stderr() -> None:
            assert proc.stderr is not None
            while True:
                chunk = await proc.stderr.readline()
                if not chunk:
                    break
                stderr_chunks.append(chunk)
                line = chunk.decode(errors="replace").rstrip("\n")
                if line and ctx.on_log_line is not None:
                    result = ctx.on_log_line(line)
                    if asyncio.iscoroutine(result):
                        await result
                if ctx.cancel_event.is_set() or ctx.pause_event.is_set():
                    proc.terminate()
                    break
                if duration_seconds and duration_seconds > 0:
                    current = parse_ffmpeg_time_seconds(line)
                    if current is not None:
                        progress = min(current / duration_seconds, 0.99)
                        await ctx.report(operation, progress, line.strip())

        try:
            await asyncio.gather(read_stderr(), proc.wait())
        finally:
            self._active_processes.pop(id(proc), None)

        stderr = b"".join(stderr_chunks).decode(errors="replace")
        if ctx.pause_event.is_set():
            from montage_backend.models.domain.media import ProcessingPausedError

            raise ProcessingPausedError("Media processing was paused")
        ctx.check_cancelled()

        if proc.returncode != 0:
            from montage_backend.models.domain.media import MediaProcessingError

            raise MediaProcessingError(
                f"FFmpeg command failed ({proc.returncode}): {' '.join(args)}",
                details={"stderr": stderr[-2000:]},
            )
        return stderr

    async def run_capture_stdout(
        self,
        args: list[str],
        *,
        ctx: ProcessingContext | None = None,
    ) -> bytes:
        ctx = ctx or ProcessingContext()
        ctx.check_cancelled()
        require_ffmpeg(self._ffmpeg_bin, self._ffprobe_bin)

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            from montage_backend.models.domain.media import MediaProcessingError

            raise MediaProcessingError(
                f"FFmpeg is not installed ({args[0]} not found on PATH). "
                "Install with: brew install ffmpeg",
            ) from exc
        self._active_processes[id(proc)] = proc
        try:
            stdout, stderr = await proc.communicate()
        finally:
            self._active_processes.pop(id(proc), None)

        ctx.check_cancelled()
        if proc.returncode != 0:
            from montage_backend.models.domain.media import MediaProcessingError

            raise MediaProcessingError(
                f"FFmpeg command failed ({proc.returncode}): {' '.join(args)}",
                details={"stderr": stderr.decode(errors="replace")[-2000:]},
            )
        return stdout

    async def run_json(self, args: list[str], *, ctx: ProcessingContext | None = None) -> dict[str, Any]:
        ctx = ctx or ProcessingContext()
        ctx.check_cancelled()
        require_ffmpeg(self._ffmpeg_bin, self._ffprobe_bin)

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            from montage_backend.models.domain.media import MediaProcessingError

            raise MediaProcessingError(
                f"FFmpeg is not installed ({args[0]} not found on PATH). "
                "Install with: brew install ffmpeg",
            ) from exc
        self._active_processes[id(proc)] = proc
        try:
            stdout, stderr = await proc.communicate()
        finally:
            self._active_processes.pop(id(proc), None)

        ctx.check_cancelled()
        if proc.returncode != 0:
            from montage_backend.models.domain.media import MediaProcessingError

            raise MediaProcessingError(
                f"ffprobe command failed ({proc.returncode})",
                details={"stderr": stderr.decode(errors="replace")[-2000:]},
            )
        return json.loads(stdout.decode())

    def cancel_all(self) -> None:
        for proc in list(self._active_processes.values()):
            if proc.returncode is None:
                proc.terminate()

    @property
    def ffmpeg_bin(self) -> str:
        return self._ffmpeg_bin

    @property
    def ffprobe_bin(self) -> str:
        return self._ffprobe_bin
