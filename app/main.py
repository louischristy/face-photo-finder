from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine

from app.models import Base

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DATABASE_URL = f"sqlite:///{DATA_DIR / 'face_photo_finder.sqlite3'}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Face Photo Finder", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Face Photo Finder</title>
        <style>
          body { font-family: system-ui, sans-serif; margin: 0; background:#f6f7f9; color:#172033; }
          main { max-width: 920px; margin: 70px auto; padding: 0 24px; }
          .card { background:white; border-radius:18px; padding:32px; box-shadow:0 10px 35px rgba(0,0,0,.08); }
          h1 { margin-top:0; }
          .badge { display:inline-block; padding:7px 11px; border-radius:999px; background:#e9f8ee; }
          .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:14px; margin-top:24px; }
          .item { padding:18px; border:1px solid #e5e7eb; border-radius:14px; }
        </style>
      </head>
      <body><main><div class="card">
        <span class="badge">Local service running</span>
        <h1>Face Photo Finder</h1>
        <p>Private, project-based Google Drive photo discovery and face-search application.</p>
        <div class="grid">
          <div class="item"><strong>Projects</strong><br>Isolated photo collections</div>
          <div class="item"><strong>Drive Sources</strong><br>Multiple folders per project</div>
          <div class="item"><strong>Local Index</strong><br>Private on-device processing</div>
          <div class="item"><strong>Downloads</strong><br>Originals and ZIP bundles</div>
        </div>
      </div></main></body>
    </html>
    """
