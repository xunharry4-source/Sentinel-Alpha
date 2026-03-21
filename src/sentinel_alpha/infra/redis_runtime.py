from __future__ import annotations

import json

from sentinel_alpha.config import get_settings
from sentinel_alpha.domain.models import StrategyBrief

try:
    from redis import Redis
except ImportError:  # pragma: no cover
    Redis = None  # type: ignore[assignment]


class RedisRuntimeBus:
    """Caches strategy state and publishes runtime events for agent coordination."""

    def __init__(self, url: str | None = None) -> None:
        if Redis is None:
            raise RuntimeError("redis is required to use RedisRuntimeBus.")
        resolved_url = url or get_settings().redis_url
        self.client = Redis.from_url(resolved_url)

    def cache_strategy_brief(self, brief: StrategyBrief) -> None:
        self.client.setex(f"strategy:{brief.symbol}", 300, json.dumps(brief.__dict__))

    def publish_agent_event(self, channel: str, payload: dict[str, object]) -> None:
        self.client.publish(channel, json.dumps(payload))
