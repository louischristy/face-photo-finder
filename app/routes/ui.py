from html import escape

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Face, Photo, PhotoSource, Project, StorageAccount
from app.ui import page

router = APIRouter(prefix="/ui", tags=["ui"])


def _busy_form(action: str, inner: str, message: str, form_class: str = "row") -> str:
    return f'<form class="{form_class} busy-form" action="{action}" method="post" data-busy-message="{escape(message)}">{inner}</form>'


@router.get("/projects", response_class=HTMLResponse)
def projects_page(session: Session = Depends(get_session)):
    projects = session.scalars(select(Project).order_by(Project.created_at.desc())).all()
    cards = "".join(f'<div class="card"><h2>{escape(p.name)}</h2><div class="muted">{escape(p.slug)}</div><p><a class="button" href="/ui/projects/{p.id}">Open Project</a></p></div>' for p in projects)
    body = '<div class="card"><h1>Projects</h1><p class="muted">Each project has an isolated catalogue and face index.</p><form class="row busy-form" action="/projects" method="post" data-busy-message="Creating project..."><input name="name" placeholder="Project name" required><button type="submit">Create Project</button><span class="busy-status muted" role="status"></span></form></div>' + (cards or '<div class="card">No projects yet.</div>') + BUSY_SCRIPT
    return page("Projects", body)


@router.get("/accounts", response_class=HTMLResponse)
def accounts_page(session: Session = Depends(get_session)):
    accounts = session.scalars(select(StorageAccount).order_by(StorageAccount.created_at.desc())).all()
    rows = "".join(f'<tr><td>{escape(a.label)}</td><td>{escape(a.account_hint or "—")}</td><td>{escape(a.provider)}</td><td>{"Active" if a.active else "Disabled"}</td></tr>' for a in accounts)
    body = f'<div class="card"><h1>Storage Accounts</h1><p>Connect multiple Google identities. OAuth tokens stay on this computer.</p><form class="row busy-form" action="/accounts/google" method="post" data-busy-message="Opening Google connection..."><input name="label" placeholder="e.g. Event Google Account 1"><button type="submit">Connect Google Account</button><span class="busy-status muted" role="status"></span></form><p class="muted">Google connection requires credentials.json in the application folder.</p></div><div class="card"><table><thead><tr><th>Label</th><th>Account</th><th>Provider</th><th>Status</th></tr></thead><tbody>{rows or "<tr><td colspan=4>No cloud accounts connected.</td></tr>"}</tbody></table></div>{BUSY_SCRIPT}'
    return page("Storage Accounts", body)


