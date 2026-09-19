"""API-key authentication. Keys identify tenants; an open server hands out an anonymous tenant."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Header, HTTPException, Request

from tonedown_server.settings import Settings, Tenant


def make_auth_dependency(settings: Settings) -> Callable[..., Tenant]:
    async def dependency(
        request: Request,
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
        authorization: str | None = Header(default=None),
    ) -> Tenant:
        key = x_api_key
        if not key and authorization and authorization.lower().startswith("bearer "):
            key = authorization[7:].strip()
        if key:
            tenant = settings.tenant_for(key)
            if tenant is None:
                raise HTTPException(status_code=401, detail="Unknown API key")
            return tenant
        if settings.open_access:
            client = request.client.host if request.client else "unknown"
            return Tenant(name=f"anonymous:{client}", anonymous=True)
        raise HTTPException(status_code=401, detail="Missing API key (X-API-Key header)")

    return dependency
