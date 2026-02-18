"""Plex API client — fetches active playback sessions."""

import xml.etree.ElementTree as ET

import httpx

from config import settings
from models import Session


async def get_sessions() -> list[Session]:
    """Query Plex for currently-playing sessions."""
    if not settings.plex_enabled:
        return []

    url = f"{settings.plex_url.rstrip('/')}/status/sessions"
    headers = {
        "X-Plex-Token": settings.plex_token,
        "Accept": "application/xml",
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()

    root = ET.fromstring(resp.text)
    sessions: list[Session] = []

    for video in root.iter("Video"):
        # Resolve file path from the first Media > Part element
        part = video.find(".//Part")
        if part is None:
            continue
        media_path = part.get("file", "")
        if not media_path:
            continue

        # Build a human-readable title
        v_type = video.get("type", "")
        if v_type == "episode":
            show = video.get("grandparentTitle", "")
            season = video.get("parentIndex", "")
            ep = video.get("index", "")
            ep_title = video.get("title", "")
            title = f"{show}"
            subtitle = f"S{int(season):02d}E{int(ep):02d} — {ep_title}" if season and ep else ep_title
        else:
            title = video.get("title", "Unknown")
            subtitle = ""

        view_offset_ms = int(video.get("viewOffset", 0))
        duration_ms = int(video.get("duration", 0))
        session_el = video.find("Session")
        sid = session_el.get("id", "") if session_el is not None else video.get("sessionKey", "")

        # Thumbnail via proxy — token is added server-side, never sent to client
        thumb = video.get("thumb", "")
        thumb_url = ""
        if thumb:
            from urllib.parse import quote
            # Only include the path portion; the proxy adds auth + base URL
            upstream_path = (
                f"/photo/:/transcode"
                f"?width=400&height=225&minSize=1&url={thumb}"
            )
            thumb_url = f"/api/proxy/plex?path={quote(upstream_path, safe='')}"

        sessions.append(Session(
            session_id=f"plex-{sid}",
            source="plex",
            title=title,
            subtitle=subtitle,
            media_path=media_path,
            position_seconds=view_offset_ms / 1000.0,
            duration_seconds=duration_ms / 1000.0,
            thumbnail_url=thumb_url,
            year=int(video.get("year", 0)) or None,
        ))

    return sessions