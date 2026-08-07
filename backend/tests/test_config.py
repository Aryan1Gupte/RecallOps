from recallops.config import get_settings


def test_production_settings_disable_public_api_docs_by_default(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("RECALL_OPS_ENABLE_API_DOCS", raising=False)
    get_settings.cache_clear()

    try:
        assert get_settings().enable_api_docs is False
    finally:
        get_settings.cache_clear()


def test_public_api_docs_can_be_explicitly_enabled(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("RECALL_OPS_ENABLE_API_DOCS", "true")
    get_settings.cache_clear()

    try:
        assert get_settings().enable_api_docs is True
    finally:
        get_settings.cache_clear()