@router.get("/projects/{project_id}", response_class=HTMLResponse)
def project_page(project_id: int, request: Request, session: Session = Depends(get_session)):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    sources = session.scalars(select(PhotoSource).where(PhotoSource.project_id == project_id).order_by(PhotoSource.id)).all()
    accounts = session.scalars(select(StorageAccount).where(StorageAccount.provider == "google_drive", StorageAccount.active.is_(True))).all()
    photo_count = session.scalar(select(func.count(Photo.id)).where(Photo.project_id == project_id)) or 0
    pending = session.scalar(select(func.count(Photo.id)).where(Photo.project_id == project_id, Photo.indexed.is_(False))) or 0
    face_count = session.scalar(select(func.count(Face.id)).where(Face.project_id == project_id)) or 0
    account_options = ''.join(f'<option value="{a.id}">{escape(a.label)} — {escape(a.account_hint or "connected")}</option>' for a in accounts)
    index_checks = ''.join(f'<label><input style="min-width:auto" type="checkbox" name="source_ids" value="{s.id}" checked> {escape(s.display_name or s.source_type)}</label>' for s in sources)
    search_checks = ''.join(f'<label><input style="min-width:auto" type="checkbox" name="source_ids" value="{s.id}" checked> {escape(s.display_name or s.source_type)}</label>' for s in sources)
    source_rows = ''.join(f'<tr><td>{escape(s.display_name or "Unnamed source")}</td><td><span class="pill">{escape(s.source_type)}</span></td><td>{escape(s.source_uri)}</td><td>{s.last_scanned_at.strftime("%Y-%m-%d %H:%M") if s.last_scanned_at else "Never"}</td><td><form class="busy-form" action="/projects/{project_id}/sources/{s.id}/scan" method="post" data-busy-message="Scanning source..."><button type="submit">Scan / Update</button><span class="busy-status muted" role="status"></span></form></td></tr>' for s in sources)

    indexed = request.query_params.get("indexed")
    indexed_faces = request.query_params.get("faces")
    failed = request.query_params.get("failed")
    result_banner = ""
    if indexed is not None:
        result_banner = f'<div class="card"><strong>Face indexing completed.</strong> Processed {escape(indexed)} photo(s), detected {escape(indexed_faces or "0")} face(s), failed {escape(failed or "0")}.</div>'

    body = f'''<div class="row" style="justify-content:space-between"><div><h1>{escape(project.name)}</h1><div class="muted">Project-specific catalogue and face search</div></div><a class="button secondary" href="/ui/projects">All Projects</a></div>
{result_banner}
<div class="grid"><div class="card"><div class="stat">{photo_count}</div><div class="muted">Catalogued photos</div></div><div class="card"><div class="stat">{pending}</div><div class="muted">Awaiting face indexing</div></div><div class="card"><div class="stat">{face_count}</div><div class="muted">Detected faces</div></div><div class="card"><div class="stat">{len(sources)}</div><div class="muted">Storage sources</div></div></div>
<div class="card"><h2>Add Google Drive Source</h2><form class="row busy-form" action="/projects/{project_id}/sources/google-drive" method="post" data-busy-message="Adding Google Drive source..."><select name="storage_account_id" required><option value="">Choose Google account</option>{account_options}</select><input name="folder_url" placeholder="Google Drive folder link" required><input name="display_name" placeholder="Source name"><button type="submit">Add Drive Folder</button><span class="busy-status muted" role="status"></span></form><p class="muted"><a href="/ui/accounts">Connect another Google account</a></p></div>
<div class="card"><h2>Add Local / External Folder</h2><form class="row busy-form" action="/projects/{project_id}/sources/local" method="post" data-busy-message="Adding folder..."><input name="folder_path" placeholder="/Volumes/Event SSD/Photos or C:\\Photos" required><input name="display_name" placeholder="Source name"><label><input style="min-width:auto" type="checkbox" name="removable_media" value="true"> External/removable</label><button type="submit">Add Folder</button><span class="busy-status muted" role="status"></span></form></div>
<div class="card"><h2>Storage Sources</h2><table><thead><tr><th>Source</th><th>Type</th><th>Location</th><th>Last Scan</th><th>Catalogue</th></tr></thead><tbody>{source_rows or '<tr><td colspan="5">Add a storage source to begin.</td></tr>'}</tbody></table></div>
<div class="card"><h2>1. Build / Update Face Index</h2><p class="muted">Only new or changed photos are processed. Google Drive images are downloaded temporarily for processing and are not permanently copied.</p><form id="face-index-form" class="row busy-form" action="/projects/{project_id}/faces/index" method="post" data-require-sources="true" data-busy-message="Indexing selected sources... Keep this page open; Drive photos are processed sequentially.">{index_checks}<button type="submit">Index Faces</button><span class="busy-status muted" role="status"></span></form></div>
<div class="card"><h2>2. Find My Photos</h2><p class="muted">Upload one clear reference photo. It is processed temporarily and is not stored.</p><form class="busy-form" action="/projects/{project_id}/faces/search" method="post" enctype="multipart/form-data" data-busy-message="Searching indexed faces..."><div class="row"><input type="file" name="reference" accept="image/*" required><select name="mode"><option value="strict">Strict</option><option value="recommended" selected>Recommended</option><option value="balanced">Balanced</option><option value="broad">Broad</option></select></div><div class="row" style="margin-top:12px">{search_checks}</div><p><button type="submit">Search Matching Photos</button> <span class="busy-status muted" role="status"></span></p></form></div>
{BUSY_SCRIPT}'''
    return page(project.name, body)


BUSY_SCRIPT = '''<script>
document.querySelectorAll('form.busy-form').forEach(function(form) {
  form.addEventListener('submit', function(event) {
    if (form.dataset.busy === '1') {
      event.preventDefault();
      return;
    }
    if (form.dataset.requireSources === 'true' && !form.querySelector('input[name="source_ids"]:checked')) {
      event.preventDefault();
      alert('Select at least one source first.');
      return;
    }
    form.dataset.busy = '1';
    const button = form.querySelector('button[type="submit"]');
    const status = form.querySelector('.busy-status');
    if (button) {
      button.dataset.originalText = button.textContent;
      button.disabled = true;
      button.textContent = 'Processing...';
      button.style.opacity = '0.65';
    }
    if (status) {
      status.textContent = form.dataset.busyMessage || 'Processing... Please wait.';
    }
  });
});
</script>'''
