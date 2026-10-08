from html import escape
from io import BytesIO
from pathlib import Path

import cv2 as cv
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from pillow_heif import register_heif_opener
from PIL import Image, ImageOps
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_user
from app.database import get_session
from app.models import Photo, PhotoSource, Project, User
from app.services.face_engine import OpenCVFaceEngine
from app.services.face_matching import SEARCH_THRESHOLDS, find_similar_faces
from app.services.index_jobs import cancel_index_job, get_index_job, start_index_job
from app.settings import get_app_settings
from app.ui import page

register_heif_opener()
router = APIRouter(prefix="/projects", tags=["faces"])
MODELS = Path("models")
DETECTOR = MODELS / "face_detection_yunet_2023mar.onnx"
RECOGNIZER = MODELS / "face_recognition_sface_2021dec.onnx"
MAX_REFERENCE_BYTES = 20 * 1024 * 1024
MAX_REFERENCE_PIXELS = 40_000_000


def _engine() -> OpenCVFaceEngine:
    try: return OpenCVFaceEngine(DETECTOR, RECOGNIZER)
    except FileNotFoundError as exc: raise HTTPException(503, str(exc)) from exc


def _decode_reference(data: bytes) -> np.ndarray:
    try:
        with Image.open(BytesIO(data)) as image:
            if image.width <= 0 or image.height <= 0 or image.width * image.height > MAX_REFERENCE_PIXELS:
                raise HTTPException(413, "Reference image dimensions are too large")
            corrected = ImageOps.exif_transpose(image); rgb = np.asarray(corrected.convert("RGB"))
        return cv.cvtColor(rgb, cv.COLOR_RGB2BGR)
    except HTTPException:
        raise
    except Exception as exc: raise HTTPException(400, "Reference image could not be read") from exc


def _validated_sources(session: Session, project_id: int, source_ids: list[int] | None) -> tuple[int, ...]:
    if not session.get(Project, project_id): raise HTTPException(404, "Project not found")
    allowed = set(session.scalars(select(PhotoSource.id).where(PhotoSource.project_id == project_id, PhotoSource.active.is_(True))).all())
    selected = tuple(dict.fromkeys(source_ids or []))
    if set(selected) - allowed: raise HTTPException(400, "Selected source is unavailable or does not belong to this project")
    return selected


@router.post("/{project_id}/faces/index")
def index_faces(project_id: int, source_ids: list[int] | None = Form(None), session: Session = Depends(get_session), _: User = Depends(require_user)):
    return JSONResponse(start_index_job(project_id, _validated_sources(session, project_id, source_ids), DETECTOR, RECOGNIZER), status_code=202)


@router.get("/{project_id}/faces/index/status")
def index_faces_status(project_id: int, session: Session = Depends(get_session), _: User = Depends(require_user)):
    if not session.get(Project, project_id): raise HTTPException(404, "Project not found")
    return get_index_job(project_id) or {"project_id": project_id, "status": "idle", "running": False, "percent": 0.0}


@router.post("/{project_id}/faces/index/cancel")
def index_faces_cancel(project_id: int, session: Session = Depends(get_session), _: User = Depends(require_user)):
    if not session.get(Project, project_id): raise HTTPException(404, "Project not found")
    return {"cancel_requested": cancel_index_job(project_id)}


@router.post("/{project_id}/faces/search", response_class=HTMLResponse)
async def search_faces(project_id: int, reference: UploadFile | None = File(None), selfie_reference: UploadFile | None = File(None), mode: str = Form(""), source_ids: list[int] | None = Form(None), session: Session = Depends(get_session), user: User = Depends(require_user)):
    project = session.get(Project, project_id)
    if not project: raise HTTPException(404, "Project not found")
    if not mode:
        mode = get_app_settings(session).default_search_mode
    if mode not in SEARCH_THRESHOLDS:
        raise HTTPException(400, "Invalid search mode")
    selected = _validated_sources(session, project_id, source_ids)
    upload = selfie_reference or reference
    if upload is None:
        raise HTTPException(400, "Take a selfie or choose a reference photo first")
    try:
        data = await upload.read(MAX_REFERENCE_BYTES + 1)
    finally:
        await upload.close()
        other = reference if upload is selfie_reference else selfie_reference
        if other is not None:
            await other.close()
    if not data: raise HTTPException(400, "Reference image is empty")
    if len(data) > MAX_REFERENCE_BYTES: raise HTTPException(413, "Reference image is too large")
    detected = _engine().detect_and_embed(_decode_reference(data))
    if not detected: raise HTTPException(400, "No face was detected. Try a clear, front-facing selfie with good lighting.")
    reference_face = max(detected, key=lambda item: item.bbox[2] * item.bbox[3])
    matches = find_similar_faces(session, project_id, reference_face.embedding, selected, mode)
    cards, seen_photos = [], set()
    for face, score in matches:
        if face.photo_id in seen_photos: continue
        seen_photos.add(face.photo_id); photo = session.get(Photo, face.photo_id); source = session.get(PhotoSource, face.source_id)
        if photo and source:
            preview = f'<img src="/media/photos/{photo.id}" alt="{escape(photo.name)}" loading="lazy" style="width:100%;height:260px;object-fit:cover;border-radius:12px">'
            actions = f'<p><a class="button" href="/media/photos/{photo.id}" target="_blank">View Photo</a> <a class="button secondary" href="/media/photos/{photo.id}/download">Download Original</a></p>'
            cards.append(f'<div class="card">{preview}<h3>{escape(photo.name)}</h3><div class="pill">Similarity {score:.3f}</div><p class="muted">Source: {escape(source.display_name or source.source_type)}</p>{actions}</div>')
    results_html = "".join(cards) or '<div class="card">No matches found. Try Balanced or Broad mode, or another reference photo.</div>'
    body = f'<div class="row" style="justify-content:space-between"><div><h1>Search Results</h1><p class="muted">{len(cards)} matching photographs · {escape(mode.title())} mode. Similarity is a ranking signal, not an identity probability.</p></div><a class="button secondary" href="/ui/projects/{project_id}">Back to Project</a></div><div class="grid">{results_html}</div>'
    return page(f"{project.name} Search", body, user=user)