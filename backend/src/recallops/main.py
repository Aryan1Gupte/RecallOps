"""FastAPI application entry point."""

from fastapi import APIRouter, FastAPI

from recallops.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name)
api_router = APIRouter(prefix=settings.api_prefix)


@api_router.get("/health")
def health() -> dict[str, str]:
    """Report whether the API process is ready to receive requests."""

    return {"status": "ok", "service": "recallops-api"}


app.include_router(api_router)
