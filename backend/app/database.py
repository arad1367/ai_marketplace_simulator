"""Supabase client factories.

Two clients are exposed:

* :func:`get_service_client` – authenticated with the service-role key. Used for
  trusted server-side reads/writes (inserting simulation logs, reading raw data
  for admin CSV export). Bypasses Row Level Security.
* :func:`get_anon_client` – authenticated with the public anon key. Used to
  verify end-user JWTs when checking admin access.

Clients are cached so we do not rebuild an HTTP session on every request.
"""

from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from .config import get_settings


class SupabaseNotConfiguredError(RuntimeError):
    """Raised when Supabase credentials are missing at runtime."""


@lru_cache
def get_service_client() -> Client:
    """Return a service-role Supabase client (bypasses RLS)."""
    settings = get_settings()
    if not settings.supabase_configured:
        raise SupabaseNotConfiguredError(
            "Supabase is not configured. Set SUPABASE_URL and "
            "SUPABASE_SERVICE_KEY in backend/.env."
        )
    return create_client(settings.supabase_url, settings.supabase_service_key)


@lru_cache
def get_anon_client() -> Client:
    """Return an anon-key Supabase client (used for JWT verification)."""
    settings = get_settings()
    if not (settings.supabase_url and settings.supabase_anon_key):
        raise SupabaseNotConfiguredError(
            "Supabase auth is not configured. Set SUPABASE_URL and "
            "SUPABASE_ANON_KEY in backend/.env."
        )
    return create_client(settings.supabase_url, settings.supabase_anon_key)
