from html import escape
import math

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Face, Photo, PhotoSource, Project
from app.services.face_indexer import embedding_from_bytes
from app.services.face_matching import find_similar_faces
from app.ui import page

router = APIRouter(prefix="/projects", tags=["gallery"])
PAGE_SIZE = 48
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


@router.get("/{project_id}/faces/gallery", response_class=HTMLResponse)
def face_gallery(project_id: int, source_id: int | None = Query(None), page_number: int = Query(1, alias="page", ge=1), session: Session = Depends(get_session)):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    sources = _project_sources(session, project_id)
    _validate_source(sources, source_id)
    conditions = [Face.project_id == project_id]
    if source_id is not None:
        conditions.append(Face.source_id == source_id)
    total = session.scalar(select(func.count(Face.id)).where(*conditions)) or 0
    pages = max(1, math.ceil(total / PAGE_SIZE))
    page_number = min(page_number, pages)
    faces = session.scalars(select(Face).where(*conditions).order_by(Face.id).offset((page_number - 1) * PAGE_SIZE).limit(PAGE_SIZE)).all()
    cards = []
    for face in faces:
        photo = session.get(Photo, face.photo_id)
        source = session.get(PhotoSource, face.source_id)
        if not photo or not source:
            continue
        source_arg = f"&source_id={source_id}" if source_id is not None else ""
        cards.append(
            f'<div class="card"><a href="/projects/{project_id}/faces/{face.id}/matches?mode=strict{source_arg}" title="Find similar photos">'
            f'<img src="/media/faces/{face.id}" alt="Detected face" loading="lazy" style="width:100%;height:230px;object-fit:cover;border-radius:12px"></a>'
            f'<h3>{escape(photo.name)}</h3><p class="muted">Source: {escape(source.display_name or source.source_type)}</p>'
            f'<p><a class="button" href="/projects/{project_id}/faces/{face.id}/matches?mode=strict{source_arg}">Find Similar Photos</a></p>'
            f'<p><a class="button secondary" href="/media/photos/{photo.id}" target="_blank">View Photo</a> <a class="button secondary" href="/media/photos/{photo.id}/download">Download Original</a></p></div>'
        )
    def page_link(number, label):
        source_arg = f"&source_id={source_id}" if source_id is not None else ""
        return f'<a class="button secondary" href="/projects/{project_id}/faces/gallery?page={number}{source_arg}">{label}</a>'
    nav = '<div class="row" style="justify-content:space-between;align-items:center">'
    nav += page_link(page_number - 1, "Previous") if page_number > 1 else '<span></span>'
    nav += f'<span class="muted">Page {page_number} of {pages}</span>'
    nav += page_link(page_number + 1, "Next") if page_number < pages else '<span></span>'
    nav += '</div>'
    cards_html = "".join(cards) or EMPTY_GALLERY
    options_html = _source_options(sources, source_id)
    body = (
        f'<div class="row" style="justify-content:space-between"><div><h1>Detected Faces Gallery</h1><p class="muted">{total} detected face region(s). Click a face to use it as a temporary search reference.</p></div><a class="button secondary" href="/ui/projects/{project_id}">Back to Project</a></div>'
        f'<div class="card"><form class="row" method="get" action="/projects/{project_id}/faces/gallery"><select name="source_id">{options_html}</select><button type="submit">Filter Gallery</button></form></div>'
        f'{nav}<div class="grid">{cards_html}</div>{nav}'
    )
    return page(f"{project.name} Faces", body)


@router.get("/{project_id}/faces/{face_id}/matches", response_class=HTMLResponse)
def face_matches(project_id: int, face_id: int, source_id: int | None = Query(None), mode: str = Query("strict"), session: Session = Depends(get_session)):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    reference_face = session.get(Face, face_id)
    if not reference_face or reference_face.project_id != project_id:
        raise HTTPException(404, "Face not found")
    sources = _project_sources(session, project_id)
    _validate_source(sources, source_id)
    if mode not in {"strict", "balanced", "broad"}:
        raise HTTPException(400, "Search mode must be strict, balanced, or broad")
    reference = embedding_from_bytes(reference_face.embedding, reference_face.embedding_dim)
    scope = (source_id,) if source_id is not None else ()
    matches = find_similar_faces(session, project_id, reference, scope, mode)
    best_by_photo = {}
    for face, score in matches:
        current = best_by_photo.get(face.photo_id)
        if current is None or score > current[1]:
            best_by_photo[face.photo_id] = (face, score)
    ordered = sorted(best_by_photo.values(), key=lambda item: item[1], reverse=True)
    cards = []
    for face, score in ordered:
        photo = session.get(Photo, face.photo_id)
        source = session.get(PhotoSource, face.source_id)
        if not photo or not source:
            continue
        cards.append(
            f'<div class="card"><img src="/media/photos/{photo.id}" alt="{escape(photo.name)}" loading="lazy" style="width:100%;height:260px;object-fit:cover;border-radius:12px">'
            f'<h3>{escape(photo.name)}</h3><p class="muted">Similarity: {score:.3f} · Source: {escape(source.display_name or source.source_type)}</p>'
            f'<p><a class="button" href="/media/photos/{photo.id}" target="_blank">View Photo</a> <a class="button secondary" href="/media/photos/{photo.id}/download">Download Original</a></p></div>'
        )
    source_arg = f"&source_id={source_id}" if source_id is not None else ""
    links = []
    for name in ("strict", "balanced", "broad"):
        css_class = "button" if name == mode else "button secondary"
        links.append(f'<a class="{css_class}" href="/projects/{project_id}/faces/{face_id}/matches?mode={name}{source_arg}">{name.title()}</a>')
    mode_links = " ".join(links)
    back_arg = f"?source_id={source_id}" if source_id is not None else ""
    cards_html = "".join(cards) or EMPTY_MATCHES
    body = (
        f'<div class="row" style="justify-content:space-between"><div><h1>Similar Photo Search</h1><p class="muted">Using the selected detected face as a temporary reference. Similarity is a ranking signal, not an identity probability.</p></div><a class="button secondary" href="/projects/{project_id}/faces/gallery{back_arg}">Back to Faces</a></div>'
        f'<div class="card"><div class="row"><img src="/media/faces/{face_id}" alt="Selected face" style="width:120px;height:120px;object-fit:cover;border-radius:12px"><div><h3>Selected reference face</h3><p>{len(ordered)} photo result(s)</p><div class="row">{mode_links}</div></div></div></div>'
        f'<div class="grid">{cards_html}</div>'
    )
    return page(f"{project.name} Similar Photos", body)
