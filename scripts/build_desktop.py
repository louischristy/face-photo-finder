import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "packaging" / "auroara_face_photo_finder.spec"
MODELS = (
    ROOT / "models" / "face_detection_yunet_2023mar.onnx",
    ROOT / "models" / "face_recognition_sface_2021dec.onnx",
)


def main() -> None:
    missing = [path for path in MODELS if not path.exists()]
    if missing:
        names = ", ".join(path.name for path in missing)
        raise SystemExit(f"Missing face models: {names}. Run: python setup_models.py")
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(SPEC)], cwd=ROOT, check=True)
    print(f"Desktop build complete: {ROOT / 'dist'}")


if __name__ == "__main__":
    main()
