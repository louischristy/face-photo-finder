from dataclasses import dataclass
from pathlib import Path

import cv2 as cv
import numpy as np


@dataclass
class DetectedFace:
    bbox: tuple[int, int, int, int]
    confidence: float
    embedding: np.ndarray


class OpenCVFaceEngine:
    """Local face detector/embedding engine using OpenCV YuNet + SFace ONNX models."""

    def __init__(self, detector_model: Path, recognizer_model: Path, score_threshold: float = 0.75):
        if not detector_model.exists() or not recognizer_model.exists():
            raise FileNotFoundError("Face models are not installed. Run the model setup step first.")
        self.detector = cv.FaceDetectorYN.create(str(detector_model), "", (320, 320), score_threshold, 0.3, 5000)
        self.recognizer = cv.FaceRecognizerSF.create(str(recognizer_model), "")

    def _detect(self, image_bgr: np.ndarray, threshold: float) -> np.ndarray | None:
        height, width = image_bgr.shape[:2]
        self.detector.setInputSize((width, height))
        self.detector.setScoreThreshold(threshold)
        _, faces = self.detector.detect(image_bgr)
        return faces

    def detect_and_embed(self, image_bgr: np.ndarray) -> list[DetectedFace]:
        # First preserve the established behaviour for indexed/event photographs.
        working = image_bgr
        scale = 1.0
        faces = self._detect(working, 0.75)

        # Direct phone selfies can be high-resolution images where the face occupies a
        # relatively small part of the frame. If the normal pass misses it, retry on a
        # detector-friendly copy and slightly relax YuNet's confidence threshold.
        if faces is None:
            height, width = image_bgr.shape[:2]
            longest = max(height, width)
            if longest > 1280:
                scale = 1280.0 / longest
                working = cv.resize(image_bgr, (max(1, round(width * scale)), max(1, round(height * scale))), interpolation=cv.INTER_AREA)
            faces = self._detect(working, 0.55)

        if faces is None:
            return []

        results: list[DetectedFace] = []
        for face in faces:
            aligned = self.recognizer.alignCrop(working, face)
            feature = self.recognizer.feature(aligned).flatten().astype(np.float32)
            norm = float(np.linalg.norm(feature))
            if norm:
                feature /= norm
            x, y, w, h = [int(v / scale) for v in face[:4]] if scale != 1.0 else [int(v) for v in face[:4]]
            results.append(DetectedFace((x, y, w, h), float(face[-1]), feature))
        return results

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        a = np.asarray(a, dtype=np.float32).flatten()
        b = np.asarray(b, dtype=np.float32).flatten()
        denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
        return float(np.dot(a, b) / denominator) if denominator else 0.0
