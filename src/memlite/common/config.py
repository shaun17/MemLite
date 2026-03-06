"""Configuration loading for MemLite."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATA_DIR = Path.home() / ".memlite"
DEFAULT_SQLITE_PATH = DEFAULT_DATA_DIR / "memlite.sqlite3"
DEFAULT_KUZU_PATH = DEFAULT_DATA_DIR / "kuzu"


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="MEMLITE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="MemLite")
    environment: str = Field(default="development")
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8080)
    log_level: str = Field(default="INFO")
    sqlite_path: Path = Field(default=DEFAULT_SQLITE_PATH)
    kuzu_path: Path = Field(default=DEFAULT_KUZU_PATH)
    sqlite_vec_extension_path: Path | None = Field(default=None)

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
