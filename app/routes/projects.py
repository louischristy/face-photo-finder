import re

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_admin, require_user
from app.database import get_session
from app.models import Photo, PhotoSource, Project, StorageAccount, User
from app.services.drive_urls import extract_folder_id
from app.services.local_storage import validate_local_source
from app.services.source_scanner import scan_source

router = APIRouter(prefix="/projects", tags=["projects"])


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "project"


@router.get("")
def list_projects(session: Session = Depends(get_session), _: User = Depends(require_user)):
    projects = session.scalars(select(Project).order_by(Project.created_at.desc())).all()
    return [{"id": p.id, "name": p.name, "slug": p.slug, "public_enabled": p.public_enabled} for p in projects]


@router.post("")
def create_project(name: str = Form(...), session: Session = Depends(get_session), _: User = Depends(require_admin)):
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
    return RedirectResponse(f"/ui/projects/{project.id}", status_code=303)


@router.get("/{project_id}/dashboard")
def project_dashboard(project_id: int, session: Session = Depends(get_session), _: User = Depends(require_user)):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    sources = session.scalars(select(PhotoSource).where(PhotoSource.project_id == project_id)).all()
    accounts = session.scalars(select(StorageAccount).where(StorageAccount.active.is_(True))).all()
    photo_count = session.scalar(select(func.count(Photo.id)).where(Photo.project_id == project_id)) or 0
    pending_count = session.scalar(select(func.count(Photo.id)).where(Photo.project_id == project_id, Photo.indexed.is_(False))) or 0
    return {"project": {"id": project.id, "name": project.name, "slug": project.slug}, "photo_count": photo_count, "pending_face_index": pending_count, "google_accounts": [{"id": a.id, "label": a.label, "account": a.account_hint} for a in accounts if a.provider == "google_drive"], "sources": [{"id": s.id, "type": s.source_type, "name": s.display_name, "uri": s.source_uri, "active": s.active, "removable": s.removable_media, "last_scanned_at": s.last_scanned_at.isoformat() if s.last_scanned_at else None} for s in sources]}


@router.post("/{project_id}/sources/google-drive")
def add_drive_source(project_id: int, folder_url: str = Form(...), display_name: str = Form(""), storage_account_id: int | None = Form(None), session: Session = Depends(get_session), _: User = Depends(require_admin)):
    if not session.get(Project, project_id): raise HTTPException(404, "Project not found")
    if storage_account_id is None: raise HTTPException(400, "Select the Google account that can access this folder")
    account = session.get(StorageAccount, storage_account_id)
    if not account or account.provider != "google_drive": raise HTTPException(400, "Invalid Google account")
    try: folder_id = extract_folder_id(folder_url)
    except ValueError as exc: raise HTTPException(400, str(exc)) from exc
    source = PhotoSource(project_id=project_id, source_type="google_drive", source_key=folder_id, source_uri=folder_url.strip(), display_name=display_name.strip() or None, storage_account_id=storage_account_id)
    session.add(source)
    try: session.commit()
    except IntegrityError as exc:
        session.rollback(); raise HTTPException(409, "This source is already attached to the project") from exc
    return RedirectResponse(f"/ui/projects/{project_id}", status_code=303)


@router.post("/{project_id}/sources/local")
def add_local_source(project_id: int, folder_path: str = Form(...), display_name: str = Form(""), removable_media: bool = Form(False), session: Session = Depends(get_session), _: User = Depends(require_admin)):
    if not session.get(Project, project_id): raise HTTPException(404, "Project not found")
    try: path = validate_local_source(folder_path)
    except ValueError as exc: raise HTTPException(400, str(exc)) from exc
    source = PhotoSource(project_id=project_id, source_type="local_folder", source_key=str(path), source_uri=str(path), display_name=display_name.strip() or path.name, removable_media=removable_media)
    session.add(source)
    try: session.commit()
    except IntegrityError as exc:
        session.rollback(); raise HTTPException(409, "This source is already attached to the project") from exc
    return RedirectResponse(f"/ui/projects/{project_id}", status_code=303)


@router.post("/{project_id}/sources/{source_id}/scan")
def scan_project_source(project_id: int, source_id: int, session: Session = Depends(get_session), _: User = Depends(require_user)):
    source = session.get(PhotoSource, source_id)
    if not source or source.project_id != project_id: raise HTTPException(404, "Source not found in this project")
    try: result = scan_source(session, source)
    except (ValueError, FileNotFoundError) as exc: raise HTTPException(400, str(exc)) from exc
    return {"source_id": source_id, **result}
