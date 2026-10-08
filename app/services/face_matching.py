import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Face
from app.services.face_indexer import embedding_from_bytes

# Strict remains unchanged because real-world testing showed good precision.
# Recommended provides a controlled middle ground before the deliberately
# wider Balanced and Broad diagnostic/discovery modes.
SEARCH_THRESHOLDS = {
    "strict": 0.50,
    "recommended": 0.46,
    "balanced": 0.42,
    "broad": 0.34,
}


def find_similar_faces(session: Session, project_id: int, reference: np.ndarray, source_ids: tuple[int, ...] = (), mode: str = "recommended") -> list[tuple[Face, float]]:
    threshold = SEARCH_THRESHOLDS.get(mode)
    if threshold is None:
        raise ValueError("Search mode must be strict, recommended, balanced, or broad")
    query = select(Face).where(Face.project_id == project_id)
    if source_ids:
        query = query.where(Face.source_id.in_(source_ids))
    faces = session.scalars(query).all()
    reference = np.asarray(reference, dtype=np.float32).flatten()
    norm = float(np.linalg.norm(reference))
    if norm:
        reference /= norm
    results = []
    for face in faces:
        vector = embedding_from_bytes(face.embedding, face.embedding_dim)
        score = float(np.dot(reference, vector))
        if score >= threshold:
            results.append((face, score))
    return sorted(results, key=lambda item: item[1], reverse=True)
