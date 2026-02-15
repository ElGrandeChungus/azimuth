import json
import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    OPENROUTER_API_KEY: str
    OPENROUTER_BASE_URL: str
    DATABASE_PATH: str
    DEFAULT_MODEL: str
    CORS_ORIGINS: list[str]



def _parse_cors_origins(raw: str | None) -> list[str]:
    if not raw:
        return ["http://localhost:5173", "http://localhost:3000"]

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = [origin.strip() for origin in raw.split(",") if origin.strip()]

    if not isinstance(parsed, list):
        raise ValueError("CORS_ORIGINS must be a JSON array or comma-separated string")

    origins = [str(origin).strip() for origin in parsed if str(origin).strip()]

    local_origin = os.getenv("LOCAL_NETWORK_ORIGIN", "").strip()
    if local_origin and local_origin not in origins:
        origins.append(local_origin)

    return origins


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is required")

    return Settings(
        OPENROUTER_API_KEY=api_key,
        OPENROUTER_BASE_URL=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip(),
        DATABASE_PATH=os.getenv("DATABASE_PATH", "data/azimuth.db").strip(),
        DEFAULT_MODEL=os.getenv("DEFAULT_MODEL", "anthropic/claude-sonnet-4.5").strip(),
        CORS_ORIGINS=_parse_cors_origins(os.getenv("CORS_ORIGINS")),
    )


settings = get_settings()