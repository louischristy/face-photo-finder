from html import escape
import math

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Face, Photo, PhotoSource, Project
from app.services.face_indexer import embedding_from_bytes
from app.services.face_matching import SEARCH_THRESHOLDS, find_similar_faces
from app.ui import page

router = APIRouter(prefix="/projects", tags=["gallery"])
PAGE_SIZE = 48
DEDUP_THRESHOLDS = {"conservative": 0.66, "normal": 0.58, "aggressive": 0.52}
EMPTY_GALLERY = '<div class="card">No detected faces in this scope.</div>'
EMPTY_MATCHES = '<div class="card">No similar photos met this search threshold.</div>'


def _project_sources(session: Session, project_id: int):
    return session.scalars(select(PhotoSource).where(PhotoSource.project_id == project_id).order_by(PhotoSource.id)).all()


def _validate_source(sources, source_id: int | None):
    if source_id is not None and source_id not in {source.id for source in sources}:
        raise HTTPException(400, "Selected source does not belong to this project")


def _source_options(sources, source_id: int | None):
    options = ['<option value="">All indexed sources</option>']
    for source in sources:
        selected = " selected" if source.id == source_id else ""
        options.append(f'<option value="{source.id}"{selected}>{escape(source.display_name or source.source_type)}</option>')
    return "".join(options)


def _dedup_options(selected_mode: str):
    labels = {"conservative": "Conservative", "normal": "Normal", "aggressive": "Aggressive"}
    options = []
    for name, threshold in DEDUP_THRESHOLDS.items():
        selected = " selected" if name == selected_mode else ""
        options.append(f'<option value="{name}"{selected}>{labels[name]} ({threshold:.2f})</option>')
    return "".join(options)


def _face_quality(face: Face) -> float:
    confidence = max(0.0, min(float(face.detector_score or 0.0), 1.0))
    area = max(0, int(face.bbox_w or 0)) * max(0, int(face.bbox_h or 0))
    size_score = min(math.sqrt(area) / 400.0, 1.0) if area else 0.0
    return (confidence * 0.72) + (size_score * 0.28)


def _normalized_embedding(face: Face) -> np.ndarray:
    vector = embedding_from_bytes(face.embedding, face.embedding_dim).astype(np.float32, copy=True).flatten()
    norm = float(np.linalg.norm(vector))
    if norm:
        vector /= norm
    return vector


def _representative_faces(faces: list[Face], threshold: float) -> tuple[list[Face], int]:
    representatives: list[Face] = []
    representative_vectors: list[np.ndarray] = []
    suppressed = 0
    for face in faces:
        vector = _normalized_embedding(face)
        duplicate = any(
            candidate.shape == vector.shape and float(np.dot(vector, candidate)) >= threshold
            for candidate in representative_vectors
        )
        if duplicate:
            suppressed += 1
            continue
        representatives.append(face)
        representative_vectors.append(vector)
    return representatives, suppressed


@router.get("/{project_id}/faces/gallery", response_class=HTMLResponse)
def face_gallery(project_id: int, source_id: int | None = Query(None), dedup: str = Query("normal"), page_number: int = Query(1, alias="page", ge=1), session: Session = Depends(get_session)):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    sources = _project_sources(session, project_id)
    _validate_source(sources, source_id)
    if dedup not in DEDUP_THRESHOLDS:
        raise HTTPException(400, "Deduplication mode must be conservative, normal, or aggressive")
    threshold = DEDUP_THRESHOLDS[dedup]
    conditions = [Face.project_id == project_id]
    if source_id is not None:
        conditions.append(Face.source_id == source_id)

    all_faces = session.scalars(select(Face).where(*conditions)).all()
    all_faces.sort(key=lambda face: (_face_quality(face), face.detector_score or 0.0, face.id), reverse=True)
    representatives, suppressed = _representative_faces(all_faces, threshold)
    total = len(all_faces)
    representative_total = len(representatives)
    pages = max(1, math.ceil(representative_total / PAGE_SIZE))
    page_number = min(page_number, pages)
    start = (page_number - 1) * PAGE_SIZE
    faces = representatives[start:start + PAGE_SIZE]

    cards = []
    for face in faces:
        photo = session.get(Photo, face.photo_id)
        source = session.get(PhotoSource, face.source_id)
        if not photo or not source:
            continue
        source_arg = f"&source_id={source_id}" if source_id is not None else ""
        quality = _face_quality(face)
        cards.append(
            f'<div class="card"><a href="/projects/{project_id}/faces/{face.id}/matches?mode=recommended{source_arg}" title="Find similar photos">'
            f'<img src="/media/faces/{face.id}" alt="Representative detected face" loading="lazy" style="width:100%;height:230px;object-fit:cover;border-radius:12px"></a>'
            f'<h3>{escape(photo.name)}</h3><p class="muted">Source: {escape(source.display_name or source.source_type)} · Quality: {quality:.2f}</p>'
            f'<p><a class="button" href="/projects/{project_id}/faces/{face.id}/matches?mode=recommended{source_arg}">Find Similar Photos</a></p>'
            f'<p><a class="button secondary" href="/media/photos/{photo.id}" target="_blank">View Photo</a> <a class="button secondary" href="/media/photos/{photo.id}/download">Download Original</a></p></div>'
        )

    def page_link(number, label):
        source_arg = f"&source_id={source_id}" if source_id is not None else ""
        return f'<a class="button secondary" href="/projects/{project_id}/faces/gallery?page={number}&dedup={dedup}{source_arg}">{label}</a>'

    nav = '<div class="row" style="justify-content:space-between;align-items:center">'
    nav += page_link(page_number - 1, "Previous") if page_number > 1 else '<span></span>'
    nav += f'<span class="muted">Page {page_number} of {pages} · Clearest representative crops first</span>'
    nav += page_link(page_number + 1, "Next") if page_number < pages else '<span></span>'
    nav += '</div>'
    cards_html = "".join(cards) or EMPTY_GALLERY
    options_html = _source_options(sources, source_id)
    dedup_html = _dedup_options(dedup)
    suppression_rate = (suppressed / total * 100.0) if total else 0.0
    body = (
        f'<div class="row" style="justify-content:space-between"><div><h1>Representative Faces Gallery</h1><p class="muted">{total} indexed face region(s) · {representative_total} temporary representative(s) · {suppressed} similar crop(s) suppressed ({suppression_rate:.1f}%). Dedup mode: {dedup.title()} · threshold {threshold:.2f}.</p></div><a class="button secondary" href="/ui/projects/{project_id}">Back to Project</a></div>'
        f'<div class="card"><form class="row" method="get" action="/projects/{project_id}/faces/gallery"><select name="source_id">{options_html}</select><select name="dedup">{dedup_html}</select><button type="submit">Apply Gallery Filter</button></form><p class="muted">Conservative keeps more representatives. Aggressive suppresses more visually similar crops. This changes display only; the indexed faces are untouched.</p></div>'
        f'{nav}<div class="grid">{cards_html}</div>{nav}'
    )
    return page(f"{project.name} Faces", body)


