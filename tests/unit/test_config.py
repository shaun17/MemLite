from memlite.common.config import get_settings, reset_settings_cache


def test_settings_read_environment(monkeypatch):
    monkeypatch.setenv("MEMLITE_APP_NAME", "MemLite Test")
    monkeypatch.setenv("MEMLITE_PORT", "9001")
    reset_settings_cache()

    settings = get_settings()

    assert settings.app_name == "MemLite Test"
    assert settings.port == 9001

    reset_settings_cache()
