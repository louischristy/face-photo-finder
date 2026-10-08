from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select

from app.auth import SESSION_COOKIE, require_user
from app.branding import APP_NAME
from app.csrf import csrf_token, enforce_csrf
from app.database import SessionLocal, engine
from app.licensing import licence_status
from app.models import Base, User
from app.routes.accounts import router as accounts_router
from app.routes.activation import router as activation_router
from app.routes.admin_settings import router as admin_settings_router
from app.routes.admin_users import router as admin_users_router
from app.routes.auth import router as auth_router
from app.routes.brand import router as brand_router
from app.routes.faces import router as faces_router
from app.routes.gallery import router as gallery_router
from app.routes.media import bulk_router as bulk_media_router, router as media_router
from app.routes.projects import router as projects_router
from app.routes.search import router as search_router
from app.routes.ui import router as ui_router
from app.services.diagnostics import system_diagnostics


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title=APP_NAME, version="0.7.0", lifespan=lifespan)


@app.middleware("http")
async def activation_and_csrf_middleware(request: Request, call_next):
    path = request.url.path
    status = licence_status()
    activation_allowed = path == "/activate" or path.startswith("/brand/") or path == "/health"
    if not status.active and not activation_allowed:
        return RedirectResponse("/activate", status_code=303)
    await enforce_csrf(request)
    response = await call_next(request)
    session_token = request.cookies.get(SESSION_COOKIE)
    if session_token:
        response.set_cookie("auroara_fpf_csrf", csrf_token(session_token), max_age=12 * 60 * 60, httponly=False, samesite="strict", secure=False, path="/")
    else:
        response.delete_cookie("auroara_fpf_csrf", path="/")
    return response


app.include_router(activation_router)
app.include_router(auth_router)
app.include_router(accounts_router)
app.include_router(projects_router)
app.include_router(search_router)
app.include_router(faces_router)
app.include_router(gallery_router, dependencies=[Depends(require_user)])
app.include_router(media_router)
app.include_router(bulk_media_router)
app.include_router(brand_router)
app.include_router(admin_users_router)
app.include_router(admin_settings_router)
app.include_router(ui_router, dependencies=[Depends(require_user)])


@app.get("/health")
def health():
    diagnostics = system_diagnostics(); licence = licence_status()
    return {"status": "ok" if diagnostics["ready"] and licence.active else "setup_required", "version": "0.7.0", "licence": {"active": licence.active, "state": licence.state}, "diagnostics": diagnostics}


@app.get("/")
def home():
    if not licence_status().active: return RedirectResponse("/activate", status_code=307)
    with SessionLocal() as session: users = session.scalar(select(func.count(User.id))) or 0
    return RedirectResponse("/login" if users else "/setup", status_code=307)