@router.get("/{project_id}/faces/{face_id}/matches", response_class=HTMLResponse)
def face_matches(project_id: int, face_id: int, source_id: int | None = Query(None), mode: str = Query("recommended"), session: Session = Depends(get_session)):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    reference_face = session.get(Face, face_id)
    if not reference_face or reference_face.project_id != project_id:
        raise HTTPException(404, "Face not found")
    sources = _project_sources(session, project_id)
    _validate_source(sources, source_id)
    if mode not in SEARCH_THRESHOLDS:
        raise HTTPException(400, "Search mode must be strict, recommended, balanced, or broad")
    reference = embedding_from_bytes(reference_face.embedding, reference_face.embedding_dim)
    scope = (source_id,) if source_id is not None else ()
    matches = find_similar_faces(session, project_id, reference, scope, mode)
    best_by_photo = {}
    for face, score in matches:
        current = best_by_photo.get(face.photo_id)
        candidate_rank = (score, _face_quality(face))
        current_rank = (current[1], _face_quality(current[0])) if current else None
        if current_rank is None or candidate_rank > current_rank:
            best_by_photo[face.photo_id] = (face, score)
    ordered = sorted(best_by_photo.values(), key=lambda item: (item[1], _face_quality(item[0])), reverse=True)
    cards = []
    for rank, (face, score) in enumerate(ordered, start=1):
        photo = session.get(Photo, face.photo_id)
        source = session.get(PhotoSource, face.source_id)
        if not photo or not source:
            continue
        quality = _face_quality(face)
        margin = score - SEARCH_THRESHOLDS[mode]
        cards.append(
            f'<div class="card">'
            f'<div class="row" style="align-items:flex-start"><img src="/media/faces/{face.id}" alt="Matched face crop" loading="lazy" style="width:110px;height:110px;object-fit:cover;border-radius:12px">'
            f'<div><strong>Result #{rank}</strong><p class="muted">Similarity: {score:.3f}<br>Threshold: {SEARCH_THRESHOLDS[mode]:.2f}<br>Margin: +{margin:.3f}<br>Crop quality: {quality:.2f}</p></div></div>'
            f'<img src="/media/photos/{photo.id}" alt="{escape(photo.name)}" loading="lazy" style="width:100%;height:260px;object-fit:cover;border-radius:12px;margin-top:10px">'
            f'<h3>{escape(photo.name)}</h3><p class="muted">Source: {escape(source.display_name or source.source_type)}</p>'
            f'<p><a class="button" href="/media/photos/{photo.id}" target="_blank">View Photo</a> <a class="button secondary" href="/media/photos/{photo.id}/download">Download Original</a></p></div>'
        )
    source_arg = f"&source_id={source_id}" if source_id is not None else ""
    links = []
    for name in ("strict", "recommended", "balanced", "broad"):
        css_class = "button" if name == mode else "button secondary"
        links.append(f'<a class="{css_class}" href="/projects/{project_id}/faces/{face_id}/matches?mode={name}{source_arg}">{name.title()} ({SEARCH_THRESHOLDS[name]:.2f})</a>')
    mode_links = " ".join(links)
    back_arg = f"?source_id={source_id}" if source_id is not None else ""
    cards_html = "".join(cards) or EMPTY_MATCHES
    if ordered:
        scores = [score for _, score in ordered]
        score_summary = f'Highest {max(scores):.3f} · Lowest {min(scores):.3f} · Active threshold {SEARCH_THRESHOLDS[mode]:.2f}'
    else:
        score_summary = f'No results at active threshold {SEARCH_THRESHOLDS[mode]:.2f}'
    body = (
        f'<div class="row" style="justify-content:space-between"><div><h1>Similar Photo Search</h1><p class="muted">Using the selected detected face as a temporary reference. Similarity is a ranking signal, not an identity probability.</p></div><a class="button secondary" href="/projects/{project_id}/faces/gallery{back_arg}">Back to Faces</a></div>'
        f'<div class="card"><div class="row"><img src="/media/faces/{face_id}" alt="Selected face" style="width:120px;height:120px;object-fit:cover;border-radius:12px"><div><h3>Selected reference face</h3><p>{len(ordered)} photo result(s)<br><span class="muted">{score_summary}</span></p><div class="row">{mode_links}</div></div></div></div>'
        f'<div class="grid">{cards_html}</div>'
    )
    return page(f"{project.name} Similar Photos", body)
