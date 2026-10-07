from pathlib import Path

import numpy as np

from app.services.face_engine import OpenCVFaceEngine

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"


def main() -> None:
    engine = OpenCVFaceEngine(
        MODELS / "face_detection_yunet_2023mar.onnx",
        MODELS / "face_recognition_sface_2021dec.onnx",
    )
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    result = engine.detect_and_embed(blank)
    if result:
        raise RuntimeError("Blank image unexpectedly produced a face")
    print("OpenCV YuNet/SFace models loaded and inference executed successfully.")


if __name__ == "__main__":
    main()
