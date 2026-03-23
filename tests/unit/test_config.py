from memolite.common.config import get_settings, reset_settings_cache


def test_settings_read_environment(monkeypatch):
    monkeypatch.setenv("MEMOLITE_APP_NAME", "MemLite Test")
    monkeypatch.setenv("MEMOLITE_PORT", "9001")
    monkeypatch.setenv("MEMOLITE_EMBEDDER_PROVIDER", "hash")
    monkeypatch.setenv("MEMOLITE_EMBEDDER_MODEL", "local-demo")
    monkeypatch.setenv("MEMOLITE_EMBEDDER_CACHE_ENABLED", "false")
    monkeypatch.setenv("MEMOLITE_EMBEDDER_CACHE_SIZE", "321")
    monkeypatch.setenv("MEMOLITE_RERANKER_PROVIDER", "cross_encoder")
    monkeypatch.setenv("MEMOLITE_RERANKER_MODEL", "reranker-demo")
    reset_settings_cache()

    settings = get_settings()

    assert settings.app_name == "MemLite Test"
    assert settings.port == 9001
    assert settings.embedder_provider == "hash"
    assert settings.embedder_model == "local-demo"
    assert settings.embedder_cache_enabled is False
    assert settings.embedder_cache_size == 321
    assert settings.reranker_provider == "cross_encoder"
    assert settings.reranker_model == "reranker-demo"

    reset_settings_cache()
