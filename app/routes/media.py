from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from pillow_heif import register_heif_opener
from PIL import Image, ImageOps
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Face, Photo, PhotoSource
from app.services.face_indexer import google_photo_bytes, local_photo_path

register_heif_opener()
router = APIRouter(prefix="/media", tags=["media"])


def _resolve_photo(photo_id: int, session: Session):
    photo = session.get(Photo, photo_id)
    if not photo:
        raise HTTPException(404, "Photo not found")
    source = session.get(PhotoSource, photo.source_id)
    if not source or source.project_id != photo.project_id:
        raise HTTPException(404, "Photo source not found")
    return photo, source


def _drive_bytes(session: Session, source: PhotoSource, photo: Photo) -> bytes:
    try:
        return google_photo_bytes(session, source, photo)
    except Exception as exc:
        raise HTTPException(502, f"Unable to retrieve Google Drive photo: {photo.name}") from exc


def _photo_image(session: Session, photo: Photo, source: PhotoSource) -> Image.Image:
    try:
        if source.source_type == "local_folder":
            data = local_photo_path(source, photo).read_bytes()
        elif source.source_type == "google_drive":
            data = _drive_bytes(session, source, photo)
        else:
            raise HTTPException(400, "Unsupported storage provider")
        with Image.open(BytesIO(data)) as image:
            return ImageOps.exif_transpose(image).convert("RGB")
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(415, "Image could not be rendered") from exc


@router.get("/faces/{face_id}")
def preview_face(face_id: int, session: Session = Depends(get_session)):
    face = session.get(Face, face_id)
    if not face:
        raise HTTPException(404, "Face not found")
    photo, source = _resolve_photo(face.photo_id, session)
    image = _photo_image(session, photo, source)
    pad_x = max(12, int(face.bbox_w * 0.35))
    pad_y = max(12, int(face.bbox_h * 0.35))
    left = max(0, face.bbox_x - pad_x)
    top = max(0, face.bbox_y - pad_y)
    right = min(image.width, face.bbox_x + face.bbox_w + pad_x)
    bottom = min(image.height, face.bbox_y + face.bbox_h + pad_y)
    if right <= left or bottom <= top:
        raise HTTPException(422, "Stored face crop is invalid")
    crop = image.crop((left, top, right, bottom))
    crop.thumbnail((480, 480))
    output = BytesIO()
    crop.save(output, format="JPEG", quality=86, optimize=True)
    return Response(output.getvalue(), media_type="image/jpeg", headers={"Cache-Control": "private, max-age=900"})


@router.get("/photos/{photo_id}")
def preview_photo(photo_id: int, session: Session = Depends(get_session)):
    photo, source = _resolve_photo(photo_id, session)
    if source.source_type == "local_folder":
        try:
            return FileResponse(local_photo_path(source, photo), media_type=photo.mime_type or None, filename=None)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    if source.source_type == "google_drive":
        data = _drive_bytes(session, source, photo)
        try:
            with Image.open(BytesIO(data)) as image:
                corrected = ImageOps.exif_transpose(image).convert("RGB")
                corrected.thumbnail((1600, 1600))
                output = BytesIO()
                corrected.save(output, format="JPEG", quality=88, optimize=True)
            return Response(output.getvalue(), media_type="image/jpeg", headers={"Cache-Control": "private, max-age=300"})
        except Exception as exc:
            raise HTTPException(415, "Google Drive image could not be rendered") from exc
    raise HTTPException(400, "Unsupported storage provider")


@router.get("/photos/{photo_id}/download")
def download_photo(photo_id: int, session: Session = Depends(get_session)):
    photo, source = _resolve_photo(photo_id, session)
    if source.source_type == "local_folder":
        try:
            return FileResponse(local_photo_path(source, photo), media_type=photo.mime_type or "application/octet-stream", filename=photo.name)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    if source.source_type == "google_drive":
        return Response(_drive_bytes(session, source, photo), media_type=photo.mime_type or "application/octet-stream", headers={"Content-Disposition": f'attachment; filename="{photo.name.replace(chr(34), "")}"'})
    raise HTTPException(400, "Unsupported storage provider")
