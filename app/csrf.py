import hashlib
import hmac

from fastapi import HTTPException, Request

from app.auth import SESSION_COOKIE

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
EXEMPT_PATHS = {"/login", "/setup"}


def csrf_token(session_token: str) -> str:
    return hmac.new(session_token.encode("utf-8"), b"auroara-face-photo-finder-csrf-v1", hashlib.sha256).hexdigest()


def csrf_token_for_request(request: Request) -> str:
    token = request.cookies.get(SESSION_COOKIE)
    return csrf_token(token) if token else ""


async def enforce_csrf(request: Request) -> None:
    if request.method in SAFE_METHODS or request.url.path in EXEMPT_PATHS:
        return
    session_token = request.cookies.get(SESSION_COOKIE)
    if not session_token:
        return
    supplied = request.headers.get("X-CSRF-Token", "")
    if not supplied:
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("application/x-www-form-urlencoded") or content_type.startswith("multipart/form-data"):
            form = await request.form()
            supplied = str(form.get("csrf_token", ""))
    expected = csrf_token(session_token)
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
