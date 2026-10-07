import re

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Photo, PhotoSource, Project
from app.services.drive_urls import extract_folder_id
from app.services.local_storage import validate_local_source

router = APIRouter(prefix="/projects", tags=["projects"])


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "project"


@router.get("")
def list_projects(session: Session = Depends(get_session)):
    projects = session.scalars(select(Project).order_by(Project.created_at.desc())).all()
    return [
        {"id": p.id, "name": p.name, "slug": p.slug, "public_enabled": p.public_enabled}
        for p in projects
    ]


@router.post("")
def create_project(name: str = Form(...), session: Session = Depends(get_session)):
    name = name.strip()
    if not name:
        raise HTTPException(400, "Project name is required")
    base = _slugify(name)
    slug = base
    suffix = 2
    while session.scalar(select(Project.id).where(Project.slug == slug)):
        slug = f"{base}-{suffix}"
        suffix += 1
    project = Project(name=name, slug=slug)
    session.add(project)
    session.commit()
    return RedirectResponse(f"/projects/{project.id}/dashboard", status_code=303)


@router.get("/{project_id}/dashboard")
def project_dashboard(project_id: int, session: Session = Depends(get_session)):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    sources = session.scalars(select(PhotoSource).where(PhotoSource.project_id == project_id)).all()
    photo_count = session.scalar(select(func.count(Photo.id)).where(Photo.project_id == project_id)) or 0
    return {
        "project": {"id": project.id, "name": project.name, "slug": project.slug},
        "photo_count": photo_count,
        "sources": [
            {"id": s.id, "type": s.source_type, "name": s.display_name, "uri": s.source_uri, "active": s.active}
            for s in sources
        ],
    }


@router.post("/{project_id}/sources/google-drive")
def add_drive_source(
    project_id: int,
    folder_url: str = Form(...),
    display_name: str = Form(""),
    storage_account_id: int | None = Form(None),
    session: Session = Depends(get_session),
):
    if not session.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    try:
        folder_id = extract_folder_id(folder_url)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    source = PhotoSource(
        project_id=project_id,
        source_type="google_drive",
        source_key=folder_id,
        source_uri=folder_url.strip(),
        display_name=display_name.strip() or None,
        storage_account_id=storage_account_id,
    )
    session.add(source)
    session.commit()
    return RedirectResponse(f"/projects/{project_id}/dashboard", status_code=303)


@router.post("/{project_id}/sources/local")
def add_local_source(
    project_id: int,
    folder_path: str = Form(...),
    display_name: str = Form(""),
    removable_media: bool = Form(False),
    session: Session = Depends(get_session),
):
    if not session.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    try:
        path = validate_local_source(folder_path)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    source = PhotoSource(
        project_id=project_id,
        source_type="local_folder",
        source_key=str(path),
        source_uri=str(path),
        display_name=display_name.strip() or path.name,
        removable_media=removable_media,
    )
    session.add(source)
    session.commit()
    return RedirectResponse(f"/projects/{project_id}/dashboard", status_code=303)
