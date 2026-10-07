from html import escape

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Photo, PhotoSource, Project, StorageAccount
from app.ui import page

router = APIRouter(prefix="/ui", tags=["ui"])


@router.get("/projects", response_class=HTMLResponse)
def projects_page(session: Session = Depends(get_session)):
    projects = session.scalars(select(Project).order_by(Project.created_at.desc())).all()
    cards = "".join(f'<div class="card"><h2>{escape(p.name)}</h2><div class="muted">{escape(p.slug)}</div><p><a class="button" href="/ui/projects/{p.id}">Open Project</a></p></div>' for p in projects)
    body = '<div class="card"><h1>Projects</h1><p class="muted">Each project has an isolated catalogue and face index.</p><form class="row" action="/projects" method="post"><input name="name" placeholder="Project name" required><button>Create Project</button></form></div>' + (cards or '<div class="card">No projects yet.</div>')
    return page("Projects", body)


@router.get("/accounts", response_class=HTMLResponse)
def accounts_page(session: Session = Depends(get_session)):
    accounts = session.scalars(select(StorageAccount).order_by(StorageAccount.created_at.desc())).all()
    rows = "".join(f'<tr><td>{escape(a.label)}</td><td>{escape(a.account_hint or "—")}</td><td>{escape(a.provider)}</td><td>{"Active" if a.active else "Disabled"}</td></tr>' for a in accounts)
    body = f'''<div class="card"><h1>Storage Accounts</h1><p>Connect multiple Google identities. OAuth tokens stay on this computer.</p><form class="row" action="/accounts/google" method="post"><input name="label" placeholder="e.g. Event Google Account 1"><button>Connect Google Account</button></form><p class="muted">Google connection requires credentials.json in the application folder.</p></div><div class="card"><table><thead><tr><th>Label</th><th>Account</th><th>Provider</th><th>Status</th></tr></thead><tbody>{rows or '<tr><td colspan="4">No cloud accounts connected.</td></tr>'}</tbody></table></div>'''
    return page("Storage Accounts", body)


@router.get("/projects/{project_id}", response_class=HTMLResponse)
def project_page(project_id: int, session: Session = Depends(get_session)):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    sources = session.scalars(select(PhotoSource).where(PhotoSource.project_id == project_id).order_by(PhotoSource.id)).all()
    accounts = session.scalars(select(StorageAccount).where(StorageAccount.provider == "google_drive", StorageAccount.active.is_(True))).all()
    photo_count = session.scalar(select(func.count(Photo.id)).where(Photo.project_id == project_id)) or 0
    pending = session.scalar(select(func.count(Photo.id)).where(Photo.project_id == project_id, Photo.indexed.is_(False))) or 0
    account_options = ''.join(f'<option value="{a.id}">{escape(a.label)} — {escape(a.account_hint or "connected")}</option>' for a in accounts)
    source_rows = ''.join(f'''<tr><td><input type="checkbox" name="source_ids" value="{s.id}" checked></td><td>{escape(s.display_name or "Unnamed source")}</td><td><span class="pill">{escape(s.source_type)}</span></td><td>{escape(s.source_uri)}</td><td>{s.last_scanned_at.strftime("%Y-%m-%d %H:%M") if s.last_scanned_at else "Never"}</td><td><form action="/projects/{project_id}/sources/{s.id}/scan" method="post"><button>Scan / Update</button></form></td></tr>''' for s in sources)
    body = f'''<div class="row" style="justify-content:space-between"><div><h1>{escape(project.name)}</h1><div class="muted">Project-specific catalogue and search scope</div></div><a class="button secondary" href="/ui/projects">All Projects</a></div><div class="grid"><div class="card"><div class="stat">{photo_count}</div><div class="muted">Catalogued photos</div></div><div class="card"><div class="stat">{pending}</div><div class="muted">Awaiting face indexing</div></div><div class="card"><div class="stat">{len(sources)}</div><div class="muted">Storage sources</div></div></div><div class="card"><h2>Add Google Drive Source</h2><form class="row" action="/projects/{project_id}/sources/google-drive" method="post"><select name="storage_account_id" required><option value="">Choose Google account</option>{account_options}</select><input name="folder_url" placeholder="Google Drive folder link" required><input name="display_name" placeholder="Source name"><button>Add Drive Folder</button></form><p class="muted"><a href="/ui/accounts">Connect another Google account</a></p></div><div class="card"><h2>Add Local / External Folder</h2><form class="row" action="/projects/{project_id}/sources/local" method="post"><input name="folder_path" placeholder="/Volumes/Event SSD/Photos or C:\\Photos" required><input name="display_name" placeholder="Source name"><label><input style="min-width:auto" type="checkbox" name="removable_media" value="true"> External/removable</label><button>Add Folder</button></form></div><div class="card"><h2>Search Scope</h2><p class="muted">Choose all project sources or only the locations that should participate in a face search.</p><form action="/projects/{project_id}/search-scope" method="post"><table><thead><tr><th>Use</th><th>Source</th><th>Type</th><th>Location</th><th>Last Scan</th><th>Catalogue</th></tr></thead><tbody>{source_rows or '<tr><td colspan="6">Add a storage source to begin.</td></tr>'}</tbody></table><p><button type="submit">Use Selected Sources</button></p></form></div>'''
    return page(project.name, body)
