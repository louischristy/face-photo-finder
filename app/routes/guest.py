from __future__ import annotations

import hmac
import os
import secrets
import tempfile
import threading
import time
import zipfile
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pillow_heif import register_heif_opener
from PIL import Image, ImageOps
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.database import SessionLocal, get_session
from app.models import Photo, PhotoSource, Project
from app.routes.faces import MAX_REFERENCE_BYTES, _decode_reference, _engine
from app.routes.media import BULK_TEMP_ROOT, CACHE_ROOT, _original_bytes, _remove_temp_file, _safe_zip_name, _write_cache
from app.services.face_matching import find_similar_faces

register_heif_opener()
router = APIRouter(prefix="/guest", tags=["guest-event"])
_SEARCHES: dict[str, tuple[float, int, tuple[int, ...]]] = {}
_ZIP_JOBS: dict[str, dict] = {}
_ZIP_LOCK = threading.Lock()
SEARCH_TTL = 30 * 60
ZIP_JOB_TTL = 60 * 60
MAX_MATCHES = 500
SOURCE_READ_ATTEMPTS = 3
SOURCE_RETRY_DELAYS = (0.35, 0.9)


def _authorize(x_guest_key: str | None = Header(None)) -> None:
    expected = os.getenv("AUROARA_GUEST_KEY", "")
    if not expected or not x_guest_key or not hmac.compare_digest(expected, x_guest_key):
        raise HTTPException(404, "Not found")


def _event_scope(session: Session) -> tuple[int, tuple[int, ...]]:
    raw = os.getenv("AUROARA_GUEST_PROJECT_ID", "").strip()
    if not raw.isdigit():
        raise HTTPException(503, "Guest event is not configured")
    project_id = int(raw)
    if not session.get(Project, project_id):
        raise HTTPException(503, "Guest event project is unavailable")
    configured = [part.strip() for part in os.getenv("AUROARA_GUEST_SOURCE_IDS", "").split(",") if part.strip()]
    active = tuple(session.scalars(select(PhotoSource.id).where(PhotoSource.project_id == project_id, PhotoSource.active.is_(True))).all())
    if configured:
        if not all(item.isdigit() for item in configured):
            raise HTTPException(503, "Guest event sources are invalid")
        requested = tuple(dict.fromkeys(int(item) for item in configured))
        if set(requested) - set(active):
            raise HTTPException(503, "Guest event source is unavailable")
        return project_id, requested
    return project_id, active


def _cleanup_searches() -> None:
    cutoff = time.time() - SEARCH_TTL
    for key, value in list(_SEARCHES.items()):
        if value[0] < cutoff:
            _SEARCHES.pop(key, None)


def _cleanup_zip_jobs() -> None:
    cutoff = time.time() - ZIP_JOB_TTL
    stale_paths = []
    with _ZIP_LOCK:
        for key, job in list(_ZIP_JOBS.items()):
            if job["created"] < cutoff:
                if job.get("path"):
                    stale_paths.append(job["path"])
                _ZIP_JOBS.pop(key, None)
    for path in stale_paths:
        _remove_temp_file(path)


def _search(search_id: str) -> tuple[int, tuple[int, ...]]:
    _cleanup_searches()
    item = _SEARCHES.get(search_id)
    if not item:
        raise HTTPException(404, "Search expired. Please search again.")
    return item[1], item[2]


def _photo_token(search_id: str, index: int) -> str:
    return f"{search_id}.{index}"


def _photo_from_token(token: str) -> tuple[int, int]:
    search_id, separator, raw_index = token.rpartition(".")
    if not separator or not raw_index.isdigit():
        raise HTTPException(404, "Photo not found")
    project_id, photo_ids = _search(search_id)
    index = int(raw_index)
    if index < 0 or index >= len(photo_ids):
        raise HTTPException(404, "Photo not found")
    return project_id, photo_ids[index]


