"""App settings. All external keys optional — app degrades gracefully without them."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MSCOUT_", env_file=BASE_DIR / ".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8106
    # mindat.org API token (free account at mindat.org -> My Home Page -> API key).
    # Without it the /api/mindat endpoints return 503 with signup instructions.
    mindat_api_key: str = ""
    # Upstream HTTP timeout (seconds). Public ArcGIS/USGS servers can be slow.
    upstream_timeout: float = 30.0
    # Cache TTL seconds for upstream responses (default 24h; geodata changes slowly).
    cache_ttl: int = 86400
    cache_dir: Path = BASE_DIR / "data" / "cache"


settings = Settings()
