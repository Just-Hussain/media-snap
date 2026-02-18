"""Sessions router — lists active playback sessions."""

from fastapi import APIRouter, HTTPException

from models import Session
from services.session_manager import get_all_sessions

router = APIRouter(tags=["sessions"])


@router.get("/sessions", response_model=list[Session])
async def list_sessions():
    """Return all active playback sessions across Plex and Jellyfin."""
    try:
        return await get_all_sessions()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error fetching sessions: {e}")