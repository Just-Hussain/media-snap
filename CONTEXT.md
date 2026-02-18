# MediaSnap — Project Context

## What is this?

MediaSnap is a self-hosted web tool that runs alongside Plex and Jellyfin on a home server. It detects active playback sessions, and lets the user capture screenshots or video clips from the source media file via a web UI. The primary use case is: "I'm watching something on my TV/console and want to screenshot or clip a moment to share with friends, but I can't easily do that from the playback device."

## How it works (high level)

1. The backend polls the Plex and Jellyfin APIs every few seconds to discover what's currently playing.
2. The web UI shows active sessions with "Screenshot" and "Clip" buttons.
3. On capture, the backend resolves the media file's absolute path on disk (reported by the media server API), calculates the playback timestamp, and invokes FFmpeg directly on the source file.
4. The result is saved to a local captures directory and tracked in a SQLite database.
5. The user can browse, download, and delete captures from a gallery view.

The critical architectural insight is that MediaSnap runs on the same machine as the media servers, so it has direct filesystem access to the source media files via a shared volume mount. FFmpeg operates on the source files — no transcoding stream capture, no network overhead, full quality output.

## Tech stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Python 3.12+, FastAPI, uvicorn | Async, simple, good for orchestrating shell commands and HTTP calls |
| Database | SQLite via aiosqlite | Zero-config, single-user tool, no external DB needed |
| Media processing | FFmpeg (system binary) | Industry standard, called via `asyncio.create_subprocess_exec` |
| Frontend | React 19, TypeScript, Vite 6 | Lightweight SPA, Vite for fast dev/build |
| Config | pydantic-settings, env vars / `.env` | Type-safe config from environment |
| HTTP client | httpx (async) | For calling Plex/Jellyfin APIs |
| Containerization | Docker, multi-stage Dockerfile, docker-compose | Single container: builds frontend, installs FFmpeg + Python deps |

No ORM is used. SQL is written directly with parameterized queries via aiosqlite. No CSS framework is used — styles are inline React styles. No state management library — just React useState/useEffect.

## Project structure

```
mediasnap/
├── CONTEXT.md               # This file
├── README.md                # User-facing setup & usage docs
├── docker-compose.yml       # Production deployment
├── Dockerfile               # Multi-stage: frontend build + Python runtime + FFmpeg
├── backend/
│   ├── main.py              # FastAPI app, lifespan, middleware, static mounts
│   ├── config.py            # Settings class (pydantic-settings), reads env vars
│   ├── database.py          # SQLite schema, init_db(), get_db()
│   ├── models.py            # Pydantic models: Session, Capture, ScreenshotRequest, ClipRequest
│   ├── requirements.txt     # Python dependencies
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── sessions.py      # GET /api/sessions
│   │   ├── captures.py      # POST screenshot/clip, GET gallery, GET/DELETE individual captures
│   │   └── proxy.py         # GET /api/proxy/plex, GET /api/proxy/jellyfin (thumbnail proxy)
│   └── services/
│       ├── __init__.py
│       ├── plex.py          # Plex API client (XML parsing)
│       ├── jellyfin.py      # Jellyfin API client (JSON)
│       ├── session_manager.py  # Merges sources, maintains in-memory session cache
│       └── ffmpeg.py        # FFmpeg command builder + async subprocess executor
├── frontend/
│   ├── index.html           # Vite entry HTML
│   ├── package.json
│   ├── vite.config.ts       # Dev server proxy: /api and /captures -> :8787
│   ├── tsconfig.json
│   └── src/
│       ├── main.tsx          # React DOM createRoot
│       ├── App.tsx           # Main component: tabs, session cards, gallery
│       └── api.ts            # Typed fetch wrapper + all API call functions
└── data/                     # Runtime directory (gitignored)
    ├── captures/             # Screenshot JPEGs and clip MP4s
    └── mediasnap.db          # SQLite database
```

## API endpoints

| Method | Path | Purpose | Status |
|--------|------|---------|--------|
| GET | `/api/health` | Health check | Done |
| GET | `/api/sessions` | List active playback sessions (Plex + Jellyfin merged) | Done |
| POST | `/api/capture/screenshot` | Take screenshot of a session at current timestamp | Done |
| POST | `/api/capture/clip` | Extract video clip (runs as background task) | Done |
| GET | `/api/captures` | List all captures (paginated, filterable by type) | Done |
| GET | `/api/captures/{id}` | Get single capture metadata | Done |
| GET | `/api/captures/{id}/file` | Download capture file | Done |
| DELETE | `/api/captures/{id}` | Delete capture + file from disk | Done |
| GET | `/api/proxy/plex` | Proxy Plex thumbnails (injects token server-side) | Done |
| GET | `/api/proxy/jellyfin` | Proxy Jellyfin thumbnails (injects API key server-side) | Done |

