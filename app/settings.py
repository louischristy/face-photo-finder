import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.branding import ACCENT_COLOR, APP_NAME, COMPANY_NAME, LOGO_URL, PRIMARY_COLOR
from app.models import SystemSetting

COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

DEFAULTS = {
    "branding.app_name": APP_NAME,
    "branding.company_name": COMPANY_NAME,
    "branding.primary_color": PRIMARY_COLOR,
    "branding.accent_color": ACCENT_COLOR,
    "branding.logo_url": LOGO_URL,
    "search.default_mode": "recommended",
    "gallery.default_dedup": "normal",
}


@dataclass(frozen=True)
class AppSettings:
    app_name: str
    company_name: str
    primary_color: str
    accent_color: str
    logo_url: str
    default_search_mode: str
    default_gallery_dedup: str


def get_values(session: Session) -> dict[str, str]:
    values = dict(DEFAULTS)
    for setting in session.scalars(select(SystemSetting)).all():
        if setting.key in values:
            values[setting.key] = setting.value
    return values


def get_app_settings(session: Session) -> AppSettings:
    values = get_values(session)
    return AppSettings(
        app_name=values["branding.app_name"],
        company_name=values["branding.company_name"],
        primary_color=values["branding.primary_color"],
        accent_color=values["branding.accent_color"],
        logo_url=values["branding.logo_url"],
        default_search_mode=values["search.default_mode"],
        default_gallery_dedup=values["gallery.default_dedup"],
    )


def validate_settings(values: dict[str, str]) -> dict[str, str]:
    cleaned = {key: str(value).strip() for key, value in values.items()}
    if not cleaned["branding.app_name"] or len(cleaned["branding.app_name"]) > 100:
        raise ValueError("Application name is required and must be at most 100 characters")
    if not cleaned["branding.company_name"] or len(cleaned["branding.company_name"]) > 150:
        raise ValueError("Company name is required and must be at most 150 characters")
    for key in ("branding.primary_color", "branding.accent_color"):
        if not COLOR_RE.fullmatch(cleaned[key]):
            raise ValueError("Brand colours must use six-digit hex values such as #285584")
    logo = cleaned["branding.logo_url"]
    if not logo or len(logo) > 500 or not (logo.startswith("/") or logo.startswith("https://")):
        raise ValueError("Logo URL must be a local /path or an https:// URL")
    if cleaned["search.default_mode"] not in {"strict", "recommended", "balanced", "broad"}:
        raise ValueError("Invalid default search mode")
    if cleaned["gallery.default_dedup"] not in {"conservative", "normal", "aggressive"}:
        raise ValueError("Invalid default gallery mode")
    return cleaned


def save_settings(session: Session, values: dict[str, str]) -> None:
    cleaned = validate_settings(values)
    for key, value in cleaned.items():
        setting = session.get(SystemSetting, key)
        if setting:
            setting.value = value
        else:
            session.add(SystemSetting(key=key, value=value))
    session.commit()
