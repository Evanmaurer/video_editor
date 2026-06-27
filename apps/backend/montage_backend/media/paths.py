from __future__ import annotations

from pathlib import Path

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


def expand_import_paths(paths: list[str]) -> list[Path]:
    """Expand folders and files into a flat list of video file paths."""
    discovered: list[Path] = []
    seen: set[str] = set()

    for raw in paths:
        path = Path(raw).expanduser().resolve()
        if path.is_dir():
            for ext in VIDEO_EXTENSIONS:
                for candidate in sorted(path.rglob(f"*{ext}")):
                    key = str(candidate)
                    if key not in seen and candidate.is_file():
                        seen.add(key)
                        discovered.append(candidate)
        elif path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
            key = str(path)
            if key not in seen:
                seen.add(key)
                discovered.append(path)

    return discovered
