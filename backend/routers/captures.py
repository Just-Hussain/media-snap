"""Captures router — screenshot and clip creation, gallery, deletion."""

import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse

from config import settings
from database import get_db
from models import Capture, ClipRequest, ScreenshotRequest
from services.ffmpeg import extract_clip, extract_screenshot
from services.session_manager import get_cached_session

router = APIRouter(tags=["captures"])


def _build_capture_response(row) -> Capture:
    return Capture(
        id=row["id"],
        source=row["source"],
        media_title=row["media_title"],
        timestamp_seconds=row["timestamp_seconds"],
        capture_type=row["capture_type"],
        file_name=row["file_name"],
        file_url=f"/captures/{row['file_name']}",
        file_size_bytes=row["file_size_bytes"],
        duration_seconds=row["duration_seconds"],
        status=row["status"],
        error_message=row["error_message"],
        created_at=row["created_at"],
    )


# ── Screenshot ──────────────────────────────────────────────────

@router.post("/capture/screenshot", response_model=Capture)
async def take_screenshot(req: ScreenshotRequest):
    session = get_cached_session(req.session_id)
    if not session:
        raise HTTPException(404, "Session not found. Refresh the sessions list.")

    ts = max(0.0, session.position_seconds + req.offset_seconds)
    ts = min(ts, session.duration_seconds)

    capture_id = str(uuid.uuid4())
    file_name = f"{capture_id}.jpg"
    output_path = os.path.join(settings.capture_dir, file_name)
    now = datetime.now(timezone.utc).isoformat()

    # Synchronous-ish: screenshots are fast enough (<1s) to do inline
    try:
        await extract_screenshot(session.media_path, ts, output_path)
        file_size = os.path.getsize(output_path)
        status = "complete"
        error = None
    except Exception as e:
        file_size = 0
        status = "failed"
        error = str(e)

    # Persist to DB
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO captures
               (id, source, media_title, media_path, timestamp_seconds,
                capture_type, file_path, file_name, file_size_bytes,
                status, error_message, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                capture_id, session.source,
                f"{session.title} — {session.subtitle}".strip(" —"),
                session.media_path, ts,
                "screenshot", output_path, file_name, file_size,
                status, error, now,
            ),
        )
        await db.commit()
    finally:
        await db.close()

    if status == "failed":
        raise HTTPException(500, f"Screenshot failed: {error}")

    return Capture(
        id=capture_id,
        source=session.source,
        media_title=f"{session.title} — {session.subtitle}".strip(" —"),
        timestamp_seconds=ts,
        capture_type="screenshot",
        file_name=file_name,
        file_url=f"/captures/{file_name}",
        file_size_bytes=file_size,
        status=status,
        created_at=now,
    )


# ── Clip (Phase 2) ─────────────────────────────────────────────

async def _process_clip(
    capture_id: str, media_path: str, start: float,
    duration: float, output_path: str,
):
    """Background task for clip extraction."""
    db = await get_db()
    try:
        await extract_clip(media_path, start, duration, output_path)
        file_size = os.path.getsize(output_path)
        await db.execute(
            "UPDATE captures SET status='complete', file_size_bytes=? WHERE id=?",
            (file_size, capture_id),
        )
    except Exception as e:
        await db.execute(
            "UPDATE captures SET status='failed', error_message=? WHERE id=?",
            (str(e), capture_id),
        )
    finally:
        await db.commit()
        await db.close()


@router.post("/capture/clip", response_model=Capture)
async def take_clip(req: ClipRequest, bg: BackgroundTasks):
    session = get_cached_session(req.session_id)
    if not session:
        raise HTTPException(404, "Session not found. Refresh the sessions list.")

    # Resolve start/end
    if req.relative_seconds is not None:
        start = max(0.0, session.position_seconds + req.relative_seconds)
        end = session.position_seconds
        if start > end:
            start, end = end, start
    elif req.start_seconds is not None and req.end_seconds is not None:
        start = max(0.0, req.start_seconds)
        end = min(req.end_seconds, session.duration_seconds)
    else:
        raise HTTPException(400, "Provide relative_seconds or start_seconds + end_seconds")

    duration = end - start
    if duration <= 0:
        raise HTTPException(400, "Clip duration must be positive")
    if duration > 600:
        raise HTTPException(400, "Maximum clip duration is 10 minutes")

    capture_id = str(uuid.uuid4())
    file_name = f"{capture_id}.mp4"
    output_path = os.path.join(settings.capture_dir, file_name)
    now = datetime.now(timezone.utc).isoformat()

    # Insert as pending, process in background
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO captures
               (id, source, media_title, media_path, timestamp_seconds,
                capture_type, file_path, file_name, file_size_bytes,
                duration_seconds, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 'pending', ?)""",
            (
                capture_id, session.source,
                f"{session.title} — {session.subtitle}".strip(" —"),
                session.media_path, start,
                "clip", output_path, file_name,
                duration, now,
            ),
        )
        await db.commit()
    finally:
        await db.close()

    bg.add_task(
        _process_clip, capture_id, session.media_path,
        start, duration, output_path,
    )

    return Capture(
        id=capture_id,
        source=session.source,
        media_title=f"{session.title} — {session.subtitle}".strip(" —"),
        timestamp_seconds=start,
        capture_type="clip",
        file_name=file_name,
        file_url=f"/captures/{file_name}",
        duration_seconds=duration,
        status="pending",
        created_at=now,
    )


# ── Gallery & Management ────────────────────────────────────────

@router.get("/captures", response_model=list[Capture])
async def list_captures(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    capture_type: str = Query(None),
):
    db = await get_db()
    try:
        q = "SELECT * FROM captures"
        params: list = []
        if capture_type:
            q += " WHERE capture_type = ?"
            params.append(capture_type)
        q += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cursor = await db.execute(q, params)
        rows = await cursor.fetchall()
    finally:
        await db.close()

    return [_build_capture_response(r) for r in rows]


@router.get("/captures/{capture_id}", response_model=Capture)
async def get_capture(capture_id: str):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM captures WHERE id = ?", (capture_id,))
        row = await cursor.fetchone()
    finally:
        await db.close()
    if not row:
        raise HTTPException(404, "Capture not found")
    return _build_capture_response(row)


@router.get("/captures/{capture_id}/file")
async def download_capture(capture_id: str):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM captures WHERE id = ?", (capture_id,))
        row = await cursor.fetchone()
    finally:
        await db.close()
    if not row:
        raise HTTPException(404, "Capture not found")
    if row["status"] != "complete":
        raise HTTPException(409, f"Capture status is '{row['status']}'")
    return FileResponse(row["file_path"], filename=row["file_name"])


@router.delete("/captures/{capture_id}")
async def delete_capture(capture_id: str):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM captures WHERE id = ?", (capture_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(404, "Capture not found")

        # Delete file from disk
        try:
            os.remove(row["file_path"])
        except FileNotFoundError:
            pass

        await db.execute("DELETE FROM captures WHERE id = ?", (capture_id,))
        await db.commit()
    finally:
        await db.close()

    return {"deleted": capture_id}