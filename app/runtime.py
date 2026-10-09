import os
import platform
import sys
from pathlib import Path

APP_DIR_NAME = "Auroara Face Photo Finder"


def is_packaged() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    if is_packaged():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent.parent


def application_data_dir() -> Path:
    override = os.getenv("AUROARA_DATA_DIR")
    if override:
        path = Path(override).expanduser().resolve()
    elif not is_packaged():
        path = bundle_dir() / "data"
    elif platform.system() == "Darwin":
        path = Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    elif platform.system() == "Windows":
        root = Path(os.getenv("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        path = root / "Auroara" / "Face Photo Finder"
    else:
        path = Path(os.getenv("XDG_DATA_HOME") or (Path.home() / ".local" / "share")) / "auroara-face-photo-finder"
    path.mkdir(parents=True, exist_ok=True)
    return path


def resource_path(*parts: str) -> Path:
    return bundle_dir().joinpath(*parts)
