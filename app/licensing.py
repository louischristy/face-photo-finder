import base64
import hashlib
import json
import os
import platform
import subprocess
import uuid
from dataclasses import dataclass
from datetime import date, datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.runtime import application_data_dir, resource_path

LICENCE_FILE = application_data_dir() / "licence.json"
PUBLIC_KEY_FILE = resource_path("resources", "licensing", "auroara-ed25519-public.key")
PRODUCT_ID = "auroara-face-photo-finder"


@dataclass(frozen=True)
class LicenceStatus:
    active: bool
    state: str
    message: str
    customer: str = ""
    licence_id: str = ""
    expires_on: str = ""


def _system_identifier() -> str:
    try:
        if platform.system() == "Darwin":
            output = subprocess.check_output(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"], text=True, timeout=3)
            marker = '"IOPlatformUUID" = "'
            if marker in output: return output.split(marker, 1)[1].split('"', 1)[0]
        if platform.system() == "Windows":
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                return str(winreg.QueryValueEx(key, "MachineGuid")[0])
    except Exception:
        pass
    return f"{platform.node()}|{uuid.getnode()}"


def machine_fingerprint() -> str:
    raw = f"{PRODUCT_ID}|{platform.system()}|{_system_identifier()}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def activation_request_code() -> str:
    payload = {"product": PRODUCT_ID, "machine": machine_fingerprint(), "platform": platform.system(), "version": 1}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()).decode().rstrip("=")
    return f"AFPF1-{encoded}"


def _canonical_payload(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def verify_licence_document(document: dict, public_key_bytes: bytes) -> LicenceStatus:
    payload=document.get("payload");signature_text=document.get("signature")
    if not isinstance(payload,dict) or not isinstance(signature_text,str): return LicenceStatus(False,"invalid","Licence document is malformed")
    try:
        public_key=Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_bytes.strip()));public_key.verify(base64.b64decode(signature_text),_canonical_payload(payload))
    except (ValueError,InvalidSignature,TypeError): return LicenceStatus(False,"invalid_signature","Licence signature is invalid")
    if payload.get("product")!=PRODUCT_ID: return LicenceStatus(False,"wrong_product","Licence is for a different product")
    if payload.get("machine")!=machine_fingerprint(): return LicenceStatus(False,"wrong_machine","Licence is bound to a different computer")
    expires=str(payload.get("expires_on") or "")
    if expires:
        try:
            if date.fromisoformat(expires)<datetime.utcnow().date(): return LicenceStatus(False,"expired","Licence has expired",str(payload.get("customer") or ""),str(payload.get("licence_id") or ""),expires)
        except ValueError: return LicenceStatus(False,"invalid","Licence expiry date is invalid")
    return LicenceStatus(True,"active","Licence is active",str(payload.get("customer") or ""),str(payload.get("licence_id") or ""),expires)


def licence_status() -> LicenceStatus:
    if os.getenv("AUROARA_DEV_BYPASS_LICENCE")=="1": return LicenceStatus(True,"development","Development licence bypass is active")
    if not LICENCE_FILE.exists(): return LicenceStatus(False,"not_activated","Product activation is required")
    if not PUBLIC_KEY_FILE.exists(): return LicenceStatus(False,"verification_unavailable","Licence verification key is not installed")
    try:
        document=json.loads(LICENCE_FILE.read_text(encoding="utf-8"));return verify_licence_document(document,PUBLIC_KEY_FILE.read_bytes())
    except (OSError,json.JSONDecodeError): return LicenceStatus(False,"invalid","Licence file could not be read")
