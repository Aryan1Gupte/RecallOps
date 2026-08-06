"""FastAPI application entry point."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from recallops.api.routes import health, incidents, memories
from recallops.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name)
app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(incidents.router, prefix=settings.api_prefix)
app.include_router(memories.router, prefix=settings.api_prefix)


def find_frontend_dist(
    configured_dist: str | None = None,
    *,
    include_repo_default: bool = True,
) -> Path | None:
    """Find a built React bundle for same-origin serving when one is present."""

    candidates: list[Path] = []
    if configured_dist is not None and configured_dist.strip():
        candidates.append(Path(configured_dist).expanduser())

    if include_repo_default:
        candidates.append(Path(__file__).resolve().parents[3] / "frontend" / "dist")
    return next(
        (
            path
            for path in candidates
            if path.is_dir() and (path / "index.html").is_file()
        ),
        None,
    )


frontend_dist = find_frontend_dist(settings.frontend_dist)
if frontend_dist is not None:
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
