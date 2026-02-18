"""Jellyfin API client — fetches active playback sessions."""

import httpx

from config import settings
from models import Session

# Jellyfin returns PositionTicks in 100-nanosecond intervals
_TICKS_PER_SECOND = 10_000_000


async def get_sessions() -> list[Session]:
    """Query Jellyfin for currently-playing sessions."""
    if not settings.jellyfin_enabled:
        return []

    url = f"{settings.jellyfin_url.rstrip('/')}/Sessions"
    headers = {"X-Emby-Token": settings.jellyfin_api_key}

    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()

    data = resp.json()
    sessions: list[Session] = []

    for s in data:
        item = s.get("NowPlayingItem")
        play_state = s.get("PlayState", {})
        if not item or not play_state:
            continue

        # Resolve the file path (first MediaSource)
        sources = item.get("MediaSources", [])
        media_path = sources[0].get("Path", "") if sources else ""
        if not media_path:
            continue

        # Build title
        item_type = item.get("Type", "")
        if item_type == "Episode":
            title = item.get("SeriesName", "")
            season = item.get("ParentIndexNumber", 0)
            ep = item.get("IndexNumber", 0)
            ep_title = item.get("Name", "")
            subtitle = f"S{season:02d}E{ep:02d} — {ep_title}" if season and ep else ep_title
        else:
            title = item.get("Name", "Unknown")
            subtitle = ""

        position_ticks = play_state.get("PositionTicks", 0) or 0
        duration_ticks = item.get("RunTimeTicks", 0) or 0

        # Thumbnail via proxy to avoid exposing internal container IPs
        item_id = item.get("Id", "")
        thumb_url = ""
        if item_id:
            upstream = (
                f"{settings.jellyfin_url}/Items/{item_id}/Images/Primary"
                f"?maxWidth=400&quality=80&api_key={settings.jellyfin_api_key}"
            )
            from urllib.parse import quote
            thumb_url = f"/api/proxy/thumbnail?url={quote(upstream, safe='')}"

        sessions.append(Session(
            session_id=f"jf-{s.get('Id', '')}",
            source="jellyfin",
            title=title,
            subtitle=subtitle,
            media_path=media_path,
            position_seconds=position_ticks / _TICKS_PER_SECOND,
            duration_seconds=duration_ticks / _TICKS_PER_SECOND,
            thumbnail_url=thumb_url,
            year=item.get("ProductionYear"),
        ))

    return sessions