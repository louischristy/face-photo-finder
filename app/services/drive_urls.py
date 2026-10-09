import re
from urllib.parse import parse_qs, urlparse

_FOLDER_PATH_RE = re.compile(r"/folders/([A-Za-z0-9_-]+)")


def extract_folder_id(value: str) -> str:
    """Extract a Google Drive folder ID from a folder URL or accept a bare ID."""
    value = value.strip()
    if not value:
        raise ValueError("Google Drive folder URL is required")

    match = _FOLDER_PATH_RE.search(value)
    if match:
        return match.group(1)

    parsed = urlparse(value)
    query_id = parse_qs(parsed.query).get("id")
    if query_id and query_id[0]:
        return query_id[0]

    if re.fullmatch(r"[A-Za-z0-9_-]{10,}", value):
        return value

    raise ValueError("Could not determine a Google Drive folder ID")
