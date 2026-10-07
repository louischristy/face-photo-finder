from pathlib import Path
import tempfile

import cv2 as cv
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Photo, PhotoSource, Project
from app.services.face_engine import OpenCVFaceEngine
from app.services.face_indexer import index_pending_local_photos
from app.services.face_matching import find_similar_faces
from app.ui import page

router = APIRouter(prefix="/projects", tags=["faces"])
MODELS = Path("models")
DETECTOR = MODELS / "face_detection_yunet_2023mar.onnx"
RECOGNIZER = MODELS / "face_recognition_sface_2021dec.onnx"


def _engine() -> OpenCVFaceEngine:
    try:
        return OpenCVFaceEngine(DETECTOR, RECOGNIZER)
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post("/{project_id}/faces/index")
def index_faces(project_id: int, source_ids: list[int] | None = Form(None), session: Session = Depends(get_session)):
    if not session.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    allowed = set(session.scalars(select(PhotoSource.id).where(PhotoSource.project_id == project_id)).all())
    selected = tuple(dict.fromkeys(source_ids or []))
    if set(selected) - allowed:
        raise HTTPException(400, "Selected source does not belong to this project")
    result = index_pending_local_photos(session, project_id, _engine(), selected)
    return RedirectResponse(f"/ui/projects/{project_id}?indexed={result['processed']}&faces={result['faces']}&failed={result['failed']}", status_code=303)


@router.post("/{project_id}/faces/search", response_class=HTMLResponse)
async def search_faces(project_id: int, reference: UploadFile = File(...), mode: str = Form("balanced"), source_ids: list[int] | None = Form(None), session: Session = Depends(get_session)):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    allowed = set(session.scalars(select(PhotoSource.id).where(PhotoSource.project_id == project_id)).all())
    selected = tuple(dict.fromkeys(source_ids or []))
    if set(selected) - allowed:
        raise HTTPException(400, "Selected source does not belong to this project")
    suffix = Path(reference.filename or "reference.jpg").suffix or ".jpg"
    data = await reference.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, "Reference image is too large")
    with tempfile.NamedTemporaryFile(suffix=suffix) as temp:
        temp.write(data); temp.flush()
        image = cv.imread(temp.name)
        if image is None:
            raise HTTPException(400, "Reference image could not be read")
        detected = _engine().detect_and_embed(image)
    if not detected:
        raise HTTPException(400, "No face was detected in the reference image")
    reference_face = max(detected, key=lambda item: item.bbox[2] * item.bbox[3])
    matches = find_similar_faces(session, project_id, reference_face.embedding, selected, mode)
    cards = []
    seen_photos = set()
    for face, score in matches:
        if face.photo_id in seen_photos:
            continue
        seen_photos.add(face.photo_id)
        photo = session.get(Photo, face.photo_id)
        source = session.get(PhotoSource, face.source_id)
        if photo and source:
            cards.append(f'<div class="card"><h3>{photo.name}</h3><div class="pill">Similarity {score:.3f}</div><p class="muted">Source: {source.display_name or source.source_type}</p></div>')
    body = f'<div class="row" style="justify-content:space-between"><div><h1>Search Results</h1><p class="muted">{len(cards)} matching photographs · {mode.title()} mode. Similarity is not an identity probability.</p></div><a class="button secondary" href="/ui/projects/{project_id}">Back to Project</a></div><div class="grid">{"".join(cards) or "<div class=\"card\">No matches found. Try Balanced or Broad mode, or another reference photo.</div>"}</div>'
    return page(f"{project.name} Search", body)
