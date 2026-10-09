import mimetypes
from collections.abc import Iterator
from pathlib import Path

SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}


def validate_local_source(path_value: str) -> Path:
    path = Path(path_value).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"Folder is not currently available: {path}")
    if not path.is_dir():
        raise ValueError(f"Source must be a folder: {path}")
    return path


def walk_local_images(root_value: str) -> Iterator[dict]:
    """Recursively discover supported images on an internal or external mounted drive."""
    root = validate_local_source(root_value)
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        stat = path.stat()
        yield {
            "source_item_key": str(path.relative_to(root)),
            "name": path.name,
            "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            "modified_time": str(stat.st_mtime_ns),
            "size": stat.st_size,
            "original_uri": path.as_uri(),
            "absolute_path": str(path),
        }
