from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import json


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
    llm_enabled: bool
    llm_default_provider: str
    llm_default_model: str
    llm_default_temperature: float
    llm_default_max_tokens: int
    llm_provider_envs: dict[str, dict[str, str]]
    llm_agent_configs: dict[str, dict[str, str | float | int]]
    llm_task_configs: dict[str, dict[str, str | float | int]]
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


def _render_toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        rendered = ", ".join(_render_toml_value(item) for item in value)
        return f"[{rendered}]"
    if value is None:
        return '""'
    raise TypeError(f"Unsupported TOML value: {type(value)!r}")


def _render_toml_section(lines: list[str], path: list[str], payload: dict[str, object]) -> None:
    scalars: list[tuple[str, object]] = []
    nested: list[tuple[str, dict[str, object]]] = []
    for key, value in payload.items():
        if isinstance(value, dict):
            nested.append((key, value))
        else:
            scalars.append((key, value))
    if path:
        lines.append(f"[{'.'.join(path)}]")
    for key, value in scalars:
        lines.append(f"{key} = {_render_toml_value(value)}")
    if scalars and nested:
        lines.append("")
    for index, (key, value) in enumerate(nested):
        _render_toml_section(lines, [*path, key], value)
        if index != len(nested) - 1:
            lines.append("")


def read_config_payload(path: Path | None = None) -> dict:
    resolved = path or _config_path()
    with resolved.open("rb") as handle:
        return tomllib.load(handle)


def write_config_payload(payload: dict, path: Path | None = None) -> Path:
    resolved = path or _config_path()
    lines: list[str] = []
    for index, (section, content) in enumerate(payload.items()):
        if not isinstance(content, dict):
            raise TypeError("Top-level TOML sections must be tables.")
        _render_toml_section(lines, [section], content)
        if index != len(payload) - 1:
            lines.append("")
    resolved.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    get_settings.cache_clear()
    return resolved


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


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
    llm = payload.get("llm", {})
    llm_providers = llm.get("providers", {})
    llm_agents = llm.get("agents", {})
    llm_tasks = llm.get("tasks", {})

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
        llm_enabled=_env_bool("SENTINEL_LLM_ENABLED", bool(llm.get("enabled", False))),
        llm_default_provider=os.getenv("SENTINEL_LLM_DEFAULT_PROVIDER", str(llm.get("default_provider", "openai"))),
        llm_default_model=os.getenv("SENTINEL_LLM_DEFAULT_MODEL", str(llm.get("default_model", "gpt-4.1-mini"))),
        llm_default_temperature=float(os.getenv("SENTINEL_LLM_DEFAULT_TEMPERATURE", str(llm.get("default_temperature", 0.2)))),
        llm_default_max_tokens=int(os.getenv("SENTINEL_LLM_DEFAULT_MAX_TOKENS", str(llm.get("default_max_tokens", 1200)))),
        llm_provider_envs={str(name): dict(config) for name, config in llm_providers.items()},
        llm_agent_configs={str(name): dict(config) for name, config in llm_agents.items()},
        llm_task_configs={str(name): dict(config) for name, config in llm_tasks.items()},
        config_path=str(path),
    )
