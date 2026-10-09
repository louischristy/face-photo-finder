from fastapi import FastAPI

from app.routes.guest import router as guest_router

app = FastAPI(
    title="Auroara Event Guest Photo Search",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.include_router(guest_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "auroara-guest"}
