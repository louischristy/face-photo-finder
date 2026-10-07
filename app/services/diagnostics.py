import platform
import sys
from pathlib import Path

import cv2
import numpy
from PIL import Image


def system_diagnostics(root: Path | None = None) -> dict:
    root = root or Path.cwd()
    models = root / "models"
    detector = models / "face_detection_yunet_2023mar.onnx"
    recognizer = models / "face_recognition_sface_2021dec.onnx"
    data = root / "data"
    checks = {
        "python_supported": (3, 11) <= sys.version_info[:2] < (3, 13),
        "opencv_face_detector": hasattr(cv2, "FaceDetectorYN"),
        "opencv_face_recognizer": hasattr(cv2, "FaceRecognizerSF"),
        "detector_model": detector.is_file() and detector.stat().st_size >= 100_000,
        "recognizer_model": recognizer.is_file() and recognizer.stat().st_size >= 100_000,
        "data_directory_writable": False,
    }
    try:
        data.mkdir(parents=True, exist_ok=True)
        probe = data / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        checks["data_directory_writable"] = True
    except OSError:
        pass
    return {
        "ready": all(checks.values()),
        "platform": platform.system(),
        "platform_release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "opencv": cv2.__version__,
        "numpy": numpy.__version__,
        "pillow": Image.__version__,
        "checks": checks,
    }
