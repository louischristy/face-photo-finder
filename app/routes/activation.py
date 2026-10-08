import json
from html import escape

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app.licensing import LICENCE_FILE, PUBLIC_KEY_FILE, activation_request_code, licence_status, verify_licence_document
from app.ui import page

router = APIRouter(tags=["activation"])
MAX_LICENCE_BYTES = 128 * 1024


def _screen(error: str = "") -> str:
    status = licence_status()
    if status.active:
        body = f'''<div style="max-width:720px;margin:45px auto"><div class="card"><h1>Product Activated</h1><p>Auroara Face Photo Finder is activated for this computer.</p><p><strong>Customer:</strong> {escape(status.customer or "Development installation")}<br><strong>Licence ID:</strong> {escape(status.licence_id or "—")}<br><strong>Expires:</strong> {escape(status.expires_on or "No expiry")}</p><p><a class="button" href="/">Continue</a></p></div></div>'''
        return page("Product Activation", body, show_nav=False)
    error_html = f'<div class="card" style="border-color:#dc2626;color:#991b1b">{escape(error)}</div>' if error else ""
    code = escape(activation_request_code())
    body = f'''<div style="max-width:760px;margin:45px auto">{error_html}<div class="card"><h1>Activate Auroara Face Photo Finder</h1><p class="muted">This installation must be activated before first use. Activation is bound to this computer.</p><h3>1. Activation request code</h3><textarea readonly style="width:100%;min-height:125px;padding:12px;border:1px solid #cfd6df;border-radius:9px">{code}</textarea><p class="muted">Send this request code to Auroara's licence issuing service or authorised administrator. It contains a one-way machine fingerprint, product identifier and platform information.</p><h3>2. Install activation file</h3><form class="stack" action="/activate" method="post" enctype="multipart/form-data"><label>Signed Auroara licence file<input type="file" name="licence_file" accept="application/json,.json,.licence" required></label><button type="submit">Verify and Activate</button></form><p class="muted">The signed activation file can be installed offline. The Auroara private signing key is never stored in this application.</p></div></div>'''
    return page("Product Activation", body, show_nav=False)


@router.get("/activate", response_class=HTMLResponse)
def activation_page():
    return _screen()


@router.post("/activate", response_class=HTMLResponse)
async def install_activation(licence_file: UploadFile = File(...)):
    data = await licence_file.read(MAX_LICENCE_BYTES + 1)
    if not data or len(data) > MAX_LICENCE_BYTES:
        return HTMLResponse(_screen("Licence file is empty or too large."), status_code=400)
    if not PUBLIC_KEY_FILE.exists():
        return HTMLResponse(_screen("Licence verification key is not installed in this build."), status_code=503)
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return HTMLResponse(_screen("Licence file is not valid JSON."), status_code=400)
    status = verify_licence_document(document, PUBLIC_KEY_FILE.read_bytes())
    if not status.active:
        return HTMLResponse(_screen(status.message), status_code=400)
    LICENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = LICENCE_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(document, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    temporary.replace(LICENCE_FILE)
    return RedirectResponse("/activate", status_code=303)
