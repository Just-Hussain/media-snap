"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Plex
    plex_url: str = ""
    plex_token: str = ""

    # Jellyfin
    jellyfin_url: str = ""
    jellyfin_api_key: str = ""

    # Storage
    capture_dir: str = "/data/captures"
    db_path: str = "/data/mediasnap.db"

    # FFmpeg
    ffmpeg_path: str = "ffmpeg"
    screenshot_quality: int = 2  # 1 (best) to 31 (worst) for -q:v

    # Server
    host: str = "0.0.0.0"
    port: int = 8787

    model_config = {"env_prefix": "", "env_file": ".env"}

    @property
    def plex_enabled(self) -> bool:
        return bool(self.plex_url and self.plex_token)

    @property
    def jellyfin_enabled(self) -> bool:
        return bool(self.jellyfin_url and self.jellyfin_api_key)


settings = Settings()