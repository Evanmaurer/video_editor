from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from montage_backend.media.ffmpeg_runner import FFmpegRunner, ProcessingContext
from montage_backend.media.processor import MediaProcessor
from montage_backend.models.domain.media import (
    CorruptMediaError,
    ProcessingCancelledError,
    VideoProbeResult,
)


def _probe_payload() -> dict:
    return {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1280,
                "height": 720,
                "avg_frame_rate": "30/1",
                "nb_frames": "90",
            },
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "48000",
            },
        ],
        "format": {
            "duration": "3.0",
            "bit_rate": "2500000",
        },
    }


@pytest.fixture
def video_file(tmp_path: Path) -> Path:
    path = tmp_path / "sample.mp4"
    path.write_bytes(b"fake-video")
    return path


@pytest.fixture
def mock_runner() -> FFmpegRunner:
    runner = FFmpegRunner(ffmpeg_bin="ffmpeg", ffprobe_bin="ffprobe")
    runner.run_json = AsyncMock(return_value=_probe_payload())  # type: ignore[method-assign]
    runner.run = AsyncMock(return_value="")  # type: ignore[method-assign]
    runner.run_capture_stdout = AsyncMock(return_value=b"\x00\x00\x00\x00" * 64)  # type: ignore[method-assign]
    return runner


@pytest.fixture
def processor(mock_runner: FFmpegRunner) -> MediaProcessor:
    return MediaProcessor(runner=mock_runner)


@pytest.mark.asyncio
async def test_probe_parses_metadata(processor: MediaProcessor, video_file: Path) -> None:
    result = await processor.probe(video_file)
    assert isinstance(result, VideoProbeResult)
    assert result.width == 1280
    assert result.height == 720
    assert result.frame_rate == 30.0
    assert result.codec == "h264"
    assert result.duration_ms == 3000
    assert result.frame_count == 90
    assert result.audio_sample_rate == 48000
    assert result.bitrate == 2_500_000


@pytest.mark.asyncio
async def test_probe_missing_file_raises(processor: MediaProcessor, tmp_path: Path) -> None:
    with pytest.raises(CorruptMediaError):
        await processor.probe(tmp_path / "missing.mp4")


@pytest.mark.asyncio
async def test_generate_proxy_invokes_ffmpeg(
    processor: MediaProcessor,
    mock_runner: FFmpegRunner,
    video_file: Path,
    tmp_path: Path,
) -> None:
    output = tmp_path / "proxy.mp4"
    await processor.generate_proxy(video_file, output)
    mock_runner.run.assert_called()
    args = mock_runner.run.call_args.args[0]
    assert "libx264" in args
    assert str(output) in args


@pytest.mark.asyncio
async def test_generate_waveform_writes_json(
    processor: MediaProcessor,
    video_file: Path,
    tmp_path: Path,
) -> None:
    output = tmp_path / "waveform.json"
    await processor.generate_waveform(video_file, output)
    data = json.loads(output.read_text())
    assert "samples" in data
    assert len(data["samples"]) == MediaProcessor.WAVEFORM_SAMPLES


@pytest.mark.asyncio
async def test_process_import_creates_cache_artifacts(
    processor: MediaProcessor,
    video_file: Path,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    manifest = await processor.process_import(video_file, project_root, "abc-123")
    assert manifest.probe.width == 1280
    assert Path(manifest.paths.proxy_path).parent.exists()
    assert Path(manifest.paths.manifest_path).is_file()


@pytest.mark.asyncio
async def test_cancel_during_processing(
    processor: MediaProcessor,
    video_file: Path,
) -> None:
    ctx = ProcessingContext()
    ctx.cancel_event.set()

    with pytest.raises(ProcessingCancelledError):
        await processor.probe(video_file, ctx=ctx)


@pytest.mark.asyncio
async def test_progress_callback_called(
    processor: MediaProcessor,
    video_file: Path,
) -> None:
    events: list[tuple[str, float]] = []

    async def on_progress(operation: str, progress: float, _message: str) -> None:
        events.append((operation, progress))

    ctx = ProcessingContext(on_progress=on_progress)
    await processor.probe(video_file, ctx=ctx)
    assert ("probe", 0.0) in events
    assert ("probe", 1.0) in events
