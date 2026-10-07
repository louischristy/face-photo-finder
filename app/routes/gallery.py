from html import escape
import math

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Face, Photo, PhotoSource, Project
from app.ui import page

router = APIRouter(prefix="/projects", tags=["gallery"])
PAGE_SIZE = 48


@router.get("/{project_id}/faces/gallery", response_class=HTMLResponse)
def face_gallery(
    project_id: int,
    source_id: int | None = Query(None),
    page_number: int = Query(1, alias="page", ge=1),
    session: Session = Depends(get_session),
):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    sources = session.scalars(
        select(PhotoSource).where(PhotoSource.project_id == project_id).order_by(PhotoSource.id)
    ).all()
    allowed = {source.id for source in sources}
    if source_id is not None and source_id not in allowed:
        raise HTTPException(400, "Selected source does not belong to this project")

    conditions = [Face.project_id == project_id]
    if source_id is not None:
        conditions.append(Face.source_id == source_id)

    total = session.scalar(select(func.count(Face.id)).where(*conditions)) or 0
    pages = max(1, math.ceil(total / PAGE_SIZE))
    page_number = min(page_number, pages)
    faces = session.scalars(
        select(Face)
        .where(*conditions)
        .order_by(Face.id)
        .offset((page_number - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    ).all()

    options = ['<option value="">All indexed sources</option>']
    for source in sources:
        selected = " selected" if source.id == source_id else ""
        options.append(f'<option value="{source.id}"{selected}>{escape(source.display_name or source.source_type)}</option>')

    cards = []
    for face in faces:
        photo = session.get(Photo, face.photo_id)
        source = session.get(PhotoSource, face.source_id)
        if not photo or not source:
            continue
        cards.append(
            f'<div class="card">'
            f'<img src="/media/faces/{face.id}" alt="Detected face" loading="lazy" '
            f'style="width:100%;height:230px;object-fit:cover;border-radius:12px">'
            f'<h3>{escape(photo.name)}</h3>'
            f'<p class="muted">Source: {escape(source.display_name or source.source_type)}</p>'
            f'<p><a class="button" href="/media/photos/{photo.id}" target="_blank">View Photo</a> '
            f'<a class="button secondary" href="/media/photos/{photo.id}/download">Download Original</a></p>'
            f'</div>'
        )

    def page_link(number: int, label: str) -> str:
        source_arg = f"&source_id={source_id}" if source_id is not None else ""
        return f'<a class="button secondary" href="/projects/{project_id}/faces/gallery?page={number}{source_arg}">{label}</a>'

    nav = '<div class="row" style="justify-content:space-between;align-items:center">'
    nav += page_link(page_number - 1, "Previous") if page_number > 1 else '<span></span>'
    nav += f'<span class="muted">Page {page_number} of {pages}</span>'
    nav += page_link(page_number + 1, "Next") if page_number < pages else '<span></span>'
    nav += '</div>'

    body = (
        f'<div class="row" style="justify-content:space-between"><div><h1>Detected Faces Gallery</h1>'
        f'<p class="muted">{total} detected face region(s). Each card links to its source photograph.</p></div>'
        f'<a class="button secondary" href="/ui/projects/{project_id}">Back to Project</a></div>'
        f'<div class="card"><form class="row" method="get" action="/projects/{project_id}/faces/gallery">'
        f'<select name="source_id">{"".join(options)}</select><button type="submit">Filter Gallery</button></form></div>'
        f'{nav}<div class="grid">{"".join(cards) or "<div class=\"card\">No detected faces in this scope.</div>"}</div>{nav}'
    )
    return page(f"{project.name} Faces", body)
