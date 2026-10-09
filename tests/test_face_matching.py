import numpy as np

from app.services.face_engine import OpenCVFaceEngine


def test_cosine_similarity_identical_vectors():
    vector = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    assert OpenCVFaceEngine.cosine_similarity(vector, vector) > 0.999


def test_cosine_similarity_orthogonal_vectors():
    first = np.array([1.0, 0.0], dtype=np.float32)
    second = np.array([0.0, 1.0], dtype=np.float32)
    assert abs(OpenCVFaceEngine.cosine_similarity(first, second)) < 0.0001


def test_cosine_similarity_zero_vector_is_safe():
    first = np.array([0.0, 0.0], dtype=np.float32)
    second = np.array([1.0, 0.0], dtype=np.float32)
    assert OpenCVFaceEngine.cosine_similarity(first, second) == 0.0
