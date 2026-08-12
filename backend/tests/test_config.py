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


def test_demo_rate_limit_defaults_and_proxy_header_safety(monkeypatch) -> None:
    monkeypatch.delenv("RECALL_OPS_AI_RATE_LIMIT_REQUESTS", raising=False)
    monkeypatch.delenv("RECALL_OPS_TRUST_PROXY_HEADERS", raising=False)
    get_settings.cache_clear()

    try:
        settings = get_settings()
        assert settings.ai_rate_limit_requests == 10
        assert settings.trust_proxy_headers is False
    finally:
        get_settings.cache_clear()
