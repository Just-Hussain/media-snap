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

    Uses input-level seeking (-ss before -i) for near-instant keyframe seek,
    then decodes one frame from that point for an accurate result.
    """
    ts = _seconds_to_timecode(timestamp_seconds)

    cmd = [
        settings.ffmpeg_path,
        "-ss", ts,                     # seek to timestamp (input-level = fast)
        "-i", media_path,              # input file
        "-frames:v", "1",              # extract exactly 1 frame
        "-q:v", str(settings.screenshot_quality),  # JPEG quality
        "-y",                          # overwrite output
        output_path,
    ]

    logger.info("FFmpeg screenshot: %s @ %s -> %s", media_path, ts, output_path)
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
    precise: bool = False,
) -> None:
    """
    Extract a video clip from a media file.

    - precise=False (default): Uses stream copy (-c copy) for near-instant
      extraction. Cut points snap to nearest keyframes, so timing may be
      off by a few seconds.
    - precise=True: Re-encodes with libx264/aac for frame-accurate cuts.
      Slower but exact.
    """
    ts_start = _seconds_to_timecode(start_seconds)
    ts_dur = _seconds_to_timecode(duration_seconds)

    if precise:
        cmd = [
            settings.ffmpeg_path,
            "-ss", ts_start,
            "-i", media_path,
            "-t", ts_dur,
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "fast",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            "-y",
            output_path,
        ]
    else:
        cmd = [
            settings.ffmpeg_path,
            "-ss", ts_start,
            "-i", media_path,
            "-t", ts_dur,
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            "-movflags", "+faststart",
            "-y",
            output_path,
        ]

    logger.info(
        "FFmpeg clip (%s): %s @ %s for %s -> %s",
        "precise" if precise else "fast",
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