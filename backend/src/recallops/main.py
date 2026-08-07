"""FastAPI application entry point."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from recallops.api.routes import health, incidents, memories
from recallops.config import Settings, get_settings

SOURCE_TREE_MARKERS = ("package.json", "vite.config.ts", "vite.config.js", "src")


def find_frontend_dist(
    configured_dist: str | None = None,
    *,
    include_repo_default: bool = True,
) -> Path | None:
    """Find a built React bundle for same-origin serving when one is present."""

    if configured_dist is not None and configured_dist.strip():
        configured_path = Path(configured_dist).expanduser().resolve()
        return configured_path if _is_safe_frontend_dist(configured_path) else None

    if include_repo_default:
        repo_dist = Path(__file__).resolve().parents[3] / "frontend" / "dist"
        return repo_dist if _is_safe_frontend_dist(repo_dist) else None
    return None


def build_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI app so deployment-sensitive settings are testable."""

    resolved_settings = settings or get_settings()
    app = FastAPI(
        title=resolved_settings.app_name,
        docs_url="/docs" if resolved_settings.enable_api_docs else None,
        redoc_url="/redoc" if resolved_settings.enable_api_docs else None,
        openapi_url="/openapi.json" if resolved_settings.enable_api_docs else None,
    )
    app.include_router(health.router, prefix=resolved_settings.api_prefix)
    app.include_router(incidents.router, prefix=resolved_settings.api_prefix)
    app.include_router(memories.router, prefix=resolved_settings.api_prefix)

    frontend_dist = find_frontend_dist(resolved_settings.frontend_dist)
    if frontend_dist is not None:
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    return app


def _is_safe_frontend_dist(path: Path) -> bool:
    """Accept only built Vite dist output, never the frontend source tree."""

    if not path.is_dir():
        return False
    if path.name != "dist":
        return False
    if not (path / "index.html").is_file():
        return False
    if not (path / "assets").is_dir():
        return False
    return not any((path / marker).exists() for marker in SOURCE_TREE_MARKERS)


settings = get_settings()
app = build_app(settings)
