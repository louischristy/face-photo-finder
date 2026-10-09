import re
import secrets
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import StorageAccount
from app.runtime import application_data_dir, resource_path
from app.services.google_drive import GoogleDriveClient


def _safe_token_name(label: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", label.strip()).strip("-").lower() or "google"
    return f"google-{slug}-{secrets.token_hex(4)}.json"


def google_credentials_path() -> Path:
    local = application_data_dir() / "credentials.json"
    if local.exists():
        return local
    return resource_path("credentials.json")


def google_tokens_dir() -> Path:
    path = application_data_dir() / "tokens"
    path.mkdir(parents=True, exist_ok=True)
    return path


def connect_google_account(session: Session, label: str, credentials_path: Path | None = None, tokens_dir: Path | None = None) -> StorageAccount:
    """Authenticate one Google identity and register its private local token."""
    credentials_path = credentials_path or google_credentials_path()
    tokens_dir = tokens_dir or google_tokens_dir()
    token_key = _safe_token_name(label)
    client = GoogleDriveClient(credentials_path, tokens_dir / token_key)
    identity = client.account_identity()
    account = StorageAccount(provider="google_drive", label=label.strip() or identity.get("emailAddress") or "Google Drive", account_hint=identity.get("emailAddress"), token_key=token_key)
    session.add(account); session.commit(); session.refresh(account)
    return account
