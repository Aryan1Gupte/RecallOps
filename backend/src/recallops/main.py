"""FastAPI application entry point."""

from fastapi import FastAPI

from recallops.api.routes import health, incidents
from recallops.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name)
app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(incidents.router, prefix=settings.api_prefix)
