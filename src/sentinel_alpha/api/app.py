from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from sentinel_alpha.api.schemas import (
    BehaviorEventIn,
    CompleteSimulationRequest,
    CreateSessionRequest,
    DeploymentRequest,
    IntelligenceSearchRequest,
    MarketSnapshotIn,
    SessionSnapshot,
    StrategyIterationRequest,
    TradeExecutionIn,
    TradingPreferenceRequest,
    TradeUniverseRequest,
)
from sentinel_alpha.config import get_settings
from sentinel_alpha.api.workflow_service import WorkflowService
from sentinel_alpha.domain.models import BehaviorEvent, MarketDataPoint, TradeExecutionRecord

def create_app(service: WorkflowService | None = None) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=f"{settings.app_name} API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    resolved_service = service or WorkflowService()

    def health_payload() -> dict:
        persistent = hasattr(resolved_service, "workflow_store")
        database_status = "configured" if persistent else "not_configured"
        database_detail = (
            "Persistent workflow service is enabled. PostgreSQL, TimescaleDB, Redis, and Qdrant adapters are attached."
            if persistent
            else "In-memory workflow service is active. No external database layer is attached."
        )
        return {
            "status": "ok",
            "service": "sentinel-alpha-api",
            "frontend": {
                "status": "ok",
                "detail": f"Static web client is expected to connect from configured origins: {', '.join(settings.api_cors_origins)}.",
            },
            "api": {
                "status": "ok",
                "detail": f"FastAPI workflow service is running in {settings.app_mode} mode from {settings.config_path}.",
            },
            "database": {
                "status": database_status,
                "detail": database_detail,
            },
        }

    def snapshot(session_id: UUID) -> SessionSnapshot:
        session = resolved_service.get_session(session_id)
        return SessionSnapshot(
            session_id=session.session_id,
            user_name=session.user_name,
            phase=session.phase,
            status=session.status,
            starting_capital=session.starting_capital,
            scenarios=session.scenarios,
            behavioral_report=session.behavioral_report,
            trading_preferences=session.trading_preferences,
            trade_universe=session.trade_universe,
            strategy_package=session.strategy_package,
            strategy_checks=session.strategy_checks,
            execution_mode=session.execution_mode,
            profile_evolution=session.profile_evolution,
            market_snapshots=session.market_snapshots,
            trade_records=session.trade_records,
            strategy_feedback_log=session.strategy_feedback_log,
            intelligence_documents=session.intelligence_documents,
            monitors=resolved_service.monitor_signals(session_id),
        )

    @app.post("/api/sessions", response_model=SessionSnapshot)
    def create_session(payload: CreateSessionRequest) -> SessionSnapshot:
        session = resolved_service.create_session(payload.user_name, payload.starting_capital)
        return snapshot(session.session_id)

    @app.get("/api/health")
    def health() -> dict:
        return health_payload()

    @app.get("/api/system-health")
    def system_health() -> dict:
        return resolved_service.system_health()

    @app.get("/api/sessions/{session_id}", response_model=SessionSnapshot)
    def get_session(session_id: UUID) -> SessionSnapshot:
        try:
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    @app.post("/api/sessions/{session_id}/generate-scenarios", response_model=SessionSnapshot)
    def generate_scenarios(session_id: UUID) -> SessionSnapshot:
        try:
            resolved_service.generate_scenarios(session_id)
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    @app.post("/api/sessions/{session_id}/simulation/events", response_model=SessionSnapshot)
    def append_behavior_event(session_id: UUID, payload: BehaviorEventIn) -> SessionSnapshot:
        try:
            resolved_service.append_behavior_event(
                session_id,
                BehaviorEvent(
                    scenario_id=payload.scenario_id,
                    price_drawdown_pct=payload.price_drawdown_pct,
                    action=payload.action,
                    noise_level=payload.noise_level,
                    sentiment_pressure=payload.sentiment_pressure,
                    latency_seconds=payload.latency_seconds,
                ),
            )
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    @app.post("/api/sessions/{session_id}/simulation/complete", response_model=SessionSnapshot)
    def complete_simulation(session_id: UUID, payload: CompleteSimulationRequest) -> SessionSnapshot:
        try:
            resolved_service.complete_simulation(session_id, payload.symbol)
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/trading-preferences", response_model=SessionSnapshot)
    def set_trading_preferences(session_id: UUID, payload: TradingPreferenceRequest) -> SessionSnapshot:
        try:
            resolved_service.set_trading_preferences(
                session_id,
                payload.trading_frequency,
                payload.preferred_timeframe,
                payload.rationale,
            )
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    @app.post("/api/sessions/{session_id}/trade-universe", response_model=SessionSnapshot)
    def set_trade_universe(session_id: UUID, payload: TradeUniverseRequest) -> SessionSnapshot:
        try:
            resolved_service.set_trade_universe(session_id, payload.input_type, payload.symbols, payload.allow_overfit_override)
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    @app.post("/api/sessions/{session_id}/strategy/iterate", response_model=SessionSnapshot)
    def iterate_strategy(session_id: UUID, payload: StrategyIterationRequest) -> SessionSnapshot:
        try:
            resolved_service.iterate_strategy(session_id, payload.feedback, payload.strategy_type)
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/market-snapshots", response_model=SessionSnapshot)
    def append_market_snapshot(session_id: UUID, payload: MarketSnapshotIn) -> SessionSnapshot:
        try:
            resolved_service.append_market_snapshot(
                session_id,
                MarketDataPoint(
                    timestamp=datetime.now(timezone.utc),
                    symbol=payload.symbol,
                    timeframe=payload.timeframe,
                    open_price=payload.open_price,
                    high_price=payload.high_price,
                    low_price=payload.low_price,
                    close_price=payload.close_price,
                    volume=payload.volume,
                    source=payload.source,
                    regime_tag=payload.regime_tag,
                ),
            )
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    @app.post("/api/sessions/{session_id}/intelligence/search", response_model=SessionSnapshot)
    def search_intelligence(session_id: UUID, payload: IntelligenceSearchRequest) -> SessionSnapshot:
        try:
            resolved_service.search_intelligence(session_id, payload.query, payload.max_documents)
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    @app.post("/api/sessions/{session_id}/trade-executions", response_model=SessionSnapshot)
    def append_trade_execution(session_id: UUID, payload: TradeExecutionIn) -> SessionSnapshot:
        try:
            resolved_service.append_trade_record(
                session_id,
                TradeExecutionRecord(
                    timestamp=datetime.now(timezone.utc),
                    symbol=payload.symbol,
                    side=payload.side,
                    quantity=payload.quantity,
                    price=payload.price,
                    notional=payload.notional,
                    execution_mode=payload.execution_mode,
                    strategy_version=payload.strategy_version,
                    realized_pnl_pct=payload.realized_pnl_pct,
                    user_initiated=payload.user_initiated,
                    note=payload.note,
                ),
            )
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    @app.post("/api/sessions/{session_id}/strategy/approve", response_model=SessionSnapshot)
    def approve_strategy(session_id: UUID) -> SessionSnapshot:
        try:
            resolved_service.approve_strategy(session_id)
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/deployment", response_model=SessionSnapshot)
    def set_deployment(session_id: UUID, payload: DeploymentRequest) -> SessionSnapshot:
        try:
            resolved_service.set_deployment(session_id, payload.execution_mode)
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    @app.get("/api/sessions/{session_id}/monitors")
    def get_monitors(session_id: UUID) -> dict:
        try:
            return {"signals": resolved_service.monitor_signals(session_id)}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    @app.get("/api/sessions/{session_id}/behavioral-report-json")
    def get_behavioral_report_json(session_id: UUID) -> dict:
        try:
            session = resolved_service.get_session(session_id)
            return {"behavioral_report": session.behavioral_report}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    @app.get("/api/sessions/{session_id}/profile-evolution-json")
    def get_profile_evolution_json(session_id: UUID) -> dict:
        try:
            session = resolved_service.get_session(session_id)
            return {"profile_evolution": session.profile_evolution}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    return app


app = create_app()
