from html import escape

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import get_session
from app.licensing import activation_request_code, licence_status
from app.models import User
from app.settings import get_values, save_settings
from app.ui import page

router = APIRouter(prefix="/ui/settings", tags=["admin-settings"])


def _options(values, selected):
    return "".join(f'<option value="{escape(value)}"{" selected" if value == selected else ""}>{escape(label)}</option>' for value, label in values)


@router.get("", response_class=HTMLResponse)
def settings_page(request: Request, session: Session = Depends(get_session), admin: User = Depends(require_admin)):
    v = get_values(session); licence = licence_status()
    search_options = _options((("strict", "Strict"), ("recommended", "Recommended"), ("balanced", "Balanced"), ("broad", "Broad")), v["search.default_mode"])
    gallery_options = _options((("conservative", "Conservative"), ("normal", "Normal"), ("aggressive", "Aggressive")), v["gallery.default_dedup"])
    licence_html = f'''<div class="card"><h2>Product Licence</h2><div class="grid"><div><div class="muted">Status</div><strong>{escape(licence.state.replace('_',' ').title())}</strong></div><div><div class="muted">Customer</div><strong>{escape(licence.customer or '—')}</strong></div><div><div class="muted">Licence ID</div><strong>{escape(licence.licence_id or '—')}</strong></div><div><div class="muted">Expiry</div><strong>{escape(licence.expires_on or 'No expiry')}</strong></div></div><p class="muted">{escape(licence.message)}</p><details><summary>Machine activation request</summary><textarea readonly style="width:100%;min-height:110px;margin-top:12px;padding:12px;border:1px solid #cfd6df;border-radius:9px">{escape(activation_request_code())}</textarea></details></div>'''
    body = f'''<div class="row" style="justify-content:space-between"><div><h1>System Settings</h1><p class="muted">White-label branding and application defaults. Changes are stored locally with this installation.</p></div></div>{licence_html}
<form class="stack" action="/ui/settings" method="post">
<div class="card"><h2>Branding</h2><div class="grid"><label>Application name<input name="app_name" value="{escape(v['branding.app_name'])}" maxlength="100" required></label><label>Company / organisation<input name="company_name" value="{escape(v['branding.company_name'])}" maxlength="150" required></label><label>Primary colour<input name="primary_color" value="{escape(v['branding.primary_color'])}" pattern="#[0-9A-Fa-f]{{6}}" required></label><label>Accent colour<input name="accent_color" value="{escape(v['branding.accent_color'])}" pattern="#[0-9A-Fa-f]{{6}}" required></label></div><label>Logo URL<input name="logo_url" value="{escape(v['branding.logo_url'])}" maxlength="500" required></label><p class="muted">Use the packaged Auroara logo path or an HTTPS URL. Customer-specific logo assets can be bundled with a white-label build.</p></div>
<div class="card"><h2>Operational Defaults</h2><div class="grid"><label>Default face-search mode<select name="default_search_mode">{search_options}</select></label><label>Default representative-gallery mode<select name="default_gallery_dedup">{gallery_options}</select></label></div><p class="muted">Users can still select another search or gallery mode for an individual operation.</p></div>
<div class="card"><button type="submit">Save System Settings</button> <span class="muted">Administrator access only.</span></div></form>'''
    return page("System Settings", body, user=admin, session_token=request.cookies.get("auroara_fpf_session", ""))


@router.post("")
def update_settings(app_name: str = Form(...), company_name: str = Form(...), primary_color: str = Form(...), accent_color: str = Form(...), logo_url: str = Form(...), default_search_mode: str = Form(...), default_gallery_dedup: str = Form(...), session: Session = Depends(get_session), _: User = Depends(require_admin)):
    try:
        save_settings(session, {"branding.app_name":app_name,"branding.company_name":company_name,"branding.primary_color":primary_color,"branding.accent_color":accent_color,"branding.logo_url":logo_url,"search.default_mode":default_search_mode,"gallery.default_dedup":default_gallery_dedup})
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc
    return RedirectResponse("/ui/settings",status_code=303)
