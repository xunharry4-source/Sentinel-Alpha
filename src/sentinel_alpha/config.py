from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class AppSettings:
    app_name: str
    app_mode: str
    api_host: str
    api_port: int
    api_cors_origins: list[str]
    frontend_host: str
    frontend_port: int
    postgres_dsn: str
    timescale_dsn: str
    redis_url: str
    qdrant_url: str
    qdrant_collection: str
    minimum_universe_size: int
    health_retry_ms: int
    intelligence_enabled: bool
    intelligence_max_documents: int
    intelligence_request_timeout_seconds: int
    intelligence_rss_search_templates: list[str]
    config_path: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _config_path() -> Path:
    configured = os.getenv("SENTINEL_CONFIG_FILE")
    if configured:
        return Path(configured).expanduser().resolve()
    return _repo_root() / "config" / "settings.toml"


def _required(section: dict, key: str) -> object:
    if key not in section:
        raise KeyError(f"Missing required config key: {key}")
    return section[key]


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    path = _config_path()
    with path.open("rb") as handle:
        payload = tomllib.load(handle)

    app = payload.get("app", {})
    api = payload.get("api", {})
    frontend = payload.get("frontend", {})
    storage = payload.get("storage", {})
    behavior = payload.get("behavior", {})
    intelligence = payload.get("intelligence", {})

    return AppSettings(
        app_name=str(_required(app, "name")),
        app_mode=str(_required(app, "mode")),
        api_host=os.getenv("SENTINEL_API_HOST", str(_required(api, "host"))),
        api_port=int(os.getenv("SENTINEL_API_PORT", str(_required(api, "port")))),
        api_cors_origins=list(_required(api, "cors_origins")),
        frontend_host=os.getenv("SENTINEL_FRONTEND_HOST", str(_required(frontend, "host"))),
        frontend_port=int(os.getenv("SENTINEL_FRONTEND_PORT", str(_required(frontend, "port")))),
        postgres_dsn=os.getenv("SENTINEL_POSTGRES_DSN", str(_required(storage, "postgres_dsn"))),
        timescale_dsn=os.getenv("SENTINEL_TIMESCALE_DSN", str(storage.get("timescale_dsn", _required(storage, "postgres_dsn")))),
        redis_url=os.getenv("SENTINEL_REDIS_URL", str(_required(storage, "redis_url"))),
        qdrant_url=os.getenv("SENTINEL_QDRANT_URL", str(_required(storage, "qdrant_url"))),
        qdrant_collection=os.getenv("SENTINEL_QDRANT_COLLECTION", str(_required(storage, "qdrant_collection"))),
        minimum_universe_size=int(_required(behavior, "minimum_universe_size")),
        health_retry_ms=int(_required(behavior, "health_retry_ms")),
        intelligence_enabled=bool(_required(intelligence, "enabled")),
        intelligence_max_documents=int(_required(intelligence, "max_documents")),
        intelligence_request_timeout_seconds=int(_required(intelligence, "request_timeout_seconds")),
        intelligence_rss_search_templates=list(_required(intelligence, "rss_search_templates")),
        config_path=str(path),
    )
