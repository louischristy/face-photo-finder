from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Event, Lock, Thread
from typing import Any

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import Photo, PhotoSource
from app.services.face_engine import OpenCVFaceEngine
from app.services.face_indexer import index_google_photo, index_local_photo


@dataclass
class IndexJob:
    project_id: int
    source_ids: tuple[int, ...]
    status: str = "queued"
    total: int = 0
    completed: int = 0
    processed: int = 0
    faces: int = 0
    failed: int = 0
    current_photo: str = ""
    current_source: str = ""
    message: str = "Waiting to start"
    started_at: str | None = None
    finished_at: str | None = None


_lock = Lock()
_jobs: dict[int, IndexJob] = {}
_cancel: dict[int, Event] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _snapshot(job: IndexJob) -> dict[str, Any]:
    data = asdict(job)
    data["percent"] = round((job.completed / job.total * 100.0), 1) if job.total else 100.0
    data["running"] = job.status in {"queued", "running", "cancelling"}
    return data


def get_index_job(project_id: int) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(project_id)
        return _snapshot(job) if job else None


def cancel_index_job(project_id: int) -> bool:
    with _lock:
        job = _jobs.get(project_id)
        signal = _cancel.get(project_id)
        if not job or not signal or job.status not in {"queued", "running"}:
            return False
        job.status = "cancelling"
        job.message = "Cancellation requested. Finishing the current photo..."
        signal.set()
        return True


def start_index_job(project_id: int, source_ids: tuple[int, ...], detector_path, recognizer_path) -> dict[str, Any]:
    with _lock:
        existing = _jobs.get(project_id)
        if existing and existing.status in {"queued", "running", "cancelling"}:
            return _snapshot(existing)
        job = IndexJob(project_id=project_id, source_ids=source_ids)
        signal = Event()
        _jobs[project_id] = job
        _cancel[project_id] = signal

    thread = Thread(
        target=_run_index_job,
        args=(job, signal, detector_path, recognizer_path),
        name=f"face-index-{project_id}",
        daemon=True,
    )
    thread.start()
    return get_index_job(project_id) or _snapshot(job)


def _run_index_job(job: IndexJob, signal: Event, detector_path, recognizer_path) -> None:
    try:
        engine = OpenCVFaceEngine(detector_path, recognizer_path)
        with SessionLocal() as session:
            query = select(Photo).join(PhotoSource, Photo.source_id == PhotoSource.id).where(
                Photo.project_id == job.project_id,
                Photo.indexed.is_(False),
                PhotoSource.source_type.in_(("local_folder", "google_drive")),
            )
            if job.source_ids:
                query = query.where(Photo.source_id.in_(job.source_ids))
            photos = session.scalars(query.order_by(Photo.id)).all()
            with _lock:
                job.total = len(photos)
                job.status = "running"
                job.started_at = _now()
                job.message = "Indexing pending photos"

            for photo in photos:
                if signal.is_set():
                    with _lock:
                        job.status = "cancelled"
                        job.message = "Indexing cancelled"
                    break

                source = session.get(PhotoSource, photo.source_id)
                with _lock:
                    job.current_photo = photo.name or f"Photo {photo.id}"
                    job.current_source = (source.display_name or source.source_type) if source else "Unknown source"
                    job.message = "Detecting and indexing faces"

                try:
                    if source and source.source_type == "google_drive":
                        count = index_google_photo(session, photo, engine)
                    else:
                        count = index_local_photo(session, photo, engine)
                    with _lock:
                        job.processed += 1
                        job.faces += count
                except Exception:
                    session.rollback()
                    with _lock:
                        job.failed += 1
                finally:
                    with _lock:
                        job.completed += 1

            with _lock:
                if job.status != "cancelled":
                    job.status = "completed"
                    job.message = "Face indexing completed"
                job.current_photo = ""
                job.current_source = ""
                job.finished_at = _now()
    except Exception as exc:
        with _lock:
            job.status = "failed"
            job.message = f"Indexing job failed: {type(exc).__name__}"
            job.finished_at = _now()
