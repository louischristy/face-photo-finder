from pathlib import Path

import pytest

from app.services.local_storage import validate_local_source, walk_local_images


def test_walk_local_images_is_recursive(tmp_path: Path):
    nested = tmp_path / "camera" / "day-1"
    nested.mkdir(parents=True)
    (nested / "photo.JPG").write_bytes(b"test")
    (nested / "notes.txt").write_text("ignore", encoding="utf-8")
    items = list(walk_local_images(str(tmp_path)))
    assert len(items) == 1
    assert items[0]["name"] == "photo.JPG"
    assert items[0]["source_item_key"] == str(Path("camera") / "day-1" / "photo.JPG")


def test_missing_external_drive_path_is_reported(tmp_path: Path):
    with pytest.raises(ValueError, match="not currently available"):
        validate_local_source(str(tmp_path / "unplugged-drive"))