### Request/response shapes

**GET /api/sessions** returns:
```json
[{
  "session_id": "plex-abc123",
  "source": "plex",
  "title": "Breaking Bad",
  "subtitle": "S05E14 — Ozymandias",
  "media_path": "/media/TV/Breaking Bad/Season 5/episode.mkv",
  "position_seconds": 1832.5,
  "duration_seconds": 2874.0,
  "thumbnail_url": "/api/proxy/plex?path=%2Fphoto%2F%3A%2Ftranscode%3Fwidth%3D400%26height%3D225%26minSize%3D1%26url%3D%2Flibrary%2Fmetadata%2F12158%2Fthumb%2F1771299229",
  "year": 2013
}]
```
Note: `thumbnail_url` is always a relative proxy path. Credentials are never exposed to the client.

**POST /api/capture/screenshot** expects:
```json
{ "session_id": "plex-abc123", "offset_seconds": 0.0 }
```
`offset_seconds` is relative to the current playback position (e.g., -5.0 to go back 5 seconds).

**POST /api/capture/clip** expects one of:
```json
{ "session_id": "plex-abc123", "relative_seconds": -30, "precise": false }
{ "session_id": "plex-abc123", "start_seconds": 100, "end_seconds": 130, "precise": true }
```
`relative_seconds` is negative to mean "last N seconds from current position". `precise: true` re-encodes for frame-accurate cuts (slower); `false` uses stream copy (fast, keyframe-snapped).

**Capture response shape** (returned by all capture endpoints and gallery):
```json
{
  "id": "uuid",
  "source": "plex",
  "media_title": "Breaking Bad — S05E14 — Ozymandias",
  "timestamp_seconds": 1832.5,
  "capture_type": "screenshot",
  "file_name": "uuid.jpg",
  "file_url": "/captures/uuid.jpg",
  "file_size_bytes": 245000,
  "duration_seconds": null,
  "status": "complete",
  "error_message": null,
  "created_at": "2026-02-18T12:00:00+00:00"
}
```

**GET /api/proxy/plex?path={url-encoded-path}** — Proxies a thumbnail from Plex. The `path` parameter is a Plex path without the host or token (e.g., `/photo/:/transcode?width=400&height=225&minSize=1&url=/library/metadata/12158/thumb/1771299229`). The proxy prepends `PLEX_URL` and appends `X-Plex-Token` server-side. Returns the image bytes with `Cache-Control: public, max-age=86400`.

**GET /api/proxy/jellyfin?path={url-encoded-path}** — Same pattern for Jellyfin. Path is e.g. `/Items/{id}/Images/Primary?maxWidth=400&quality=80`. The proxy prepends `JELLYFIN_URL` and appends `api_key` server-side.

## External API details

### Plex

- **Sessions endpoint:** `GET {PLEX_URL}/status/sessions` with header `X-Plex-Token: {token}`
- Returns XML. Active playback items are `<Video>` elements under `<MediaContainer>`.
- File path: `video.find(".//Part").get("file")`
- Position: `viewOffset` attribute in milliseconds
- Duration: `duration` attribute in milliseconds
- Session ID: `<Session>` child element's `id` attribute, or `sessionKey` on the `<Video>`
- For episodes: `grandparentTitle` (show), `parentIndex` (season), `index` (episode), `title` (episode name)
- Thumbnail: `thumb` attribute — a Plex-internal path like `/library/metadata/12158/thumb/1771299229`. Served via the image transcoder at `/photo/:/transcode?width=400&height=225&url={thumb}`. Token is required but injected by the proxy, not included in client-facing URLs.

### Jellyfin

- **Sessions endpoint:** `GET {JELLYFIN_URL}/Sessions` with header `X-Emby-Token: {api_key}`
- Returns JSON array. Active playback has `NowPlayingItem` and `PlayState` objects.
- File path: `NowPlayingItem.MediaSources[0].Path`
- Position: `PlayState.PositionTicks` in 100-nanosecond units (divide by 10,000,000 for seconds)
- Duration: `NowPlayingItem.RunTimeTicks` (same unit)
- For episodes: `SeriesName`, `ParentIndexNumber` (season), `IndexNumber` (episode), `Name` (episode title)
- Thumbnail: `/Items/{ItemId}/Images/Primary?maxWidth=400&quality=80`. API key is required but injected by the proxy.

### Session normalization

Both sources are normalized into the `Session` pydantic model. Session IDs are prefixed with `plex-` or `jf-` to avoid collisions. The session manager merges results from both sources concurrently via `asyncio.gather` and caches them in-memory so the capture endpoints can look up a session by ID without re-polling.

## Thumbnail proxy architecture

