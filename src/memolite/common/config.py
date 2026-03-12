"""Configuration loading for MemoLite."""

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATA_DIR = Path.home() / ".memolite"
LEGACY_SQLITE_PATH = DEFAULT_DATA_DIR / "memlite.sqlite3"
DEFAULT_KUZU_PATH = DEFAULT_DATA_DIR / "kuzu"

LEGACY_ENV_PREFIX = "MEMLITE_"
ENV_PREFIX = "MEMOLITE_"


def _backfill_legacy_environment() -> None:
    """Map legacy MEMLITE_* variables into MEMOLITE_* when needed."""
    for key, value in tuple(os.environ.items()):
        if not key.startswith(LEGACY_ENV_PREFIX):
            continue
        new_key = f"{ENV_PREFIX}{key.removeprefix(LEGACY_ENV_PREFIX)}"
        os.environ.setdefault(new_key, value)


_backfill_legacy_environment()


def _resolve_default_sqlite_path() -> Path:
    """Prefer the new default DB path, with a fallback to the legacy one."""
    preferred_path = DEFAULT_DATA_DIR / "memolite.sqlite3"
    if preferred_path.exists():
        return preferred_path
    if LEGACY_SQLITE_PATH.exists():
        return LEGACY_SQLITE_PATH
    return preferred_path


DEFAULT_SQLITE_PATH = _resolve_default_sqlite_path()


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="MemoLite")
    environment: str = Field(default="development")
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=18731)
    log_level: str = Field(default="INFO")
    sqlite_path: Path = Field(default=DEFAULT_SQLITE_PATH)
    kuzu_path: Path = Field(default=DEFAULT_KUZU_PATH)
    sqlite_vec_extension_path: Path | None = Field(default=None)
    mcp_api_key: str | None = Field(default=None)
    semantic_search_candidate_multiplier: int = Field(default=3)
    semantic_search_max_candidates: int = Field(default=100)
    episodic_search_candidate_multiplier: int = Field(default=4)
    episodic_search_max_candidates: int = Field(default=100)

    @property
    def data_dir(self) -> Path:
        """Return the common data directory."""
        return self.sqlite_path.parent


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()


def reset_settings_cache() -> None:
    """Clear the cached settings for tests."""
    get_settings.cache_clear()
