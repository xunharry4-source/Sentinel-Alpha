from __future__ import annotations

import json
from uuid import UUID, uuid4

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None  # type: ignore[assignment]

from sentinel_alpha.config import get_settings


class PostgresWorkflowStore:
    """PostgreSQL-backed workflow persistence for product sessions."""

    def __init__(self, dsn: str | None = None) -> None:
        if psycopg is None:
            raise RuntimeError("psycopg is required to use PostgresWorkflowStore.")
        self.dsn = dsn or get_settings().postgres_dsn

    def create_session(self, user_name: str, starting_capital: float) -> dict:
        session_id = uuid4()
        user_id = uuid4()
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into users (id, display_name, default_execution_mode)
                    values (%s, %s, %s)
                    """,
                    (user_id, user_name, "advice_only"),
                )
                cursor.execute(
                    """
                    insert into workflow_sessions (id, user_id, status, phase)
                    values (%s, %s, %s, %s)
                    """,
                    (session_id, user_id, "active", "created"),
                )
        return {
            "session_id": session_id,
            "user_id": user_id,
            "user_name": user_name,
            "starting_capital": starting_capital,
            "phase": "created",
            "status": "active",
            "scenarios": [],
            "behavioral_report": None,
            "trade_universe": None,
            "strategy_package": None,
            "execution_mode": None,
        }

    def save_phase_payload(self, session_id: UUID, phase: str, payload_key: str, payload: dict | list | None) -> None:
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    update workflow_sessions
                    set phase = %s, updated_at = now()
                    where id = %s
                    """,
                    (phase, session_id),
                )
                if payload_key == "behavioral_report" and payload is not None:
                    report = payload
                    cursor.execute(
                        """
                        insert into behavioral_reports (
                            id, session_id, loss_tolerance, noise_sensitivity,
                            panic_sell_tendency, bottom_fishing_tendency, hold_strength,
                            overtrading_tendency, max_drawdown_endured, recommended_risk_ceiling,
                            archetype, report_json
                        ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                        on conflict (session_id) do update set
                            loss_tolerance = excluded.loss_tolerance,
                            noise_sensitivity = excluded.noise_sensitivity,
                            panic_sell_tendency = excluded.panic_sell_tendency,
                            bottom_fishing_tendency = excluded.bottom_fishing_tendency,
                            hold_strength = excluded.hold_strength,
                            overtrading_tendency = excluded.overtrading_tendency,
                            max_drawdown_endured = excluded.max_drawdown_endured,
                            recommended_risk_ceiling = excluded.recommended_risk_ceiling,
                            archetype = excluded.archetype,
                            report_json = excluded.report_json
                        """,
                        (
                            uuid4(),
                            session_id,
                            report.get("loss_tolerance"),
                            report.get("noise_sensitivity"),
                            report.get("panic_sell_tendency"),
                            report.get("bottom_fishing_tendency"),
                            report.get("hold_strength"),
                            report.get("overtrading_tendency"),
                            report.get("max_drawdown_endured"),
                            report.get("recommended_risk_ceiling"),
                            report.get("archetype"),
                            json.dumps(report),
                        ),
                    )
                elif payload_key == "trade_universe" and payload is not None:
                    cursor.execute(
                        """
                        insert into trade_universe_requests (
                            id, session_id, input_type, symbols, expanded_symbols, expansion_reason, minimum_universe_size
                        ) values (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
                        """,
                        (
                            uuid4(),
                            session_id,
                            payload["input_type"],
                            json.dumps(payload["requested"]),
                            json.dumps(payload["expanded"]),
                            payload["expansion_reason"],
                            payload["minimum_universe_size"],
                        ),
                    )
                elif payload_key == "trading_preferences" and payload is not None:
                    cursor.execute(
                        """
                        insert into trading_preferences (
                            id, session_id, trading_frequency, preferred_timeframe, rationale, preference_json
                        ) values (%s, %s, %s, %s, %s, %s::jsonb)
                        on conflict (session_id) do update set
                            trading_frequency = excluded.trading_frequency,
                            preferred_timeframe = excluded.preferred_timeframe,
                            rationale = excluded.rationale,
                            preference_json = excluded.preference_json
                        """,
                        (
                            uuid4(),
                            session_id,
                            payload["trading_frequency"],
                            payload["preferred_timeframe"],
                            payload.get("rationale"),
                            json.dumps(payload),
                        ),
                    )
                elif payload_key == "strategy_package" and payload is not None:
                    cursor.execute(
                        """
                        insert into strategy_iterations (
                            id, session_id, iteration_no, user_feedback, candidate_json, behavioral_compatibility, approved
                        ) values (%s, %s, %s, %s, %s::jsonb, %s, %s)
                        """,
                        (
                            uuid4(),
                            session_id,
                            payload["iteration_no"],
                            payload.get("feedback"),
                            json.dumps(payload),
                            payload.get("behavioral_compatibility"),
                            False,
                        ),
                    )

    def approve_strategy(self, session_id: UUID) -> None:
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    update strategy_iterations
                    set approved = true
                    where session_id = %s
                      and iteration_no = (
                        select max(iteration_no) from strategy_iterations where session_id = %s
                      )
                    """,
                    (session_id, session_id),
                )
                cursor.execute(
                    "update workflow_sessions set phase = %s, updated_at = now() where id = %s",
                    ("strategy_approved", session_id),
                )

    def set_deployment(self, session_id: UUID, execution_mode: str) -> None:
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into deployment_settings (session_id, execution_mode, autonomous_enabled, advice_only)
                    values (%s, %s, %s, %s)
                    on conflict (session_id) do update set
                        execution_mode = excluded.execution_mode,
                        autonomous_enabled = excluded.autonomous_enabled,
                        advice_only = excluded.advice_only,
                        confirmed_at = now()
                    """,
                    (session_id, execution_mode, execution_mode == "autonomous", execution_mode == "advice_only"),
                )
                cursor.execute(
                    "update workflow_sessions set phase = %s, selected_execution_mode = %s, updated_at = now() where id = %s",
                    ("autonomous_active" if execution_mode == "autonomous" else "advice_only_active", execution_mode, session_id),
                )

    def save_monitor_signals(self, session_id: UUID, signals: list[dict]) -> None:
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                for signal in signals:
                    cursor.execute(
                        """
                        insert into monitor_signals (id, session_id, monitor_type, severity, title, payload)
                        values (%s, %s, %s, %s, %s, %s::jsonb)
                        """,
                        (uuid4(), session_id, signal["monitor_type"], signal["severity"], signal["title"], json.dumps(signal)),
                    )

    def save_market_snapshot(self, session_id: UUID, snapshot: dict) -> None:
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into market_asset_snapshots (
                        id, session_id, symbol, timeframe, snapshot_json
                    ) values (%s, %s, %s, %s, %s::jsonb)
                    """,
                    (uuid4(), session_id, snapshot["symbol"], snapshot["timeframe"], json.dumps(snapshot)),
                )

    def save_trade_record(self, session_id: UUID, trade: dict) -> None:
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into trade_execution_records (
                        id, session_id, symbol, side, quantity, price, notional,
                        execution_mode, strategy_version, realized_pnl_pct,
                        user_initiated, note, payload
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        uuid4(),
                        session_id,
                        trade["symbol"],
                        trade["side"],
                        trade["quantity"],
                        trade["price"],
                        trade["notional"],
                        trade["execution_mode"],
                        trade.get("strategy_version"),
                        trade["realized_pnl_pct"],
                        trade["user_initiated"],
                        trade.get("note"),
                        json.dumps(trade),
                    ),
                )

    def save_profile_evolution(self, session_id: UUID, profile_evolution: dict) -> None:
        last_event = (profile_evolution.get("events") or [{}])[-1]
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into profile_evolution_events (
                        id, session_id, source_type, source_ref, event_json
                    ) values (%s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        uuid4(),
                        session_id,
                        last_event.get("source_type", "unknown"),
                        last_event.get("source_ref", "unknown"),
                        json.dumps(profile_evolution),
                    ),
                )

    def save_intelligence_documents(self, session_id: UUID, query: str, documents: list[dict]) -> None:
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                for document in documents:
                    cursor.execute(
                        """
                        insert into intelligence_documents (
                            id, session_id, query, source, title, url, published_at, payload
                        ) values (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                        """,
                        (
                            uuid4(),
                            session_id,
                            query,
                            document.get("source"),
                            document.get("title"),
                            document.get("url"),
                            document.get("published_at"),
                            json.dumps(document),
                        ),
                    )
