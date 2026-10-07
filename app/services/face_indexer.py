from io import BytesIO
from pathlib import Path

import cv2 as cv
import numpy as np
from pillow_heif import register_heif_opener
from PIL import Image, ImageOps
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Face, Photo, PhotoSource, StorageAccount
from app.services.face_engine import OpenCVFaceEngine
from app.services.google_drive import GoogleDriveClient

register_heif_opener()


def embedding_to_bytes(value: np.ndarray) -> bytes:
    return np.asarray(value, dtype=np.float32).tobytes()


def embedding_from_bytes(value: bytes, dim: int) -> np.ndarray:
    result = np.frombuffer(value, dtype=np.float32)
    if result.size != dim:
        raise ValueError("Stored face embedding dimension is invalid")
    return result


def local_photo_path(source: PhotoSource, photo: Photo) -> Path:
    root = Path(source.source_uri).expanduser().resolve()
    path = (root / photo.source_item_key).resolve()
    if root != path and root not in path.parents:
        raise ValueError("Photo path escapes the configured source folder")
    if not path.is_file():
        raise FileNotFoundError(f"Photo is unavailable: {photo.name}")
    return path


def image_bytes_to_bgr(data: bytes) -> np.ndarray:
    with Image.open(BytesIO(data)) as image:
        corrected = ImageOps.exif_transpose(image)
        rgb = np.asarray(corrected.convert("RGB"))
    return cv.cvtColor(rgb, cv.COLOR_RGB2BGR)


def load_local_image(source: PhotoSource, photo: Photo) -> np.ndarray:
    path = local_photo_path(source, photo)
    return image_bytes_to_bgr(path.read_bytes())


def _store_detected_faces(session: Session, photo: Photo, detected) -> int:
    session.execute(delete(Face).where(Face.photo_id == photo.id))
    for item in detected:
        x, y, w, h = item.bbox
        session.add(Face(project_id=photo.project_id, photo_id=photo.id, source_id=photo.source_id, bbox_x=x, bbox_y=y, bbox_w=w, bbox_h=h, detector_score=item.confidence, embedding=embedding_to_bytes(item.embedding), embedding_dim=int(item.embedding.size)))
    photo.face_count = len(detected)
    photo.indexed = True
    session.commit()
    return len(detected)


def index_local_photo(session: Session, photo: Photo, engine: OpenCVFaceEngine) -> int:
    source = session.get(PhotoSource, photo.source_id)
    if not source or source.source_type != "local_folder":
        raise ValueError("This indexing path accepts local/external sources only")
    return _store_detected_faces(session, photo, engine.detect_and_embed(load_local_image(source, photo)))


def google_client_for_source(session: Session, source: PhotoSource, credentials_path: Path = Path("credentials.json"), tokens_dir: Path = Path("data/tokens")) -> GoogleDriveClient:
    account = session.get(StorageAccount, source.storage_account_id) if source.storage_account_id else None
    if not account or not account.token_key:
        raise ValueError("Google Drive source must be assigned to an authenticated Google account")
    return GoogleDriveClient(credentials_path, tokens_dir / account.token_key)


def google_photo_bytes(session: Session, source: PhotoSource, photo: Photo) -> bytes:
    if source.source_type != "google_drive":
        raise ValueError("Photo is not from Google Drive")
    return google_client_for_source(session, source).download_file(photo.source_item_key)


def index_google_photo(session: Session, photo: Photo, engine: OpenCVFaceEngine) -> int:
    source = session.get(PhotoSource, photo.source_id)
    if not source or source.source_type != "google_drive":
        raise ValueError("This indexing path accepts Google Drive sources only")
    data = google_photo_bytes(session, source, photo)
    detected = engine.detect_and_embed(image_bytes_to_bgr(data))
    del data
    return _store_detected_faces(session, photo, detected)


def index_pending_photos(session: Session, project_id: int, engine: OpenCVFaceEngine, source_ids: tuple[int, ...] = ()) -> dict[str, int]:
    query = select(Photo).join(PhotoSource, Photo.source_id == PhotoSource.id).where(Photo.project_id == project_id, Photo.indexed.is_(False), PhotoSource.source_type.in_(("local_folder", "google_drive")))
    if source_ids:
        query = query.where(Photo.source_id.in_(source_ids))
    photos = session.scalars(query.order_by(Photo.id)).all()
    processed = faces = failed = 0
    for photo in photos:
        try:
            source = session.get(PhotoSource, photo.source_id)
            if source and source.source_type == "google_drive":
                faces += index_google_photo(session, photo, engine)
            else:
                faces += index_local_photo(session, photo, engine)
            processed += 1
        except Exception:
            session.rollback()
            failed += 1
    return {"processed": processed, "faces": faces, "failed": failed}


def index_pending_local_photos(session: Session, project_id: int, engine: OpenCVFaceEngine, source_ids: tuple[int, ...] = ()) -> dict[str, int]:
    return index_pending_photos(session, project_id, engine, source_ids)
