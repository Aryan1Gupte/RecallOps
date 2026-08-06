from recallops.main import find_frontend_dist


def test_find_frontend_dist_uses_configured_build_directory(tmp_path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html>", encoding="utf-8")

    assert find_frontend_dist(str(dist), include_repo_default=False) == dist


def test_find_frontend_dist_ignores_incomplete_build_directory(tmp_path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()

    assert find_frontend_dist(str(dist), include_repo_default=False) is None
