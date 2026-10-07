from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.database import engine
from app.models import Base
from app.routes.accounts import router as accounts_router
from app.routes.projects import router as projects_router
from app.routes.search import router as search_router
from app.routes.ui import router as ui_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Face Photo Finder", version="0.4.0", lifespan=lifespan)
app.include_router(accounts_router)
app.include_router(projects_router)
app.include_router(search_router)
app.include_router(ui_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.4.0"}


@app.get("/")
def home():
    return RedirectResponse("/ui/projects", status_code=307)
