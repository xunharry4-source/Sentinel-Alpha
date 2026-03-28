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
    performance_enabled: bool
    performance_market_data_cache_size: int
    performance_llm_cache_size: int
    performance_dataset_plan_cache_size: int
    intelligence_enabled: bool
    intelligence_max_documents: int
    intelligence_request_timeout_seconds: int
    intelligence_rss_search_templates: list[str]
    market_data_default_provider: str
    market_data_enabled_providers: list[str]
    market_data_request_timeout_seconds: int
    market_data_provider_configs: dict[str, dict[str, str | bool]]
    fundamentals_default_provider: str
    fundamentals_enabled_providers: list[str]
    fundamentals_request_timeout_seconds: int
    fundamentals_provider_configs: dict[str, dict[str, str | bool]]
    dark_pool_default_provider: str
    dark_pool_enabled_providers: list[str]
    dark_pool_request_timeout_seconds: int
    dark_pool_provider_configs: dict[str, dict[str, str | bool]]
    options_default_provider: str
    options_enabled_providers: list[str]
    options_request_timeout_seconds: int
    options_provider_configs: dict[str, dict[str, str | bool]]
    llm_enabled: bool
    llm_strict: bool
    llm_default_provider: str
    llm_default_models: list[str]
    llm_default_temperature: float
    llm_default_max_tokens: int
    llm_provider_envs: dict[str, dict[str, str | list[str]]]
    llm_agent_configs: dict[str, dict[str, object]]
    llm_task_configs: dict[str, dict[str, object]]
    programmer_agent_enabled: bool
    programmer_agent_command: str
    programmer_agent_args: list[str]
    programmer_agent_repo_path: str
    programmer_agent_allowed_paths: list[str]
    programmer_agent_protected_paths: list[str]
    programmer_agent_enforce_target_isolation: bool
    programmer_agent_auto_commit: bool
    programmer_agent_timeout_seconds: int
    programmer_agent_retry_attempts: int
    prometheus_enabled: bool
    prometheus_metrics_path: str
    sentry_enabled: bool
    sentry_dsn: str | None
    sentry_environment: str
    sentry_traces_sample_rate: float
    sentry_profiles_sample_rate: float
    langfuse_enabled: bool
    langfuse_host: str
    langfuse_public_key: str | None
    langfuse_secret_key: str | None
    grafana_url: str | None
    config_path: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]

def _load_dotenv() -> None:
    """Load repo-local .env into the process environment (non-destructive).

    This keeps secrets out of settings.toml while allowing local dev/pytest to run without
    manual `export` each time. Existing environment variables take precedence.
    """
    path = _repo_root() / ".env"
    if not path.exists():
        return
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception:
        return


def _config_path() -> Path:
    configured = os.getenv("SENTINEL_CONFIG_FILE")
    if configured:
        return Path(configured).expanduser().resolve()
    return _repo_root() / "config" / "settings.toml"


def _config_backup_dir(path: Path | None = None) -> Path:
    resolved = path or _config_path()
    return resolved.parent / "backups"


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


def backup_config_file(path: Path | None = None) -> Path | None:
    resolved = path or _config_path()
    if not resolved.exists():
        return None
    backup_dir = _config_backup_dir(resolved)
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = Path(resolved).stat().st_mtime_ns
    backup_path = backup_dir / f"{resolved.stem}.{timestamp}.bak{resolved.suffix}"
    backup_path.write_text(resolved.read_text(encoding="utf-8"), encoding="utf-8")
    return backup_path


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


