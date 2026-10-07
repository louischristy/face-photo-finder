from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Photo, PhotoSource, StorageAccount
from app.services.google_drive import GoogleDriveClient
from app.services.local_storage import walk_local_images


def _upsert_photo(session: Session, source: PhotoSource, item: dict) -> tuple[Photo, bool]:
    key = item["source_item_key"]
    photo = session.scalar(
        select(Photo).where(Photo.source_id == source.id, Photo.source_item_key == key)
    )
    created = photo is None
    if created:
        photo = Photo(
            project_id=source.project_id,
            source_id=source.id,
            source_item_key=key,
            name=item["name"],
            mime_type=item["mime_type"],
        )
        session.add(photo)

    changed = created or photo.modified_time != item.get("modified_time")
    photo.name = item["name"]
    photo.mime_type = item["mime_type"]
    photo.modified_time = item.get("modified_time")
    photo.original_uri = item.get("original_uri")
    if changed:
        photo.indexed = False
        photo.face_count = 0
    return photo, created


def scan_local_source(session: Session, source: PhotoSource) -> dict[str, int]:
    seen: set[str] = set()
    created = updated = 0
    for item in walk_local_images(source.source_uri):
        seen.add(item["source_item_key"])
        existing = session.scalar(
            select(Photo).where(Photo.source_id == source.id, Photo.source_item_key == item["source_item_key"])
        )
        old_modified = existing.modified_time if existing else None
        _, was_created = _upsert_photo(session, source, item)
        created += int(was_created)
        updated += int(not was_created and old_modified != item.get("modified_time"))

    source.last_scanned_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.commit()
    return {"discovered": len(seen), "created": created, "updated": updated}


def scan_google_source(session: Session, source: PhotoSource, credentials_path: Path, tokens_dir: Path) -> dict[str, int]:
    account = session.get(StorageAccount, source.storage_account_id) if source.storage_account_id else None
    if not account or not account.token_key:
        raise ValueError("Google Drive source must be assigned to an authenticated Google account")

    client = GoogleDriveClient(credentials_path, tokens_dir / account.token_key)
    discovered = created = updated = 0
    for drive_item in client.walk_images(source.source_key):
        item = {
            "source_item_key": drive_item["id"],
            "name": drive_item["name"],
            "mime_type": drive_item["mimeType"],
            "modified_time": drive_item.get("modifiedTime"),
            "original_uri": drive_item.get("webViewLink"),
        }
        existing = session.scalar(
            select(Photo).where(Photo.source_id == source.id, Photo.source_item_key == item["source_item_key"])
        )
        old_modified = existing.modified_time if existing else None
        _, was_created = _upsert_photo(session, source, item)
        discovered += 1
        created += int(was_created)
        updated += int(not was_created and old_modified != item.get("modified_time"))

    source.last_scanned_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.commit()
    return {"discovered": discovered, "created": created, "updated": updated}


def scan_source(session: Session, source: PhotoSource, credentials_path: Path = Path("credentials.json"), tokens_dir: Path = Path("data/tokens")) -> dict[str, int]:
    if source.source_type == "local_folder":
        return scan_local_source(session, source)
    if source.source_type == "google_drive":
        tokens_dir.mkdir(parents=True, exist_ok=True)
        return scan_google_source(session, source, credentials_path, tokens_dir)
    raise ValueError(f"Unsupported source type: {source.source_type}")
