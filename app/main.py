from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select

from app.branding import APP_NAME
from app.database import SessionLocal, engine
from app.models import Base, User
from app.routes.accounts import router as accounts_router
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
app.include_router(auth_router)
app.include_router(accounts_router)
app.include_router(projects_router)
app.include_router(search_router)
app.include_router(faces_router)
app.include_router(gallery_router)
app.include_router(media_router)
app.include_router(bulk_media_router)
app.include_router(brand_router)
app.include_router(ui_router)


@app.get("/health")
def health():
    diagnostics = system_diagnostics()
    return {"status": "ok" if diagnostics["ready"] else "setup_required", "version": "0.7.0", "diagnostics": diagnostics}


@app.get("/")
def home():
    with SessionLocal() as session:
        users = session.scalar(select(func.count(User.id))) or 0
    return RedirectResponse("/login" if users else "/setup", status_code=307)
