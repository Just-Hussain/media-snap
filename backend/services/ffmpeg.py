"""FFmpeg wrapper for screenshot and clip extraction."""

import asyncio
import logging
import os
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)


def _seconds_to_timecode(seconds: float) -> str:
    """Convert seconds to HH:MM:SS.mmm timecode."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


async def extract_screenshot(
    media_path: str,
    timestamp_seconds: float,
    output_path: str,
) -> None:
    """
    Extract a single frame from a media file at the given timestamp.

    Uses a two-pass seek for frame-accurate extraction:
    1. Coarse input-level seek (-ss before -i) with -noaccurate_seek to jump
       to the nearest keyframe ~5s before the target (fast demuxer seek).
    2. Fine output-level seek (-ss after -i) to decode forward to the exact
       frame using PTS ordering, avoiding B-frame reordering inaccuracies.
    """
    SEEK_BUFFER = 5.0
    coarse = max(0.0, timestamp_seconds - SEEK_BUFFER)
    fine = timestamp_seconds - coarse

    ts_coarse = _seconds_to_timecode(coarse)
    ts_fine = _seconds_to_timecode(fine)

    cmd = [
        settings.ffmpeg_path,
        "-noaccurate_seek",            # keyframe-only jump (skip DTS decode-forward)
        "-ss", ts_coarse,              # coarse: land near target
        "-i", media_path,              # input file
        "-ss", ts_fine,                # fine: decode to exact frame via PTS
        "-frames:v", "1",              # extract exactly 1 frame
        "-q:v", str(settings.screenshot_quality),  # JPEG quality
        "-y",                          # overwrite output
        output_path,
    ]

    logger.info("FFmpeg screenshot: %s @ coarse=%s fine=%s -> %s", media_path, ts_coarse, ts_fine, output_path)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        err = stderr.decode().strip()
        logger.error("FFmpeg failed (code %d): %s", proc.returncode, err)
        raise RuntimeError(f"FFmpeg failed: {err}")

    if not os.path.exists(output_path):
        raise RuntimeError("FFmpeg produced no output file")


async def extract_clip(
    media_path: str,
    start_seconds: float,
    duration_seconds: float,
    output_path: str,
) -> None:
    """
    Extract a video clip from a media file using stream copy.

    Uses -c copy for near-instant extraction. Cut points snap to nearest
    keyframes, so timing may be off by a few seconds.
    """
    ts_start = _seconds_to_timecode(start_seconds)
    ts_dur = _seconds_to_timecode(duration_seconds)

    cmd = [
        settings.ffmpeg_path,
        "-ss", ts_start,
        "-i", media_path,
        "-t", ts_dur,
        "-c:v", "copy",
        "-c:a", "aac",
        "-ac", "2",
        "-b:a", "192k",
        "-avoid_negative_ts", "make_zero",
        "-movflags", "+faststart",
        "-y",
        output_path,
    ]

    logger.info(
        "FFmpeg clip: %s @ %s for %s -> %s",
        media_path, ts_start, ts_dur, output_path,
    )
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        err = stderr.decode().strip()
        logger.error("FFmpeg failed (code %d): %s", proc.returncode, err)
        raise RuntimeError(f"FFmpeg failed: {err}")

    if not os.path.exists(output_path):
        raise RuntimeError("FFmpeg produced no output file")