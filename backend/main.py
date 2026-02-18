"""MediaSnap — FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from database import init_db
from routers import captures, proxy, sessions


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Path(settings.capture_dir).mkdir(parents=True, exist_ok=True)
    await init_db()
    yield
    # Shutdown (nothing to clean up)


app = FastAPI(
    title="MediaSnap",
    description="Screenshot & clip tool for Plex/Jellyfin",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router, prefix="/api")
app.include_router(captures.router, prefix="/api")
app.include_router(proxy.router, prefix="/api")

# Serve captured files
app.mount(
    "/captures",
    StaticFiles(directory=settings.capture_dir),
    name="captures",
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# In production, the built React frontend is served from here.
# During development, Vite's dev server proxies API calls instead.
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")