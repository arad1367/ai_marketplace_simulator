"""Application configuration loaded from environment variables.

Reads from a local ``.env`` file during development (see ``.env.example``) and
from the platform environment in production. All Supabase credentials are kept
server-side; only the anon key is ever shared with the browser.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Supabase ---
    supabase_url: str = ""
    # Public anon key (safe for the browser; used to verify user JWTs).
    supabase_anon_key: str = ""
    # Service-role key (server-only; bypasses RLS for trusted writes/reads).
    supabase_service_key: str = ""

    # --- CORS ---
    # Comma-separated list of allowed frontend origins.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- App ---
    app_env: str = "development"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def supabase_configured(self) -> bool:
        """True when the minimum credentials for DB access are present."""
        return bool(self.supabase_url and self.supabase_service_key)


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()
