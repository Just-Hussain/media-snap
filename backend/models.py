"""Pydantic models shared across the application."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ── Session models ──────────────────────────────────────────────

class Session(BaseModel):
    """Normalized playback session from Plex or Jellyfin."""
    session_id: str
    source: str  # "plex" | "jellyfin"
    title: str
    subtitle: str = ""  # e.g. "S02E05 - The One With..."
    media_path: str  # absolute path on the server filesystem
    position_seconds: float
    duration_seconds: float
    thumbnail_url: str = ""
    year: Optional[int] = None


# ── Capture models ──────────────────────────────────────────────

class ScreenshotRequest(BaseModel):
    session_id: str
    offset_seconds: float = 0.0  # tweak relative to current position


class ClipRequest(BaseModel):
    session_id: str
    # Either relative (e.g. -30 = last 30s) or absolute start/end
    relative_seconds: Optional[float] = None
    start_seconds: Optional[float] = None
    end_seconds: Optional[float] = None


class Capture(BaseModel):
    id: str
    source: str
    media_title: str
    timestamp_seconds: float
    capture_type: str
    file_name: str
    file_url: str
    file_size_bytes: int = 0
    duration_seconds: Optional[float] = None
    status: str
    error_message: Optional[str] = None
    created_at: str