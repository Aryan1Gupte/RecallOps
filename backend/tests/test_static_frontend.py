from fastapi.testclient import TestClient

from recallops.config import Settings
from recallops.main import build_app, find_frontend_dist


def make_settings(
    *,
    frontend_dist: str | None = None,
    enable_api_docs: bool = True,
) -> Settings:
    return Settings(
        app_name="RecallOps Test",
        app_env="test",
        api_prefix="/api",
        database_url=None,
        aws_region=None,
        bedrock_chat_model_id=None,
        bedrock_embedding_model_id=None,
        frontend_dist=frontend_dist,
        enable_api_docs=enable_api_docs,
        enable_ai_rate_limit=True,
        ai_rate_limit_requests=30,
        ai_rate_limit_window_seconds=60,
        trust_proxy_headers=False,
    )


def create_built_dist(tmp_path):
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text(
        "<!doctype html><title>RecallOps test bundle</title>",
        encoding="utf-8",
    )
    return dist


def test_find_frontend_dist_uses_configured_build_directory(tmp_path) -> None:
    dist = create_built_dist(tmp_path)

    assert find_frontend_dist(str(dist), include_repo_default=False) == dist.resolve()


def test_find_frontend_dist_ignores_incomplete_build_directory(tmp_path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()

    assert find_frontend_dist(str(dist), include_repo_default=False) is None


def test_source_like_frontend_directory_is_not_mounted(tmp_path) -> None:
    source_tree = tmp_path / "frontend"
    (source_tree / "src").mkdir(parents=True)
    (source_tree / "package.json").write_text("{}", encoding="utf-8")
    (source_tree / "index.html").write_text("<!doctype html>", encoding="utf-8")

    app = build_app(make_settings(frontend_dist=str(source_tree)))
    client = TestClient(app)

    assert find_frontend_dist(str(source_tree), include_repo_default=False) is None
    assert client.get("/").status_code == 404
    assert client.get("/package.json").status_code == 404
    assert client.get("/src/App.tsx").status_code == 404
    assert client.get("/api/health").status_code == 200


def test_build_app_serves_built_frontend_dist(tmp_path) -> None:
    dist = create_built_dist(tmp_path)
    app = build_app(make_settings(frontend_dist=str(dist)))
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "RecallOps test bundle" in response.text
    assert client.get("/api/health").status_code == 200


def test_build_app_can_disable_public_api_docs(tmp_path) -> None:
    dist = create_built_dist(tmp_path)
    app = build_app(
        make_settings(
            frontend_dist=str(dist),
            enable_api_docs=False,
        )
    )
    client = TestClient(app)

    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/api/health").status_code == 200
