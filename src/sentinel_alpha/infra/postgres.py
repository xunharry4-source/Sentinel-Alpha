from __future__ import annotations

import json
from dataclasses import asdict

from sentinel_alpha.config import get_settings
from sentinel_alpha.domain.models import BehaviorEvent, BehavioralReport, StrategyBrief, UserProfile

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None  # type: ignore[assignment]


class PostgresBehavioralRunRepository:
    """Stores durable behavioral runs and synthesized outputs in PostgreSQL."""

    def __init__(self, dsn: str | None = None) -> None:
        if psycopg is None:
            raise RuntimeError("psycopg is required to use PostgresBehavioralRunRepository.")
        self.dsn = dsn or get_settings().postgres_dsn

    def save_behavioral_run(
        self,
        user: UserProfile,
        events: list[BehaviorEvent],
        report: BehavioralReport,
        brief: StrategyBrief,
    ) -> None:
        payload = {
            "user_profile": json.dumps(asdict(user)),
            "events": json.dumps([asdict(event) for event in events]),
            "behavioral_report": json.dumps(asdict(report)),
            "strategy_brief": json.dumps(asdict(brief)),
        }
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into behavioral_runs (
                        user_id,
                        user_profile,
                        events,
                        behavioral_report,
                        strategy_brief
                    ) values (%(user_id)s, %(user_profile)s::jsonb, %(events)s::jsonb,
                              %(behavioral_report)s::jsonb, %(strategy_brief)s::jsonb)
                    """,
                    {"user_id": user.user_id, **payload},
                )
