from pathlib import Path

import cv2 as cv
import numpy as np
from pillow_heif import register_heif_opener
from PIL import Image
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Face, Photo, PhotoSource
from app.services.face_engine import OpenCVFaceEngine

register_heif_opener()


def embedding_to_bytes(value: np.ndarray) -> bytes:
    return np.asarray(value, dtype=np.float32).tobytes()


def embedding_from_bytes(value: bytes, dim: int) -> np.ndarray:
    result = np.frombuffer(value, dtype=np.float32)
    if result.size != dim:
        raise ValueError("Stored face embedding dimension is invalid")
    return result


def _local_photo_path(source: PhotoSource, photo: Photo) -> Path:
    root = Path(source.source_uri).expanduser().resolve()
    path = (root / photo.source_item_key).resolve()
    if root != path and root not in path.parents:
        raise ValueError("Photo path escapes the configured source folder")
    if not path.is_file():
        raise FileNotFoundError(f"Photo is unavailable: {photo.name}")
    return path


def load_local_image(source: PhotoSource, photo: Photo) -> np.ndarray:
    path = _local_photo_path(source, photo)
    with Image.open(path) as image:
        rgb = np.asarray(image.convert("RGB"))
    return cv.cvtColor(rgb, cv.COLOR_RGB2BGR)


def index_local_photo(session: Session, photo: Photo, engine: OpenCVFaceEngine) -> int:
    source = session.get(PhotoSource, photo.source_id)
    if not source or source.source_type != "local_folder":
        raise ValueError("This indexing path currently accepts local/external sources only")
    image = load_local_image(source, photo)
    detected = engine.detect_and_embed(image)
    session.execute(delete(Face).where(Face.photo_id == photo.id))
    for item in detected:
        x, y, w, h = item.bbox
        session.add(Face(project_id=photo.project_id, photo_id=photo.id, source_id=photo.source_id, bbox_x=x, bbox_y=y, bbox_w=w, bbox_h=h, detector_score=item.confidence, embedding=embedding_to_bytes(item.embedding), embedding_dim=int(item.embedding.size)))
    photo.face_count = len(detected)
    photo.indexed = True
    session.commit()
    return len(detected)


def index_pending_local_photos(session: Session, project_id: int, engine: OpenCVFaceEngine, source_ids: tuple[int, ...] = ()) -> dict[str, int]:
    query = select(Photo).join(PhotoSource, Photo.source_id == PhotoSource.id).where(Photo.project_id == project_id, Photo.indexed.is_(False), PhotoSource.source_type == "local_folder")
    if source_ids:
        query = query.where(Photo.source_id.in_(source_ids))
    photos = session.scalars(query.order_by(Photo.id)).all()
    processed = faces = failed = 0
    for photo in photos:
        try:
            faces += index_local_photo(session, photo, engine)
            processed += 1
        except Exception:
            session.rollback()
            failed += 1
    return {"processed": processed, "faces": faces, "failed": failed}
