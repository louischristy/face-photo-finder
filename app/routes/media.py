from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Photo, PhotoSource
from app.services.face_indexer import local_photo_path

router = APIRouter(prefix="/media", tags=["media"])


def _resolve_photo(photo_id: int, session: Session):
    photo = session.get(Photo, photo_id)
    if not photo:
        raise HTTPException(404, "Photo not found")
    source = session.get(PhotoSource, photo.source_id)
    if not source or source.project_id != photo.project_id:
        raise HTTPException(404, "Photo source not found")
    if source.source_type != "local_folder":
        raise HTTPException(400, "Preview for this storage provider is not available yet")
    try:
        return photo, local_photo_path(source, photo)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/photos/{photo_id}")
def preview_photo(photo_id: int, session: Session = Depends(get_session)):
    photo, path = _resolve_photo(photo_id, session)
    return FileResponse(path, media_type=photo.mime_type or None, filename=None)


@router.get("/photos/{photo_id}/download")
def download_photo(photo_id: int, session: Session = Depends(get_session)):
    photo, path = _resolve_photo(photo_id, session)
    return FileResponse(path, media_type=photo.mime_type or "application/octet-stream", filename=photo.name)
