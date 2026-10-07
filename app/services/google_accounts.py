import re
import secrets
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import StorageAccount
from app.services.google_drive import GoogleDriveClient


def _safe_token_name(label: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", label.strip()).strip("-").lower() or "google"
    return f"google-{slug}-{secrets.token_hex(4)}.json"


def connect_google_account(
    session: Session,
    label: str,
    credentials_path: Path = Path("credentials.json"),
    tokens_dir: Path = Path("data/tokens"),
) -> StorageAccount:
    """Authenticate one Google identity and register its private local token."""
    token_key = _safe_token_name(label)
    client = GoogleDriveClient(credentials_path, tokens_dir / token_key)
    identity = client.account_identity()
    account = StorageAccount(
        provider="google_drive",
        label=label.strip() or identity.get("emailAddress") or "Google Drive",
        account_hint=identity.get("emailAddress"),
        token_key=token_key,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account
