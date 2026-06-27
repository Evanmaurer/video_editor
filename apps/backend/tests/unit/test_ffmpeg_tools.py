from __future__ import annotations

from unittest.mock import patch

import pytest

from montage_backend.media.ffmpeg_tools import detect_ffmpeg, require_ffmpeg
from montage_backend.models.domain.media import MediaProcessingError


def test_detect_ffmpeg_when_missing() -> None:
    with patch("montage_backend.media.ffmpeg_tools.shutil.which", return_value=None):
        info = detect_ffmpeg()
    assert info.available is False
    assert "brew install ffmpeg" in (info.message or "")


def test_require_ffmpeg_raises_clear_error() -> None:
    with patch("montage_backend.media.ffmpeg_tools.shutil.which", return_value=None):
        with pytest.raises(MediaProcessingError, match="brew install ffmpeg"):
            require_ffmpeg()
