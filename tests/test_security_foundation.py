import asyncio
import base64
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from starlette.requests import Request

from app import licensing
from app.auth import SESSION_COOKIE
from app.csrf import csrf_token, enforce_csrf


def _request(method="POST", content_type="application/x-www-form-urlencoded", origin=None, csrf=None):
    headers = [(b"content-type", content_type.encode()), (b"cookie", f"{SESSION_COOKIE}=session-secret".encode())]
    if origin:
        headers.append((b"origin", origin.encode()))
    if csrf:
        headers.append((b"x-csrf-token", csrf.encode()))
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": "/ui/settings",
        "raw_path": b"/ui/settings",
        "query_string": b"",
        "headers": headers,
        "server": ("127.0.0.1", 8765),
        "client": ("127.0.0.1", 50000),
    }
    return Request(scope)


def test_csrf_accepts_same_origin_form_without_reading_body():
    request = _request(origin="http://127.0.0.1:8765")
    asyncio.run(enforce_csrf(request))
    assert not hasattr(request, "_form")


def test_csrf_accepts_session_bound_header():
    request = _request(content_type="application/json", csrf=csrf_token("session-secret"))
    asyncio.run(enforce_csrf(request))


def test_csrf_rejects_cross_origin_form():
    request = _request(origin="https://example.invalid")
    try:
        asyncio.run(enforce_csrf(request))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
    else:
        raise AssertionError("cross-origin authenticated form was accepted")


def test_signed_licence_verification(monkeypatch):
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    monkeypatch.setattr(licensing, "machine_fingerprint", lambda: "machine-123")
    payload = {
        "product": licensing.PRODUCT_ID,
        "machine": "machine-123",
        "customer": "Test Customer",
        "licence_id": "TEST-001",
        "expires_on": "2099-12-31",
    }
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    document = {"payload": payload, "signature": base64.b64encode(private_key.sign(canonical)).decode()}
    status = licensing.verify_licence_document(document, base64.b64encode(public_key))
    assert status.active
    assert status.customer == "Test Customer"


def test_licence_rejects_malformed_base64(monkeypatch):
    monkeypatch.setattr(licensing, "machine_fingerprint", lambda: "machine-123")
    status = licensing.verify_licence_document({"payload": {}, "signature": "not base64!"}, b"not base64!")
    assert not status.active
    assert status.state == "invalid_signature"
