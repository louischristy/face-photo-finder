import hashlib
import hmac

from fastapi import HTTPException, Request

from app.auth import SESSION_COOKIE

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
EXEMPT_PATHS = {"/login", "/setup"}


def csrf_token(session_token: str) -> str:
    return hmac.new(
        session_token.encode("utf-8"),
        b"auroara-face-photo-finder-csrf-v1",
        hashlib.sha256,
    ).hexdigest()


def csrf_token_for_request(request: Request) -> str:
    token = request.cookies.get(SESSION_COOKIE)
    return csrf_token(token) if token else ""


def _same_origin(request: Request) -> bool:
    expected = f"{request.url.scheme}://{request.url.netloc}"
    origin = request.headers.get("origin")
    if origin:
        return hmac.compare_digest(origin.rstrip("/"), expected.rstrip("/"))
    referer = request.headers.get("referer")
    if referer:
        return referer == expected or referer.startswith(expected.rstrip("/") + "/")
    return False


async def enforce_csrf(request: Request) -> None:
    """Protect authenticated mutations without reading the request body."""
    if request.method in SAFE_METHODS or request.url.path in EXEMPT_PATHS:
        return

    session_token = request.cookies.get(SESSION_COOKIE)
    if not session_token:
        return

    expected = csrf_token(session_token)
    supplied = request.headers.get("X-CSRF-Token", "")
    if supplied and hmac.compare_digest(supplied, expected):
        return

    content_type = request.headers.get("content-type", "").lower()
    browser_form = content_type.startswith("application/x-www-form-urlencoded") or content_type.startswith("multipart/form-data")
    if browser_form and _same_origin(request):
        return

    raise HTTPException(status_code=403, detail="Invalid or missing CSRF protection")
