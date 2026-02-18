"""Unified session manager — merges Plex + Jellyfin sessions."""

import asyncio
import logging
from typing import Optional

from models import Session
from services import jellyfin, plex

logger = logging.getLogger(__name__)

# In-memory cache so we can look up a session by ID for captures
_session_cache: dict[str, Session] = {}


async def get_all_sessions() -> list[Session]:
    """Fetch sessions from all configured sources concurrently."""
    tasks = []
    tasks.append(plex.get_sessions())
    tasks.append(jellyfin.get_sessions())

    results = await asyncio.gather(*tasks, return_exceptions=True)
    sessions: list[Session] = []

    for result in results:
        if isinstance(result, Exception):
            logger.warning("Failed to fetch sessions: %s", result)
            continue
        sessions.extend(result)

    # Update cache
    _session_cache.clear()
    for s in sessions:
        _session_cache[s.session_id] = s

    return sessions


def get_cached_session(session_id: str) -> Optional[Session]:
    """Retrieve a session from the in-memory cache."""
    return _session_cache.get(session_id)