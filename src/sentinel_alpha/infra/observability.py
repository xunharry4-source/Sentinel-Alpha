from __future__ import annotations

from fastapi import FastAPI

from sentinel_alpha.config import AppSettings

try:
    from prometheus_fastapi_instrumentator import Instrumentator
except ImportError:  # pragma: no cover
    Instrumentator = None  # type: ignore[assignment]

try:
    import sentry_sdk
except ImportError:  # pragma: no cover
    sentry_sdk = None  # type: ignore[assignment]


def initialize_observability(app: FastAPI, settings: AppSettings) -> dict[str, str]:
    statuses: dict[str, str] = {}
    if settings.prometheus_enabled and Instrumentator is not None:
        Instrumentator().instrument(app).expose(app, endpoint=settings.prometheus_metrics_path, include_in_schema=False)
        statuses["prometheus"] = "enabled"
    elif settings.prometheus_enabled:
        statuses["prometheus"] = "missing_dependency"
    else:
        statuses["prometheus"] = "disabled"

    if settings.sentry_enabled and settings.sentry_dsn and sentry_sdk is not None:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            profiles_sample_rate=settings.sentry_profiles_sample_rate,
            environment=settings.sentry_environment,
        )
        statuses["sentry"] = "enabled"
    elif settings.sentry_enabled:
        statuses["sentry"] = "misconfigured"
    else:
        statuses["sentry"] = "disabled"
    return statuses
