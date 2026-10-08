import base64

from fastapi import APIRouter
from fastapi.responses import Response

from app.branding import DEFAULT_LOGO_WEBP_BASE64

router = APIRouter(prefix="/ui/brand", tags=["brand"])


@router.get("/logo", include_in_schema=False)
def brand_logo():
    return Response(
        content=base64.b64decode(DEFAULT_LOGO_WEBP_BASE64),
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=86400"},
    )
