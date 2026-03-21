from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from random import Random
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

    def save_information_events(self, session_id: UUID, events: list[dict]) -> None:
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                for event in events:
                    cursor.execute(
                        """
                        insert into information_events (
                            id, session_id, channel, trading_day, source,
                            author, handle, title, body, info_tag,
                            sentiment_score, payload
                        ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                        """,
                        (
                            uuid4(),
                            session_id,
                            event.get("channel"),
                            event.get("trading_day"),
                            event.get("source"),
                            event.get("author"),
                            event.get("handle"),
                            event.get("title"),
                            event.get("body"),
                            event.get("info_tag"),
                            event.get("sentiment_score", 0.0),
                            json.dumps(event),
                        ),
                    )

    def save_history_event(self, session_id: UUID, event: dict) -> None:
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into history_events (
                        id, session_id, event_type, summary, phase, payload
                    ) values (%s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        uuid4(),
                        session_id,
                        event.get("event_type", "unknown"),
                        event.get("summary", ""),
                        event.get("phase"),
                        json.dumps(event),
                    ),
                )

    def save_report_snapshot(self, session_id: UUID, report: dict) -> None:
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into report_snapshots (
                        id, session_id, report_type, title, phase, related_refs, payload
                    ) values (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                    """,
                    (
                        uuid4(),
                        session_id,
                        report.get("report_type", "unknown"),
                        report.get("title", ""),
                        report.get("phase"),
                        json.dumps(report.get("related_refs", [])),
                        json.dumps(report),
                    ),
                )

    def compose_market_template_campaign(
        self,
        day_count: int = 40,
        required_shapes: list[str] | None = None,
        required_regimes: list[str] | None = None,
        baseline_open: float = 100.0,
        seed: int = 11,
    ) -> list[dict]:
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                where_clauses: list[str] = []
                params: list[object] = []
                if required_shapes:
                    where_clauses.append("lower(coalesce(shape_family, '')) = any(%s)")
                    params.append([item.lower() for item in required_shapes])
                if required_regimes:
                    where_clauses.append("lower(coalesce(market_regime, '')) = any(%s)")
                    params.append([item.lower() for item in required_regimes])
                where_sql = f"where {' and '.join(where_clauses)}" if where_clauses else ""
                cursor.execute(
                    """
                    with templ as (
                        select
                            id,
                            symbol,
                            trading_day,
                            playbook,
                            pattern_label,
                            market_regime,
                            shape_family,
                            open_price,
                            high_price,
                            low_price,
                            close_price,
                            volume,
                            metadata,
                            lag(close_price) over (partition by symbol order by trading_day) as source_prev_close
                        from market_template_days
                    )
                    select id, symbol, trading_day, playbook, pattern_label,
                           market_regime, shape_family,
                           open_price, high_price, low_price, close_price, volume, metadata, source_prev_close
                    from templ
                    """
                    + where_sql
                    + """
                    order by random()
                    limit %s
                    """,
                    (*params, day_count),
                )
                selected_rows = cursor.fetchall()

                raw_days: list[dict] = []
                for (
                    template_day_id,
                    symbol,
                    trading_day,
                    playbook,
                    pattern_label,
                    market_regime,
                    shape_family,
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    volume,
                    metadata,
                    source_prev_close,
                ) in selected_rows:
                    cursor.execute(
                        """
                        select ts, open_price, high_price, low_price, close_price, volume
                        from market_data_ts
                        where symbol = %s
                          and timeframe = '5m'
                          and source = 'template_library'
                          and date(ts) = %s
                        order by ts asc
                        """,
                        (symbol, trading_day),
                    )
                    bars = [
                        {
                            "time": ts.isoformat(),
                            "timeLabel": ts.strftime("%H:%M"),
                            "open": open_v,
                            "high": high_v,
                            "low": low_v,
                            "close": close_v,
                            "volume": vol,
                        }
                        for ts, open_v, high_v, low_v, close_v, vol in cursor.fetchall()
                    ]
                    if not bars:
                        continue
                    cursor.execute(
                        """
                        select segment_index, start_ts, end_ts, shape_family, market_regime, pattern_label, metadata
                        from market_template_intraday_segments
                        where template_day_id = %s
                        order by segment_index asc
                        """,
                        (template_day_id,),
                    )
                    segments = [
                        {
                            "segment_index": segment_index,
                            "start": start_ts.isoformat(),
                            "end": end_ts.isoformat(),
                            "shape_family": segment_shape,
                            "market_regime": segment_regime,
                            "pattern_label": segment_label,
                            "metadata": segment_meta or {},
                        }
                        for segment_index, start_ts, end_ts, segment_shape, segment_regime, segment_label, segment_meta in cursor.fetchall()
                    ]
                    raw_days.append(
                        {
                            "template_day_id": str(template_day_id),
                            "symbol": symbol,
                            "dateLabel": str(trading_day),
                            "regimeKey": playbook or "template_library",
                            "regimeLabel": pattern_label or playbook or symbol,
                            "market_regime": market_regime,
                            "shape_family": shape_family,
                            "open": open_price,
                            "high": high_price,
                            "low": low_price,
                            "close": close_price,
                            "volume": volume,
                            "metadata": metadata or {},
                            "source_prev_close": source_prev_close,
                            "bars": bars,
                            "segments": segments,
                        }
                    )
                return self._shuffle_weeks_and_scale(raw_days, day_count=day_count, baseline_open=baseline_open, seed=seed)

    def _shuffle_weeks_and_scale(
        self,
        raw_days: list[dict],
        day_count: int,
        baseline_open: float,
        seed: int,
    ) -> list[dict]:
        if not raw_days:
            return []

        grouped: dict[str, list[dict]] = defaultdict(list)
        for day in raw_days:
            iso_year, iso_week, _ = date.fromisoformat(day["dateLabel"]).isocalendar()
            grouped[f"{iso_year}-W{iso_week:02d}"].append(day)

        weeks = list(grouped.values())
        for week in weeks:
            week.sort(key=lambda item: item["dateLabel"])

        randomizer = Random(seed)
        randomizer.shuffle(weeks)

        remixed: list[dict] = []
        current_anchor = baseline_open
        current_index = 0
        for week in weeks:
            if current_index >= day_count:
                break
            for day in week:
                if current_index >= day_count:
                    break
                source_anchor = float(day.get("source_prev_close") or 0.0)
                if source_anchor <= 0:
                    source_anchor = float(day["open"])
                if source_anchor <= 0:
                    continue
                scale = current_anchor / source_anchor
                remixed_day = self._scale_template_day(day, scale, current_index)
                remixed.append(remixed_day)
                current_anchor = remixed_day["close"]
                current_index += 1
        return remixed

    def _scale_template_day(self, day: dict, scale: float, day_index: int) -> dict:
        scaled_bars = [
            {
                **bar,
                "open": round(bar["open"] * scale, 4),
                "high": round(bar["high"] * scale, 4),
                "low": round(bar["low"] * scale, 4),
                "close": round(bar["close"] * scale, 4),
            }
            for bar in day["bars"]
        ]
        return {
            **day,
            "dayIndex": day_index,
            "source_weekly_remix": True,
            "open": round(day["open"] * scale, 4),
            "high": round(day["high"] * scale, 4),
            "low": round(day["low"] * scale, 4),
            "close": round(day["close"] * scale, 4),
            "bars": scaled_bars,
        }

    def market_template_coverage(self) -> dict:
        required_shapes = ["w", "n", "v", "a", "box", "trend"]
        required_regimes = ["bull", "bear", "oscillation", "fake_reversal", "gap"]
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select
                        lower(coalesce(shape_family, '')) as shape_family,
                        lower(coalesce(market_regime, '')) as market_regime,
                        count(*) as sample_count
                    from market_template_days
                    group by lower(coalesce(shape_family, '')), lower(coalesce(market_regime, ''))
                    order by sample_count desc
                    """
                )
                rows = cursor.fetchall()

        shape_counts: dict[str, int] = {}
        regime_counts: dict[str, int] = {}
        matrix: list[dict] = []
        for shape_family, market_regime, sample_count in rows:
            if shape_family:
                shape_counts[shape_family] = shape_counts.get(shape_family, 0) + sample_count
            if market_regime:
                regime_counts[market_regime] = regime_counts.get(market_regime, 0) + sample_count
            matrix.append(
                {
                    "shape_family": shape_family or "unknown",
                    "market_regime": market_regime or "unknown",
                    "sample_count": sample_count,
                }
            )

        missing_shapes = [item for item in required_shapes if shape_counts.get(item, 0) == 0]
        missing_regimes = [item for item in required_regimes if regime_counts.get(item, 0) == 0]
        return {
            "status": "ok" if not missing_shapes and not missing_regimes else "incomplete",
            "required_shapes": required_shapes,
            "required_regimes": required_regimes,
            "shape_counts": shape_counts,
            "regime_counts": regime_counts,
            "missing_shapes": missing_shapes,
            "missing_regimes": missing_regimes,
            "matrix": matrix,
        }