def _original_bytes_with_retry(session: Session, photo: Photo, source: PhotoSource) -> bytes:
    if source.source_type != "google_drive":
        return _original_bytes(session, photo, source)
    last_error: HTTPException | None = None
    for attempt in range(SOURCE_READ_ATTEMPTS):
        try:
            return _original_bytes(session, photo, source)
        except HTTPException as exc:
            last_error = exc
            if exc.status_code != 502 or attempt >= SOURCE_READ_ATTEMPTS - 1:
                raise
            time.sleep(SOURCE_RETRY_DELAYS[attempt])
    if last_error:
        raise last_error
    raise HTTPException(502, "Unable to retrieve photo")


def _guest_preview_cache(photo_id: int) -> Path:
    return CACHE_ROOT / "guest-photos" / f"{photo_id}.jpg"


def _build_zip_job(job_id: str, project_id: int, source_ids: tuple[int, ...], photo_ids: tuple[int, ...]) -> None:
    BULK_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="guest-matches-", suffix=".zip", dir=str(BULK_TEMP_ROOT))
    os.close(fd)
    used, failures = set(), []
    try:
        with SessionLocal() as session:
            with zipfile.ZipFile(temp_name, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as bundle:
                for index, photo_id in enumerate(photo_ids, start=1):
                    photo = session.get(Photo, photo_id)
                    if photo and photo.project_id == project_id and photo.source_id in source_ids:
                        source = session.get(PhotoSource, photo.source_id)
                        if source:
                            try:
                                bundle.writestr(_safe_zip_name(photo.name, photo.id, used), _original_bytes_with_retry(session, photo, source))
                            except Exception as exc:
                                failures.append(f"{photo.name}: {exc}")
                    with _ZIP_LOCK:
                        job = _ZIP_JOBS.get(job_id)
                        if job:
                            job["completed"] = index
                            job["failures"] = len(failures)
                if failures:
                    bundle.writestr("download-errors.txt", "Some originals could not be retrieved:\n\n" + "\n".join(failures))
        with _ZIP_LOCK:
            job = _ZIP_JOBS.get(job_id)
            if job:
                job.update(status="ready", path=temp_name, failures=len(failures))
    except Exception as exc:
        _remove_temp_file(temp_name)
        with _ZIP_LOCK:
            job = _ZIP_JOBS.get(job_id)
            if job:
                job.update(status="failed", error=str(exc) or "ZIP preparation failed")


@router.post("/search", dependencies=[Depends(_authorize)])
async def guest_search(reference: UploadFile = File(...), session: Session = Depends(get_session)):
    try:
        data = await reference.read(MAX_REFERENCE_BYTES + 1)
    finally:
        await reference.close()
    if not data:
        raise HTTPException(400, "Reference image is empty")
    if len(data) > MAX_REFERENCE_BYTES:
        raise HTTPException(413, "Reference image is too large")
    detected = _engine().detect_and_embed(_decode_reference(data))
    if not detected:
        raise HTTPException(400, "No face was detected. Try a clear, front-facing selfie with good lighting.")
    project_id, source_ids = _event_scope(session)
    if not source_ids:
        raise HTTPException(503, "No event photo sources are active")
    face = max(detected, key=lambda item: item.bbox[2] * item.bbox[3])
    matches = find_similar_faces(session, project_id, face.embedding, source_ids, "recommended")
    photo_ids, seen = [], set()
    for match, _score in matches:
        if match.photo_id not in seen:
            seen.add(match.photo_id)
            photo_ids.append(match.photo_id)
            if len(photo_ids) >= MAX_MATCHES:
                break
    search_id = secrets.token_urlsafe(24)
    _cleanup_searches()
    _SEARCHES[search_id] = (time.time(), project_id, tuple(photo_ids))
    return {"search_id": search_id, "matches": [{"photo_id": _photo_token(search_id, index)} for index, _item in enumerate(photo_ids)]}


@router.get("/photos/{photo_token}", dependencies=[Depends(_authorize)])
def guest_preview(photo_token: str, session: Session = Depends(get_session)):
    project_id, photo_id = _photo_from_token(photo_token)
    configured_project, source_ids = _event_scope(session)
    if project_id != configured_project:
        raise HTTPException(404, "Photo not found")
    photo = session.get(Photo, photo_id)
    if not photo or photo.project_id != project_id or photo.source_id not in source_ids:
        raise HTTPException(404, "Photo not found")
    source = session.get(PhotoSource, photo.source_id)
    if not source:
        raise HTTPException(404, "Photo source not found")
    cache_path = _guest_preview_cache(photo_id)
    if cache_path.is_file():
        return FileResponse(cache_path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})
    try:
        with Image.open(BytesIO(_original_bytes_with_retry(session, photo, source))) as image:
            corrected = ImageOps.exif_transpose(image).convert("RGB")
            corrected.thumbnail((1400, 1400))
            output = BytesIO()
            corrected.save(output, format="JPEG", quality=86, optimize=True)
        preview = output.getvalue()
        _write_cache(cache_path, preview)
        return Response(preview, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(415, "Image could not be rendered") from exc


@router.get("/photos/{photo_token}/download", dependencies=[Depends(_authorize)])
def guest_download(photo_token: str, session: Session = Depends(get_session)):
    project_id, photo_id = _photo_from_token(photo_token)
    configured_project, source_ids = _event_scope(session)
    if project_id != configured_project:
        raise HTTPException(404, "Photo not found")
    photo = session.get(Photo, photo_id)
    if not photo or photo.project_id != project_id or photo.source_id not in source_ids:
        raise HTTPException(404, "Photo not found")
    source = session.get(PhotoSource, photo.source_id)
    if not source:
        raise HTTPException(404, "Photo source not found")
    safe_name = Path(photo.name).name.replace(chr(34), "")
    return Response(_original_bytes_with_retry(session, photo, source), media_type=photo.mime_type or "application/octet-stream", headers={"Content-Disposition": f'attachment; filename="{safe_name}"', "Cache-Control": "no-store"})


@router.post("/search/{search_id}/download-jobs", dependencies=[Depends(_authorize)])
def guest_start_download_job(search_id: str, session: Session = Depends(get_session)):
    project_id, photo_ids = _search(search_id)
    configured_project, source_ids = _event_scope(session)
    if project_id != configured_project or not photo_ids:
        raise HTTPException(404, "No matched photos to download")
    _cleanup_zip_jobs()
    job_id = secrets.token_urlsafe(24)
    with _ZIP_LOCK:
        _ZIP_JOBS[job_id] = {"created": time.time(), "status": "preparing", "completed": 0, "total": len(photo_ids), "failures": 0, "path": None, "error": None}
    threading.Thread(target=_build_zip_job, args=(job_id, project_id, source_ids, photo_ids), daemon=True).start()
    return {"job_id": job_id, "status": "preparing", "completed": 0, "total": len(photo_ids), "failures": 0}


@router.get("/download-jobs/{job_id}", dependencies=[Depends(_authorize)])
def guest_download_job_status(job_id: str):
    _cleanup_zip_jobs()
    with _ZIP_LOCK:
        job = _ZIP_JOBS.get(job_id)
        if not job:
            raise HTTPException(404, "Download preparation expired")
        return {key: job.get(key) for key in ("status", "completed", "total", "failures", "error")}


@router.get("/download-jobs/{job_id}/file", dependencies=[Depends(_authorize)])
def guest_download_job_file(job_id: str):
    _cleanup_zip_jobs()
    with _ZIP_LOCK:
        job = _ZIP_JOBS.get(job_id)
        if not job:
            raise HTTPException(404, "Download preparation expired")
        if job["status"] != "ready" or not job.get("path"):
            raise HTTPException(409, "Download is not ready")
        path = job["path"]
    if not Path(path).is_file():
        raise HTTPException(404, "Prepared download is unavailable")
    return FileResponse(path, media_type="application/zip", filename="my-event-photos.zip", headers={"Cache-Control": "no-store"})
