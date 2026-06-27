from __future__ import annotations

from pathlib import Path

from montage_backend.media.paths import expand_import_paths


def test_expand_import_paths_folder_and_files(tmp_path: Path) -> None:
    folder = tmp_path / "footage"
    nested = folder / "nested"
    nested.mkdir(parents=True)
    clip_a = folder / "a.mp4"
    clip_b = nested / "b.mov"
    ignored = folder / "notes.txt"
    clip_a.write_bytes(b"a")
    clip_b.write_bytes(b"b")
    ignored.write_text("ignore")

    single = tmp_path / "solo.webm"
    single.write_bytes(b"solo")

    expanded = expand_import_paths([str(folder), str(single), str(single)])
    names = {path.name for path in expanded}
    assert names == {"a.mp4", "b.mov", "solo.webm"}
