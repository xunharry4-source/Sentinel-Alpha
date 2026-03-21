from __future__ import annotations

from sentinel_alpha.config import get_settings
from sentinel_alpha.domain.models import BehaviorEvent, MarketDataPoint

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None  # type: ignore[assignment]


class TimescaleBehaviorEventWriter:
    """Writes simulation behavior traces into a TimescaleDB hypertable."""

    def __init__(self, dsn: str | None = None) -> None:
        if psycopg is None:
            raise RuntimeError("psycopg is required to use TimescaleBehaviorEventWriter.")
        self.dsn = dsn or get_settings().timescale_dsn

    def write_behavior_events(self, user_id: str, events: list[BehaviorEvent]) -> None:
        if not events:
            return
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                for event in events:
                    cursor.execute(
                        """
                        insert into behavior_events_ts (
                            user_id,
                            scenario_id,
                            price_drawdown_pct,
                            action,
                            noise_level,
                            sentiment_pressure,
                            latency_seconds
                        ) values (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            user_id,
                            event.scenario_id,
                            event.price_drawdown_pct,
                            event.action,
                            event.noise_level,
                            event.sentiment_pressure,
                            event.latency_seconds,
                        ),
                    )

    def write_market_data_points(self, session_id: str, points: list[MarketDataPoint]) -> None:
        if not points:
            return
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                for point in points:
                    cursor.execute(
                        """
                        insert into market_data_ts (
                            session_id,
                            ts,
                            symbol,
                            timeframe,
                            open_price,
                            high_price,
                            low_price,
                            close_price,
                            volume,
                            source,
                            regime_tag
                        ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            session_id,
                            point.timestamp,
                            point.symbol,
                            point.timeframe,
                            point.open_price,
                            point.high_price,
                            point.low_price,
                            point.close_price,
                            point.volume,
                            point.source,
                            point.regime_tag,
                        ),
                    )
