"""Proxy router — serves Plex/Jellyfin thumbnails to the browser.

Credentials are injected server-side so they never reach the client.
The client only sees paths like /api/proxy/plex?path=/photo/:/transcode?...
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
import httpx

from config import settings

router = APIRouter(tags=["proxy"])


async def _fetch(url: str, headers: dict | None = None) -> Response:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers or {})
            resp.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Failed to fetch thumbnail: {e}")

    return Response(
        content=resp.content,
        media_type=resp.headers.get("content-type", "image/jpeg"),
        headers={"Cache-Control": "public, max-age=10"},
    )


@router.get("/proxy/plex")
async def proxy_plex(path: str = Query(..., description="Plex path (no host, no token)")):
    """Proxy a Plex image request, injecting the token server-side."""
    if not settings.plex_enabled:
        raise HTTPException(404, "Plex is not configured")

    # Basic path validation — must start with /
    if not path.startswith("/"):
        raise HTTPException(400, "Invalid path")

    separator = "&" if "?" in path else "?"
    url = f"{settings.plex_url.rstrip('/')}{path}{separator}X-Plex-Token={settings.plex_token}"
    return await _fetch(url)


@router.get("/proxy/jellyfin")
async def proxy_jellyfin(path: str = Query(..., description="Jellyfin path (no host, no key)")):
    """Proxy a Jellyfin image request, injecting the API key server-side."""
    if not settings.jellyfin_enabled:
        raise HTTPException(404, "Jellyfin is not configured")

    if not path.startswith("/"):
        raise HTTPException(400, "Invalid path")

    separator = "&" if "?" in path else "?"
    url = f"{settings.jellyfin_url.rstrip('/')}{path}{separator}api_key={settings.jellyfin_api_key}"
    return await _fetch(url)