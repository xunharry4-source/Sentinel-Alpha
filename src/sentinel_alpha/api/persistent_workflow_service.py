from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from uuid import UUID

from sentinel_alpha.api.workflow_service import WorkflowService, WorkflowSession
from sentinel_alpha.domain.models import BehaviorEvent, MarketDataPoint, StrategyBrief, TradeExecutionRecord, UserProfile
from sentinel_alpha.infra.postgres import PostgresBehavioralRunRepository
from sentinel_alpha.infra.qdrant_memory import QdrantBehaviorMemoryStore
from sentinel_alpha.infra.redis_runtime import RedisRuntimeBus
from sentinel_alpha.infra.simple_embedding import SimpleHashEmbedding
from sentinel_alpha.infra.timescale import TimescaleBehaviorEventWriter
from sentinel_alpha.infra.workflow_store import PostgresWorkflowStore

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None  # type: ignore[assignment]

try:
    from qdrant_client import QdrantClient
except ImportError:  # pragma: no cover
    QdrantClient = None  # type: ignore[assignment]


class PersistentWorkflowService(WorkflowService):
    def __init__(self) -> None:
        super().__init__()
        self.workflow_store = PostgresWorkflowStore()
        self.behavior_repo = PostgresBehavioralRunRepository()
        self.event_writer = TimescaleBehaviorEventWriter()
        self.runtime_bus = RedisRuntimeBus()
        self.memory_store = QdrantBehaviorMemoryStore(embedding_function=SimpleHashEmbedding())

    def create_session(self, user_name: str, starting_capital: float) -> WorkflowSession:
        payload = self.workflow_store.create_session(user_name, starting_capital)
        session = WorkflowSession(
            session_id=payload["session_id"],
            user_name=payload["user_name"],
            starting_capital=payload["starting_capital"],
            phase=payload["phase"],
            status=payload["status"],
        )
        self.sessions[session.session_id] = session
        self._append_history_event(
            session,
            "session_created",
            "会话已创建。",
            {"starting_capital": starting_capital, "user_name": user_name},
        )
        self.workflow_store.save_history_event(session.session_id, session.history_events[-1])
        self.runtime_bus.publish_agent_event("workflow.session.created", {"session_id": str(session.session_id), "user_name": user_name})
        return session

    def generate_scenarios(self, session_id: UUID) -> WorkflowSession:
        session = super().generate_scenarios(session_id)
        self.workflow_store.save_phase_payload(session_id, session.phase, "scenarios", session.scenarios)
        market_points: list[MarketDataPoint] = []
        for package in session.scenario_packages:
            for point in package.price_track:
                market_points.append(
                    MarketDataPoint(
                        timestamp=point.timestamp,
                        symbol=package.symbol_alias,
                        timeframe="scenario",
                        open_price=point.price,
                        high_price=point.price,
                        low_price=point.price,
                        close_price=point.price,
                        volume=0.0,
                        source="scenario_replay",
                        regime_tag=package.playbook,
                    )
                )
        self.event_writer.write_market_data_points(str(session_id), market_points)
        self.workflow_store.save_history_event(session_id, session.history_events[-1])
        self.runtime_bus.publish_agent_event("workflow.scenarios.generated", {"session_id": str(session_id), "count": len(session.scenarios)})
        return session

    def append_behavior_event(self, session_id: UUID, event: BehaviorEvent) -> WorkflowSession:
        session = super().append_behavior_event(session_id, event)
        self.event_writer.write_behavior_events(str(session_id), [event])
        self.workflow_store.save_history_event(session_id, session.history_events[-1])
        self.runtime_bus.publish_agent_event("workflow.simulation.event", {"session_id": str(session_id), "scenario_id": event.scenario_id, "action": event.action})
        return session

    def complete_simulation(self, session_id: UUID, symbol: str) -> WorkflowSession:
        session = super().complete_simulation(session_id, symbol)
        self.workflow_store.save_phase_payload(session_id, session.phase, "behavioral_report", session.behavioral_report)

        user = UserProfile(
            user_id=str(session.session_id),
            preferred_assets=[symbol],
            capital_base=session.starting_capital,
            target_holding_days=10,
            self_reported_risk_tolerance=0.5,
            confidence_level=0.5,
        )
        report_payload = session.behavioral_report or {}
        report = self.profiler.profile(session.behavior_events)
        brief = StrategyBrief(
            symbol=symbol,
            action_bias="profile_only",
            expected_return_pct=0.0,
            worst_case_drawdown_pct=abs(report_payload.get("loss_tolerance", 0.0)),
            utility_score=report_payload.get("strategy_compatibility_preview", 0.0),
            recommended_position_pct=report_payload.get("recommended_risk_ceiling", 0.0) * 100.0,
            rationale=["Behavioral profiler completed initial mapping."],
        )
        self.behavior_repo.save_behavioral_run(user, session.behavior_events, report, brief)
        self.memory_store.add_behavior_memory(user, report, brief)
        self.workflow_store.save_profile_evolution(session_id, session.profile_evolution or {})
        self.workflow_store.save_report_snapshot(session_id, session.report_history[-1])
        self.workflow_store.save_history_event(session_id, session.history_events[-1])
        self.runtime_bus.publish_agent_event("workflow.profiler.ready", {"session_id": str(session_id), "symbol": symbol})
        return session

    def set_trade_universe(self, session_id: UUID, input_type: str, symbols: list[str], allow_overfit_override: bool) -> WorkflowSession:
        session = super().set_trade_universe(session_id, input_type, symbols, allow_overfit_override)
        self.workflow_store.save_phase_payload(session_id, session.phase, "trade_universe", session.trade_universe)
        self.workflow_store.save_history_event(session_id, session.history_events[-1])
        self.runtime_bus.publish_agent_event("workflow.universe.ready", {"session_id": str(session_id), "expanded": session.trade_universe["expanded"]})
        return session

    def set_trading_preferences(
        self,
        session_id: UUID,
        trading_frequency: str,
        preferred_timeframe: str,
        rationale: str | None,
    ) -> WorkflowSession:
        session = super().set_trading_preferences(session_id, trading_frequency, preferred_timeframe, rationale)
        self.workflow_store.save_phase_payload(session_id, session.phase, "trading_preferences", session.trading_preferences)
        self.runtime_bus.publish_agent_event(
            "workflow.preferences.updated",
            {
                "session_id": str(session_id),
                "trading_frequency": trading_frequency,
                "preferred_timeframe": preferred_timeframe,
            },
        )
        self.workflow_store.save_history_event(session_id, session.history_events[-1])
        return session

    def iterate_strategy(
        self,
        session_id: UUID,
        feedback: str | None,
        strategy_type: str = "rule_based_aligned",
        auto_iterations: int = 1,
        iteration_mode: str = "guided",
        objective_metric: str = "return",
        objective_targets: dict | None = None,
    ) -> WorkflowSession:
        session = super().iterate_strategy(
            session_id,
            feedback,
            strategy_type,
            auto_iterations,
            iteration_mode,
            objective_metric,
            objective_targets,
        )
        self.workflow_store.save_phase_payload(session_id, session.phase, "strategy_package", session.strategy_package)
        self.workflow_store.save_phase_payload(session_id, session.phase, "strategy_training_log", session.strategy_training_log)
        self.workflow_store.save_report_snapshot(session_id, session.report_history[-1])
        self.workflow_store.save_history_event(session_id, session.history_events[-1])
        if feedback:
            self.workflow_store.save_profile_evolution(session_id, session.profile_evolution or {})
            self.memory_store.add_profile_evolution_memory(
                user_id=str(session_id),
                source_type="strategy_feedback",
                narrative=feedback,
                metadata={"strategy_type": strategy_type, "iteration_no": session.strategy_package["iteration_no"]},
            )
        self.runtime_bus.publish_agent_event(
            "workflow.strategy.iteration",
            {
                "session_id": str(session_id),
                "iteration_no": session.strategy_package["iteration_no"],
                "strategy_type": session.strategy_package["strategy_type"],
                "iteration_mode": session.strategy_package.get("iteration_mode"),
                "strategy_checks": session.strategy_checks,
            },
        )
        return session

    def approve_strategy(self, session_id: UUID) -> WorkflowSession:
        session = super().approve_strategy(session_id)
        self.workflow_store.approve_strategy(session_id)
        self.workflow_store.save_history_event(session_id, session.history_events[-1])
        self.runtime_bus.publish_agent_event("workflow.strategy.approved", {"session_id": str(session_id)})
        return session

    def set_deployment(self, session_id: UUID, execution_mode: str) -> WorkflowSession:
        session = super().set_deployment(session_id, execution_mode)
        self.workflow_store.set_deployment(session_id, execution_mode)
        self.workflow_store.save_history_event(session_id, session.history_events[-1])
        self.runtime_bus.publish_agent_event("workflow.deployment.updated", {"session_id": str(session_id), "execution_mode": execution_mode})
        return session

    def monitor_signals(self, session_id: UUID) -> list[dict]:
        signals = super().monitor_signals(session_id)
        self.workflow_store.save_monitor_signals(session_id, signals)
        self.runtime_bus.publish_agent_event("workflow.monitors.updated", {"session_id": str(session_id), "signals": len(signals)})
        return signals

    def append_market_snapshot(self, session_id: UUID, snapshot: MarketDataPoint) -> WorkflowSession:
        session = super().append_market_snapshot(session_id, snapshot)
        self.event_writer.write_market_data_points(str(session_id), [snapshot])
        self.workflow_store.save_market_snapshot(session_id, asdict(snapshot))
        self.workflow_store.save_history_event(session_id, session.history_events[-1])
        self.runtime_bus.publish_agent_event(
            "workflow.market.snapshot",
            {"session_id": str(session_id), "symbol": snapshot.symbol, "timeframe": snapshot.timeframe},
        )
        return session

    def append_trade_record(self, session_id: UUID, trade: TradeExecutionRecord) -> WorkflowSession:
        session = super().append_trade_record(session_id, trade)
        self.workflow_store.save_trade_record(session_id, asdict(trade))
        self.workflow_store.save_profile_evolution(session_id, session.profile_evolution or {})
        self.workflow_store.save_history_event(session_id, session.history_events[-1])
        self.memory_store.add_profile_evolution_memory(
            user_id=str(session_id),
            source_type="trade_record",
            narrative=f"{trade.side} {trade.symbol} pnl={trade.realized_pnl_pct:.2f}% note={trade.note or 'none'}",
            metadata={"symbol": trade.symbol, "execution_mode": trade.execution_mode},
        )
        self.runtime_bus.publish_agent_event(
            "workflow.trade.recorded",
            {"session_id": str(session_id), "symbol": trade.symbol, "side": trade.side, "timestamp": datetime.now().isoformat()},
        )
        return session

    def search_intelligence(self, session_id: UUID, query: str, max_documents: int | None = None) -> WorkflowSession:
        session = super().search_intelligence(session_id, query, max_documents)
        self.workflow_store.save_intelligence_documents(session_id, query, session.intelligence_documents)
        self.workflow_store.save_report_snapshot(session_id, session.report_history[-1])
        self.workflow_store.save_history_event(session_id, session.history_events[-1])
        for document in session.intelligence_documents:
            self.memory_store.add_market_intelligence_memory(
                query=query,
                title=document.get("title", ""),
                content=document.get("content", ""),
                metadata={"source": document.get("source", "unknown"), "url": document.get("url", "")},
            )
        self.runtime_bus.publish_agent_event(
            "workflow.intelligence.search",
            {"session_id": str(session_id), "query": query, "documents": len(session.intelligence_documents)},
        )
        return session

    def append_information_events(self, session_id: UUID, events: list[dict]) -> WorkflowSession:
        session = super().append_information_events(session_id, events)
        self.workflow_store.save_information_events(session_id, events)
        self.workflow_store.save_history_event(session_id, session.history_events[-1])
        self.runtime_bus.publish_agent_event(
            "workflow.information_events.recorded",
            {"session_id": str(session_id), "count": len(events)},
        )
        return session

    def execute_programmer_task(
        self,
        session_id: UUID,
        instruction: str,
        target_files: list[str],
        context: str | None = None,
        commit_changes: bool = True,
    ) -> WorkflowSession:
        session = super().execute_programmer_task(session_id, instruction, target_files, context, commit_changes)
        self.workflow_store.save_report_snapshot(session_id, session.report_history[-1])
        self.workflow_store.save_history_event(session_id, session.history_events[-1])
        self.runtime_bus.publish_agent_event(
            "workflow.programmer.run",
            {
                "session_id": str(session_id),
                "status": session.programmer_runs[-1].get("status"),
                "commit_hash": session.programmer_runs[-1].get("commit_hash"),
            },
        )
        return session

    def compose_market_template_campaign(
        self,
        day_count: int = 40,
        required_shapes: list[str] | None = None,
        required_regimes: list[str] | None = None,
        baseline_open: float = 100.0,
        seed: int = 11,
    ) -> list[dict]:
        return self.workflow_store.compose_market_template_campaign(
            day_count=day_count,
            required_shapes=required_shapes,
            required_regimes=required_regimes,
            baseline_open=baseline_open,
            seed=seed,
        )

    def market_template_coverage(self) -> dict:
        return self.workflow_store.market_template_coverage()

    def system_health(self) -> dict:
        payload = super().system_health()
        payload["service_mode"] = "persistent"
        payload["modules"] = [item for item in payload["modules"] if item["name"] != "storage_layer"]
        payload["modules"].extend(
            [
                self._postgres_health(),
                self._timescale_health(),
                self._redis_health(),
                self._qdrant_health(),
                self._module_status("workflow_store", "ok", "Persistent workflow store is attached.", "No action required."),
                self._module_status("runtime_bus", "ok", "Redis runtime bus is attached.", "No action required."),
                self._module_status("memory_store", "ok", "Qdrant behavior memory store is attached.", "No action required."),
            ]
        )
        if any(item["status"] == "error" for item in payload["modules"]):
            payload["status"] = "degraded"
        elif any(item["status"] == "warning" for item in payload["modules"]):
            payload["status"] = "warning"
        return payload

    def _postgres_health(self) -> dict:
        if psycopg is None:
            return self._module_status("postgres", "error", "psycopg is not installed.", "Install psycopg and rebuild the API image.")
        try:
            with psycopg.connect(self.workflow_store.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("select 1")
                    cursor.fetchone()
            return self._module_status("postgres", "ok", "PostgreSQL workflow store is reachable.", "No action required.")
        except Exception as exc:  # pragma: no cover
            return self._module_status("postgres", "error", f"PostgreSQL health check failed: {exc}", "Check SENTINEL_POSTGRES_DSN, database container status, and schema initialization.")

    def _timescale_health(self) -> dict:
        if psycopg is None:
            return self._module_status("timescale", "error", "psycopg is not installed.", "Install psycopg and rebuild the API image.")
        try:
            with psycopg.connect(self.settings.timescale_dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("select 1")
                    cursor.fetchone()
            return self._module_status("timescale", "ok", "TimescaleDB event writer target is reachable.", "No action required.")
        except Exception as exc:  # pragma: no cover
            return self._module_status("timescale", "error", f"TimescaleDB health check failed: {exc}", "Check SENTINEL_TIMESCALE_DSN and TimescaleDB container health.")

    def _redis_health(self) -> dict:
        try:
            pong = self.runtime_bus.client.ping()
            return self._module_status("redis", "ok" if pong else "warning", "Redis runtime bus responded to ping." if pong else "Redis ping returned a non-true response.", "Restart Redis or verify SENTINEL_REDIS_URL if this warning persists.")
        except Exception as exc:  # pragma: no cover
            return self._module_status("redis", "error", f"Redis health check failed: {exc}", "Check SENTINEL_REDIS_URL and Redis container/network state.")

    def _qdrant_health(self) -> dict:
        if QdrantClient is None:
            return self._module_status("qdrant", "error", "qdrant-client is not installed.", "Install qdrant-client and rebuild the API image.")
        try:
            client = QdrantClient(url=self.settings.qdrant_url)
            client.get_collections()
            return self._module_status("qdrant", "ok", "Qdrant vector store is reachable.", "No action required.")
        except Exception as exc:  # pragma: no cover
            return self._module_status("qdrant", "error", f"Qdrant health check failed: {exc}", "Check SENTINEL_QDRANT_URL, collection setup, and Qdrant container state.")
