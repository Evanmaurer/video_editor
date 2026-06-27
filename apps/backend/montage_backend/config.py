from __future__ import annotations

import os
import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 0
    auth_token: str = ""
    log_level: str = "INFO"
    app_data_dir: Path = Path(os.environ.get("MONTAGE_APP_DATA_DIR", str(Path.home() / ".montage-ai")))
    gpu_enabled: bool = True
    worker_count: int = 2
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"

    model_config = SettingsConfigDict(env_prefix="MONTAGE_")

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        if not self.auth_token:
            object.__setattr__(self, "auth_token", secrets.token_urlsafe(32))


settings = Settings()
