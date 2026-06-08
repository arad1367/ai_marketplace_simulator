"""Authentication & authorization helpers.

Admin-gated endpoints require a valid Supabase access token (JWT) in the
``Authorization: Bearer <token>`` header. We verify the token against Supabase
Auth and then confirm ``profiles.is_admin = true`` for that user.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException, status

from .database import SupabaseNotConfiguredError, get_anon_client, get_service_client


@dataclass
class AuthenticatedUser:
    """A verified Supabase user plus their admin flag."""

    id: str
    email: Optional[str]
    is_admin: bool


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
        )
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must be 'Bearer <token>'.",
        )
    return parts[1].strip()


async def get_current_user(
    authorization: Optional[str] = Header(default=None),
) -> AuthenticatedUser:
    """Resolve and verify the current user from the bearer token."""
    token = _extract_bearer_token(authorization)

    try:
        anon = get_anon_client()
    except SupabaseNotConfiguredError as exc:  # pragma: no cover - config error
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    # Verify the JWT with Supabase Auth.
    try:
        user_response = anon.auth.get_user(token)
    except Exception as exc:  # noqa: BLE001 - supabase raises broad errors
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token.",
        ) from exc

    user = getattr(user_response, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token.",
        )

    # Look up the admin flag using the service client (bypasses RLS safely).
    is_admin = False
    try:
        service = get_service_client()
        profile = (
            service.table("profiles")
            .select("is_admin")
            .eq("id", user.id)
            .maybe_single()
            .execute()
        )
        if profile and profile.data:
            is_admin = bool(profile.data.get("is_admin", False))
    except Exception:  # noqa: BLE001 - missing profile => non-admin
        is_admin = False

    return AuthenticatedUser(id=user.id, email=user.email, is_admin=is_admin)


async def require_admin(
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """Dependency that rejects non-admin users with HTTP 403."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )
    return user