Plex and Jellyfin may run on internal Docker IPs (e.g., `172.17.0.1`) that are unreachable from the user's browser. Additionally, thumbnail URLs would otherwise expose the Plex token or Jellyfin API key to the client.

The solution is a server-side proxy with two endpoints (`/api/proxy/plex` and `/api/proxy/jellyfin`). The services build thumbnail URLs as relative proxy paths containing only the media server's internal path — no host, no credentials. When the browser requests the thumbnail, the proxy endpoint reconstructs the full upstream URL by prepending the configured server URL and appending the authentication token/key. The proxy also validates that the path starts with `/` and only proxies to configured origins.

This means:
- No internal IPs are exposed to the client.
- No Plex tokens or Jellyfin API keys appear in API responses, network requests, or browser dev tools.
- Thumbnails are cached for 24 hours via `Cache-Control: public, max-age=86400`.

## FFmpeg commands

**Screenshot** (< 1 second):
```bash
ffmpeg -ss {HH:MM:SS.mmm} -i {media_path} -frames:v 1 -q:v 2 -y {output}.jpg
```
`-ss` before `-i` = input-level seeking (fast keyframe seek). `-q:v 2` = high quality JPEG.

**Clip — fast mode** (stream copy, near-instant, keyframe-snapped):
```bash
ffmpeg -ss {start} -i {media_path} -t {duration} -c copy -avoid_negative_ts make_zero -movflags +faststart -y {output}.mp4
```

**Clip — precise mode** (re-encode, slower, frame-accurate):
```bash
ffmpeg -ss {start} -i {media_path} -t {duration} -c:v libx264 -crf 18 -preset fast -c:a aac -b:a 192k -movflags +faststart -y {output}.mp4
```

All FFmpeg calls use `asyncio.create_subprocess_exec` to avoid blocking the event loop. stderr is captured for error reporting.

## Database schema

Single table, SQLite:
```sql
CREATE TABLE IF NOT EXISTS captures (
    id TEXT PRIMARY KEY,              -- UUID
    source TEXT NOT NULL,             -- 'plex' or 'jellyfin'
    media_title TEXT NOT NULL,
    media_path TEXT NOT NULL,
    timestamp_seconds REAL NOT NULL,
    capture_type TEXT NOT NULL,       -- 'screenshot' or 'clip'
    file_path TEXT NOT NULL,          -- absolute path on disk
    file_name TEXT NOT NULL,          -- filename only (used for URL)
    file_size_bytes INTEGER DEFAULT 0,
    duration_seconds REAL,            -- only for clips
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | complete | failed
    error_message TEXT,
    created_at TEXT NOT NULL          -- ISO 8601
);
```

No migrations framework. Schema is applied idempotently via `CREATE TABLE IF NOT EXISTS` on startup.

## Configuration

All config is via environment variables (or `.env` file), handled by `pydantic-settings`:

| Variable | Default | Description |
|----------|---------|-------------|
| `PLEX_URL` | `""` | Plex server URL (e.g., `http://172.17.0.1:32400`). Leave blank to disable. |
| `PLEX_TOKEN` | `""` | Plex authentication token. Never exposed to the client. |
| `JELLYFIN_URL` | `""` | Jellyfin server URL (e.g., `http://172.17.0.1:8096`). Leave blank to disable. |
| `JELLYFIN_API_KEY` | `""` | Jellyfin API key. Never exposed to the client. |
| `CAPTURE_DIR` | `/data/captures` | Directory for saved screenshots and clips. |
| `DB_PATH` | `/data/mediasnap.db` | SQLite database file path. |
| `FFMPEG_PATH` | `ffmpeg` | Path to FFmpeg binary. |
| `SCREENSHOT_QUALITY` | `2` | FFmpeg `-q:v` value (1=best, 31=worst). |
| `HOST` | `0.0.0.0` | Server bind host. |
| `PORT` | `8787` | Server bind port. |

Sources are enabled/disabled based on whether their URL + token are both non-empty (see `plex_enabled` / `jellyfin_enabled` properties on the Settings class).

## Docker architecture

The Dockerfile is multi-stage:
1. **Stage 1 (node:20-slim):** Builds the React frontend via `npm ci && npm run build`, outputs to `/build/dist`.
2. **Stage 2 (python:3.12-slim):** Installs FFmpeg via apt, installs Python deps, copies backend source and built frontend.

The compose file mounts:
- The host media library to `/media:ro` (read-only) — must match the paths Plex/Jellyfin report in their API responses.
- `./data` to `/data` (read-write) — captures directory and SQLite DB.

In production, FastAPI serves the built frontend as static files from `frontend/dist/`. In development, Vite's dev server runs on :5173 and proxies `/api` and `/captures` to the backend on :8787.

## Security model

