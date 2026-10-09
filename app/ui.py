from html import escape

from app.branding import ACCENT_COLOR, APP_NAME, COMPANY_NAME, LOGO_URL, PRIMARY_COLOR
from app.database import SessionLocal
from app.settings import get_app_settings


def _branding():
    try:
        with SessionLocal() as session:
            return get_app_settings(session)
    except Exception:
        class Defaults:
            app_name = APP_NAME
            company_name = COMPANY_NAME
            primary_color = PRIMARY_COLOR
            accent_color = ACCENT_COLOR
            logo_url = LOGO_URL
        return Defaults()


def page(title: str, body: str, show_nav: bool = True, user=None) -> str:
    brand = _branding()
    app_name, company_name = brand.app_name, brand.company_name
    logo_url, primary_color, accent_color = brand.logo_url, brand.primary_color, brand.accent_color
    csrf_script = '''<script>(function(){function cookie(name){const prefix=name+'=';for(const part of document.cookie.split(';')){const item=part.trim();if(item.startsWith(prefix))return decodeURIComponent(item.slice(prefix.length));}return '';}const token=cookie('auroara_fpf_csrf');if(!token)return;document.querySelectorAll('form[method="post"],form[method="POST"]').forEach(function(form){if(!form.querySelector('input[name="csrf_token"]')){const input=document.createElement('input');input.type='hidden';input.name='csrf_token';input.value=token;form.appendChild(input);}});const original=window.fetch;window.fetch=function(input,init){init=init||{};const isRequest=typeof Request!=='undefined'&&input instanceof Request;const method=(init.method||(isRequest?input.method:'GET')).toUpperCase();const target=isRequest?input.url:String(input);const url=new URL(target,window.location.href);if(url.origin===window.location.origin&&!['GET','HEAD','OPTIONS','TRACE'].includes(method)){const headers=new Headers(init.headers||(isRequest?input.headers:undefined));headers.set('X-CSRF-Token',token);init.headers=headers;}return original(input,init);};})();</script>'''
    if show_nav:
        links = ['<a href="/">Home</a>', '<a href="/ui/projects">Projects</a>']
        if user is not None and getattr(user, "role", None) == "admin":
            links.extend(['<a href="/ui/accounts">Storage Accounts</a>', '<a href="/ui/users">Users</a>', '<a href="/ui/settings">System Settings</a>'])
        account = ""
        if user is not None:
            label = escape(getattr(user, "display_name", None) or getattr(user, "username", "User"))
            role = escape(getattr(user, "role", "user").replace("_", " ").title())
            account = f'<span class="user-chip">{label}<small>{role}</small></span><form action="/logout" method="post"><button class="nav-logout" type="submit">Log out</button></form>'
        header = f'''<header><nav><a class="brand" href="/"><img src="{escape(logo_url)}" alt="{escape(app_name)} logo"><span class="brand-copy"><span class="brand-title">{escape(app_name)}</span><span class="brand-company">{escape(company_name)}</span></span></a><div class="nav-links">{"".join(links)}{account}</div></nav></header>'''
    else:
        header = f'''<header><nav style="justify-content:center"><span class="brand"><img src="{escape(logo_url)}" alt="{escape(app_name)} logo"><span class="brand-copy"><span class="brand-title">{escape(app_name)}</span><span class="brand-company">{escape(company_name)}</span></span></span></nav></header>'''
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} · {escape(app_name)}</title><style>
:root{{--bg:#f5f7fa;--card:#fff;--ink:#172033;--muted:#667085;--line:#e3e8ef;--accent:{accent_color};--brand:{primary_color};--ok:#137a42;--shadow:0 8px 28px rgba(16,24,40,.06)}}*{{box-sizing:border-box}}body{{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--ink)}}header{{background:#fff;color:var(--ink);padding:0 24px;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:20;box-shadow:0 2px 10px rgba(16,24,40,.035)}}nav{{max-width:1240px;min-height:74px;margin:auto;display:flex;align-items:center;justify-content:space-between;gap:22px}}.brand{{display:flex;align-items:center;gap:12px;text-decoration:none;color:var(--brand)}}.brand img{{width:48px;height:48px;object-fit:contain;border-radius:8px}}.brand-copy{{display:flex;flex-direction:column;line-height:1.1}}.brand-title{{font-weight:800;font-size:17px;letter-spacing:-.2px}}.brand-company{{font-size:10px;color:var(--muted);margin-top:4px;text-transform:uppercase;letter-spacing:.8px}}.nav-links{{display:flex;align-items:center;gap:6px}}nav .nav-links a{{color:#344054;text-decoration:none;margin:0;padding:9px 12px;border-radius:9px;font-weight:600;font-size:14px}}nav .nav-links a:hover{{background:#eef4f8;color:var(--brand)}}.user-chip{{display:flex;flex-direction:column;margin-left:8px;padding-left:12px;border-left:1px solid var(--line);font-size:13px;font-weight:700}}.user-chip small{{font-size:10px;color:var(--muted);font-weight:600}}.nav-logout{{padding:8px 10px;background:#344054;font-size:12px}}main{{max-width:1240px;margin:32px auto;padding:0 24px 44px}}.card{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:22px;box-shadow:var(--shadow);margin-bottom:18px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}}.stat{{font-size:30px;font-weight:780;color:var(--brand)}}.muted{{color:var(--muted)}}.row{{display:flex;gap:12px;align-items:center;flex-wrap:wrap}}.stack{{display:flex;flex-direction:column;gap:14px;align-items:stretch}}.stack label{{display:flex;flex-direction:column;gap:6px;font-weight:600}}.stack input{{width:100%}}.split-panel{{display:grid;grid-template-columns:minmax(150px,190px) minmax(0,1fr);gap:26px;align-items:start}}.action-list{{display:flex;flex-direction:column;gap:9px;align-items:stretch;max-width:420px}}.action-list .button{{display:flex;justify-content:space-between;gap:18px;width:100%;text-align:left}}main .card>.row:has(>img[alt="Selected face"]){{display:grid;grid-template-columns:150px minmax(0,1fr);gap:28px;align-items:start}}main .card>.row:has(>img[alt="Selected face"])>img{{width:150px!important;height:150px!important;box-shadow:0 6px 18px rgba(16,24,40,.12)}}main .card>.row:has(>img[alt="Selected face"])>div>div.row{{flex-direction:column;align-items:stretch;max-width:430px;gap:8px}}main .card>.row:has(>img[alt="Selected face"])>div>div.row .button{{width:100%;display:flex;justify-content:space-between;text-align:left}}input,select{{padding:11px 12px;border:1px solid #cfd6df;border-radius:9px;min-width:220px;background:white;color:var(--ink)}}button,.button{{background:var(--accent);color:white;border:0;border-radius:9px;padding:11px 15px;font-weight:650;cursor:pointer;text-decoration:none;display:inline-block;transition:transform .08s ease,opacity .15s ease,box-shadow .15s ease}}button:hover,.button:hover{{opacity:.94;box-shadow:0 5px 14px rgba(0,0,0,.09)}}.secondary{{background:#344054}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:12px;border-bottom:1px solid var(--line);vertical-align:top}}.pill{{display:inline-block;padding:5px 9px;border-radius:999px;background:#eef3ff;color:#244aa5;font-size:12px}}h1,h2{{margin-top:0;letter-spacing:-.4px}}h3{{margin-top:0}}code{{font-size:12px}}@media(max-width:760px){{header{{padding:0 14px}}nav{{min-height:66px}}.brand-company,.user-chip{{display:none}}.brand img{{width:40px;height:40px}}.nav-links{{gap:2px;flex-wrap:wrap;justify-content:flex-end}}.nav-links a{{padding:8px 7px;font-size:12px}}main{{padding:0 14px 32px;margin-top:22px}}.split-panel,main .card>.row:has(>img[alt="Selected face"]){{grid-template-columns:1fr}}table{{display:block;overflow:auto}}}}
</style></head><body>{header}<main>{body}</main>{csrf_script}</body></html>'''
