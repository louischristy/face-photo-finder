from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.database import engine
from app.models import Base
from app.routes.accounts import router as accounts_router
from app.routes.projects import router as projects_router
from app.routes.search import router as search_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Face Photo Finder", version="0.3.0", lifespan=lifespan)
app.include_router(accounts_router)
app.include_router(projects_router)
app.include_router(search_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.3.0"}


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """
    <!doctype html>
    <html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Face Photo Finder</title><style>
    body{font-family:system-ui,sans-serif;margin:0;background:#f5f7fa;color:#172033}main{max-width:1000px;margin:64px auto;padding:0 24px}.card{background:white;border-radius:20px;padding:34px;box-shadow:0 12px 40px rgba(0,0,0,.07)}.badge{display:inline-block;padding:7px 12px;border-radius:999px;background:#e8f7ee}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;margin-top:26px}.item{padding:20px;border:1px solid #e4e8ef;border-radius:15px}form{display:flex;gap:10px;margin-top:28px}input{flex:1;padding:12px 14px;border:1px solid #cfd6e2;border-radius:10px;font-size:16px}button,.link{padding:12px 18px;border:0;border-radius:10px;font-weight:650;cursor:pointer;text-decoration:none;background:#172033;color:white;display:inline-block}.actions{display:flex;gap:10px;margin-top:20px}
    </style></head><body><main><div class="card"><span class="badge">Local service running</span><h1>Face Photo Finder</h1>
    <p>Create a project, connect one or more Google accounts, attach Drive/local/external storage, scan the catalogue, then choose the project sources to search.</p>
    <div class="grid"><div class="item"><strong>Projects</strong><br>Separate events and collections</div><div class="item"><strong>Mixed Storage</strong><br>Multiple Google accounts + local/external drives</div><div class="item"><strong>Incremental Scan</strong><br>Catalogue new and changed photos</div><div class="item"><strong>Private Index</strong><br>Face processing remains local</div></div>
    <div class="actions"><a class="link" href="/accounts">Storage Accounts API</a><a class="link" href="/projects">Projects API</a></div>
    <form action="/projects" method="post"><input name="name" placeholder="New project name" required><button type="submit">Create Project</button></form>
    </div></main></body></html>"""