- **No authentication** on the MediaSnap web UI itself. It is assumed to run on a trusted home network and should not be exposed publicly.
- **Credentials are never sent to the client.** Plex tokens and Jellyfin API keys are stored only in environment variables and injected server-side by the proxy endpoints. API responses, thumbnail URLs, and network requests visible in the browser contain no secrets.
- **Proxy origin validation.** The thumbnail proxy only forwards requests to paths starting with `/` and only to the configured `PLEX_URL` or `JELLYFIN_URL` origins.
- **Media volume is read-only.** The media library is mounted as `:ro` in Docker to prevent any accidental writes.

## Current state and what's done

### Complete (Phase 1 — Screenshot MVP + Phase 2 — Clip Extraction UI)
- FastAPI backend with all core services
- Plex session fetching and normalization (XML parsing)
- Jellyfin session fetching and normalization (JSON)
- Unified session manager with concurrent polling and in-memory cache
- FFmpeg screenshot extraction (input-level seeking, < 1s)
- FFmpeg clip extraction with fast (stream copy) and precise (re-encode) modes
- Clip extraction runs as a FastAPI `BackgroundTasks` job
- SQLite capture persistence
- Full CRUD API for captures (create screenshot, create clip, list, get, download, delete)
- Thumbnail proxy for both Plex and Jellyfin (no credentials leaked to client)
- React frontend with Now Playing view (session cards, thumbnails, progress bars, screenshot + clip buttons)
- Clip form on session cards with duration presets (10s/30s/60s/2m/5m) and precise mode toggle
- React gallery view with download/delete and distinct pending/failed/complete clip states
- Pending-clip polling (3-second interval, auto-stops when no pending captures)
- Session polling every 5 seconds
- Docker multi-stage build
- docker-compose deployment config

### Not started (Phase 3 — Polish)
- Share link generation (short-lived public URLs)
- Auto-cleanup of old captures (configurable retention period)
- Webhook integration (Discord, etc.)
- Subtitle burn-in option for clips
- Settings page in the UI (currently all config is env-var only)
- Mobile UI optimization
- Capture quality/format options in the UI

## Key conventions and patterns

- **No ORMs.** Raw SQL with parameterized queries via aiosqlite.
- **No CSS framework.** Inline styles in React components. Dark theme: `#0f0f23` page background, `#1a1a2e` card backgrounds, `#333` borders, `#eee` primary text, `#888`/`#aaa` secondary text, `#e5a00d` (gold) for Plex accents and primary buttons, `#00a4dc` (blue) for Jellyfin accents, `#ff6b6b` for errors and destructive actions, `#2a4a7f` for download buttons, `#4a1a1a` for delete button backgrounds.
- **Pydantic everywhere.** Request bodies, response models, and config are all Pydantic models.
- **Async throughout.** All I/O (HTTP calls, DB access, FFmpeg subprocess) is async.
- **FFmpeg via subprocess.** Not via a Python binding. Commands are built as argument lists and run via `asyncio.create_subprocess_exec`.
- **Session IDs are prefixed** with `plex-` or `jf-` to namespace across sources.
- **Captures are identified by UUIDs.** File names are `{uuid}.jpg` or `{uuid}.mp4`.
- **Error handling:** Services raise exceptions, routers catch and return `HTTPException` with detail messages.
- **Frontend has no router.** Tab switching is done via React state (`useState<"now-playing" | "gallery">`).
- **Credentials never reach the client.** All media server auth is injected server-side by the proxy layer.
- **React 19 strict types.** `useRef` requires an initial value argument (e.g., `useRef<number | undefined>(undefined)` not `useRef<number>()`).

## Development workflow

**Backend:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in your values
uvicorn main:app --reload --port 8787
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev  # http://localhost:5173, proxies /api and /captures to :8787
```

**Build for production:**
```bash
docker compose up -d --build
# Access at http://your-server:8787
```

## Known issues and gotchas

1. **Path mapping is critical.** The media file paths reported by Plex/Jellyfin must be accessible at the same absolute path inside the MediaSnap container. If Plex reports a file at `/data/media/Movies/film.mkv`, then MediaSnap must see it at exactly `/data/media/Movies/film.mkv`. The Docker volume mount must match accordingly.
2. **Session cache is ephemeral.** If the backend restarts, the session cache is empty until the next `GET /api/sessions` call (triggered by frontend polling). Any in-flight capture requests against stale session IDs will 404.
3. **No auth on the web UI.** Anyone on the network can take screenshots and browse the gallery. Acceptable for a home network, not suitable for public exposure.
4. **React 19 type strictness.** `useRef()` with no argument causes `TS2554`. Always provide an initial value: `useRef<T | undefined>(undefined)`.
6. **Empty `__init__.py` files required.** `backend/routers/__init__.py` and `backend/services/__init__.py` must exist (can be empty) for Python to treat them as packages.