def write_config_payload_with_backup(payload: dict, path: Path | None = None) -> tuple[Path, Path | None]:
    resolved = path or _config_path()
    backup_path = backup_config_file(resolved)
    written_path = write_config_payload(payload, resolved)
    return written_path, backup_path


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    _load_dotenv()
    path = _config_path()
    with path.open("rb") as handle:
        payload = tomllib.load(handle)

    app = payload.get("app", {})
    api = payload.get("api", {})
    frontend = payload.get("frontend", {})
    storage = payload.get("storage", {})
    behavior = payload.get("behavior", {})
    performance = payload.get("performance", {})
    intelligence = payload.get("intelligence", {})
    market_data = payload.get("market_data", {})
    fundamentals = payload.get("fundamentals", {})
    dark_pool = payload.get("dark_pool", {})
    options_data = payload.get("options_data", {})
    llm = payload.get("llm", {})
    programmer_agent = payload.get("programmer_agent", {})
    observability = payload.get("observability", {})
    prometheus = observability.get("prometheus", {})
    sentry = observability.get("sentry", {})
    langfuse = observability.get("langfuse", {})
    grafana = observability.get("grafana", {})
    llm_providers = llm.get("providers", {})
    llm_agents = llm.get("agents", {})
    llm_tasks = llm.get("tasks", {})
    market_data_providers = market_data.get("providers", {})
    fundamentals_providers = fundamentals.get("providers", {})
    dark_pool_providers = dark_pool.get("providers", {})
    options_providers = options_data.get("providers", {})

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
        performance_enabled=_env_bool("SENTINEL_PERFORMANCE_ENABLED", bool(performance.get("enabled", True))),
        performance_market_data_cache_size=int(os.getenv("SENTINEL_MARKET_DATA_CACHE_SIZE", str(performance.get("market_data_cache_size", 128)))),
        performance_llm_cache_size=int(os.getenv("SENTINEL_LLM_CACHE_SIZE", str(performance.get("llm_cache_size", 64)))),
        performance_dataset_plan_cache_size=int(os.getenv("SENTINEL_DATASET_PLAN_CACHE_SIZE", str(performance.get("dataset_plan_cache_size", 16)))),
        intelligence_enabled=bool(_required(intelligence, "enabled")),
        intelligence_max_documents=int(_required(intelligence, "max_documents")),
        intelligence_request_timeout_seconds=int(_required(intelligence, "request_timeout_seconds")),
        intelligence_rss_search_templates=list(_required(intelligence, "rss_search_templates")),
        market_data_default_provider=str(_required(market_data, "default_provider")),
        market_data_enabled_providers=list(_required(market_data, "enabled_providers")),
        market_data_request_timeout_seconds=int(_required(market_data, "request_timeout_seconds")),
        market_data_provider_configs={str(name): dict(config) for name, config in market_data_providers.items()},
        fundamentals_default_provider=str(_required(fundamentals, "default_provider")),
        fundamentals_enabled_providers=list(_required(fundamentals, "enabled_providers")),
        fundamentals_request_timeout_seconds=int(_required(fundamentals, "request_timeout_seconds")),
        fundamentals_provider_configs={str(name): dict(config) for name, config in fundamentals_providers.items()},
        dark_pool_default_provider=str(_required(dark_pool, "default_provider")),
        dark_pool_enabled_providers=list(_required(dark_pool, "enabled_providers")),
        dark_pool_request_timeout_seconds=int(_required(dark_pool, "request_timeout_seconds")),
        dark_pool_provider_configs={str(name): dict(config) for name, config in dark_pool_providers.items()},
        options_default_provider=str(_required(options_data, "default_provider")),
        options_enabled_providers=list(_required(options_data, "enabled_providers")),
        options_request_timeout_seconds=int(_required(options_data, "request_timeout_seconds")),
        options_provider_configs={str(name): dict(config) for name, config in options_providers.items()},
        llm_enabled=_env_bool("SENTINEL_LLM_ENABLED", bool(llm.get("enabled", False))),
        llm_strict=_env_bool("SENTINEL_LLM_STRICT", bool(llm.get("strict", True))),
        llm_default_provider=os.getenv("SENTINEL_LLM_DEFAULT_PROVIDER", str(llm.get("default_provider", "openai"))),
        llm_default_models=[str(item) for item in llm.get("default_models", ["gpt-4.1-mini"]) if str(item).strip()],
        llm_default_temperature=float(os.getenv("SENTINEL_LLM_DEFAULT_TEMPERATURE", str(llm.get("default_temperature", 0.2)))),
        llm_default_max_tokens=int(os.getenv("SENTINEL_LLM_DEFAULT_MAX_TOKENS", str(llm.get("default_max_tokens", 1200)))),
        llm_provider_envs={str(name): dict(config) for name, config in llm_providers.items()},
        llm_agent_configs={str(name): dict(config) for name, config in llm_agents.items()},
        llm_task_configs={str(name): dict(config) for name, config in llm_tasks.items()},
        programmer_agent_enabled=_env_bool("SENTINEL_PROGRAMMER_AGENT_ENABLED", bool(programmer_agent.get("enabled", False))),
        programmer_agent_command=os.getenv("SENTINEL_PROGRAMMER_AGENT_COMMAND", str(programmer_agent.get("command", "aider"))),
        programmer_agent_args=list(programmer_agent.get("args", ["--yes-always"])),
        programmer_agent_repo_path=os.getenv("SENTINEL_PROGRAMMER_AGENT_REPO_PATH", str(programmer_agent.get("repo_path", str(_repo_root())))),
        programmer_agent_allowed_paths=list(programmer_agent.get("allowed_paths", ["src/sentinel_alpha/strategies", "src/sentinel_alpha/infra/generated_sources", "src/sentinel_alpha/infra/generated_terminals", "tests", "scripts"])),
        programmer_agent_protected_paths=list(
            programmer_agent.get(
                "protected_paths",
                [
                    "src/sentinel_alpha/backtesting",
                    "src/sentinel_alpha/api/workflow_service.py",
                    "tests/backtesting/test_metrics_engine_contract.py",
                    "tests/backtesting/test_backtest_engine.py",
                    "tests/backtesting/test_workflow_backtest_integration.py",
                ],
            )
        ),
        programmer_agent_enforce_target_isolation=_env_bool(
            "SENTINEL_PROGRAMMER_AGENT_ENFORCE_TARGET_ISOLATION",
            bool(programmer_agent.get("enforce_target_isolation", True)),
        ),
        programmer_agent_auto_commit=_env_bool("SENTINEL_PROGRAMMER_AGENT_AUTO_COMMIT", bool(programmer_agent.get("auto_commit", True))),
        programmer_agent_timeout_seconds=int(os.getenv("SENTINEL_PROGRAMMER_AGENT_TIMEOUT_SECONDS", str(programmer_agent.get("timeout_seconds", 180)))),
        programmer_agent_retry_attempts=int(os.getenv("SENTINEL_PROGRAMMER_AGENT_RETRY_ATTEMPTS", str(programmer_agent.get("retry_attempts", 3)))),
        prometheus_enabled=_env_bool("SENTINEL_PROMETHEUS_ENABLED", bool(prometheus.get("enabled", True))),
        prometheus_metrics_path=os.getenv("SENTINEL_PROMETHEUS_METRICS_PATH", str(prometheus.get("metrics_path", "/metrics"))),
        sentry_enabled=_env_bool("SENTINEL_SENTRY_ENABLED", bool(sentry.get("enabled", False))),
        sentry_dsn=os.getenv("SENTINEL_SENTRY_DSN", str(sentry.get("dsn", ""))) or None,
        sentry_environment=os.getenv("SENTINEL_SENTRY_ENVIRONMENT", str(sentry.get("environment", "development"))),
        sentry_traces_sample_rate=float(os.getenv("SENTINEL_SENTRY_TRACES_SAMPLE_RATE", str(sentry.get("traces_sample_rate", 0.1)))),
        sentry_profiles_sample_rate=float(os.getenv("SENTINEL_SENTRY_PROFILES_SAMPLE_RATE", str(sentry.get("profiles_sample_rate", 0.0)))),
        langfuse_enabled=_env_bool("SENTINEL_LANGFUSE_ENABLED", bool(langfuse.get("enabled", False))),
        langfuse_host=os.getenv("SENTINEL_LANGFUSE_HOST", str(langfuse.get("host", "http://localhost:3000"))),
        langfuse_public_key=os.getenv("SENTINEL_LANGFUSE_PUBLIC_KEY", str(langfuse.get("public_key", ""))) or None,
        langfuse_secret_key=os.getenv("SENTINEL_LANGFUSE_SECRET_KEY", str(langfuse.get("secret_key", ""))) or None,
        grafana_url=os.getenv("SENTINEL_GRAFANA_URL", str(grafana.get("url", ""))) or None,
        config_path=str(path),
    )
