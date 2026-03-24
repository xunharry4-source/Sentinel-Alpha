from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import re

from sentinel_alpha.api.schemas import (
    BehaviorEventIn,
    CompleteSimulationRequest,
    ConfigSingleTestRequest,
    ConfigUpdateRequest,
    CreateSessionRequest,
    DataSourceExpansionRequestIn,
    DataSourceApplyRequest,
    DeploymentRequest,
    ProgrammerTaskRequest,
    InformationEventBatchRequest,
    IntelligenceSearchRequest,
    MarketDataLookupRequest,
    MarketSnapshotIn,
    SessionSnapshot,
    StrategyIterationRequest,
    TradingTerminalApplyRequest,
    TradingTerminalIntegrationRequestIn,
    TradingTerminalTestRequest,
    TradeExecutionIn,
    TradingPreferenceRequest,
    TradeUniverseRequest,
)
from sentinel_alpha.config import get_settings, read_config_payload, write_config_payload
from sentinel_alpha.api.workflow_service import WorkflowService
from sentinel_alpha.domain.models import BehaviorEvent, MarketDataPoint, TradeExecutionRecord
from sentinel_alpha.infra.config_validator import ConfigValidator
from sentinel_alpha.infra.free_market_data import FreeMarketDataService
from sentinel_alpha.infra.observability import initialize_observability

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
    market_data = FreeMarketDataService(settings)
    config_validator = ConfigValidator()
    app.state.observability = initialize_observability(app, settings)

    def _sanitize_llm_env_names(payload: object, provider_env_index: dict[str, dict[str, str]]) -> object:
        """Mask configured env var names in externally exposed payloads.

        We preserve the fact that multiple credentials exist and which numbered credential was used
        (provider#keyN), but we do not leak the actual environment variable names.
        """

        def _mask_env_name(raw: object) -> object:
            if raw is None:
                return None
            text = str(raw).strip()
            if not text:
                return text
            for provider, mapping in provider_env_index.items():
                if text in mapping:
                    return mapping[text]
            # Keep non-env style labels (like "google#invalid_1") but redact anything that looks like a secret.
            if re.fullmatch(r"[A-Z_][A-Z0-9_]*", text):
                return "<redacted_env>"
            if "AIza" in text or len(text) > 64:
                return "<redacted>"
            return text

        if isinstance(payload, dict):
            sanitized: dict = {}
            for key, value in payload.items():
                if key in {
                    "api_key_envs",
                    "active_api_key_env",
                    "attempted_api_key_envs",
                    "active_api_key_envs",
                    "available_api_key_envs",
                    "configured_api_key_envs",
                }:
                    if isinstance(value, list):
                        sanitized[key] = [_mask_env_name(item) for item in value]
                        continue
                    sanitized[key] = _mask_env_name(value)
                    continue
                sanitized[key] = _sanitize_llm_env_names(value, provider_env_index)
            return sanitized
        if isinstance(payload, list):
            return [_sanitize_llm_env_names(item, provider_env_index) for item in payload]
        return payload

    def _sanitize_llm_config(cfg: dict) -> dict:
        providers = cfg.get("providers") if isinstance(cfg, dict) else None
        provider_env_index: dict[str, dict[str, str]] = {}
        if isinstance(providers, dict):
            for provider, info in providers.items():
                if not isinstance(info, dict):
                    continue
                raw_envs = info.get("api_key_envs")
                if not isinstance(raw_envs, list):
                    continue
                mapping: dict[str, str] = {}
                for idx, raw in enumerate(raw_envs, 1):
                    name = str(raw).strip()
                    if not name:
                        continue
                    mapping[name] = f"{provider}#key{idx}"
                provider_env_index[str(provider)] = mapping
        sanitized = _sanitize_llm_env_names(cfg, provider_env_index)
        return sanitized if isinstance(sanitized, dict) else cfg

    def health_payload() -> dict:
        backend = str(getattr(resolved_service, "session_store_backend", "memory"))
        database_status = "configured" if backend in {"redis", "file"} else "not_configured"
        database_detail = (
            f"Workflow sessions persist via {backend} backend."
            if database_status == "configured"
            else "In-memory workflow service is active. No persistence backend is attached."
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
            "observability": app.state.observability,
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
            behavioral_user_report=session.behavioral_user_report,
            behavioral_system_report=session.behavioral_system_report,
            trading_preferences=session.trading_preferences,
            trade_universe=session.trade_universe,
            strategy_package=session.strategy_package,
            strategy_checks=session.strategy_checks,
            execution_mode=session.execution_mode,
            profile_evolution=session.profile_evolution,
            market_snapshots=session.market_snapshots,
            trade_records=session.trade_records,
            strategy_feedback_log=session.strategy_feedback_log,
            strategy_training_log=session.strategy_training_log,
            intelligence_documents=session.intelligence_documents,
            information_events=session.information_events,
            data_bundles=session.data_bundles,
            history_events=session.history_events,
            report_history=session.report_history,
            intelligence_runs=session.intelligence_runs,
            programmer_runs=session.programmer_runs,
            data_source_runs=session.data_source_runs,
            terminal_integration_runs=session.terminal_integration_runs,
            financials_runs=session.financials_runs,
            dark_pool_runs=session.dark_pool_runs,
            options_runs=session.options_runs,
            token_usage=resolved_service.llm_runtime.usage_snapshot(),
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
        # Mask any credential env var names that might appear in token usage snapshots.
        health = resolved_service.system_health()
        try:
            cfg = resolved_service.llm_config()
            provider_index = _sanitize_llm_config(cfg)
            # Use the already-built provider mapping from the sanitized llm-config to mask health.
            providers = provider_index.get("providers") if isinstance(provider_index, dict) else None
            provider_env_index: dict[str, dict[str, str]] = {}
            if isinstance(providers, dict):
                for provider, info in providers.items():
                    if not isinstance(info, dict):
                        continue
                    # Here api_key_envs are already masked as provider#keyN; build a "no-op" mapping.
                    mapping: dict[str, str] = {}
                    raw_envs = info.get("api_key_envs")
                    if isinstance(raw_envs, list):
                        for raw in raw_envs:
                            name = str(raw).strip()
                            if name:
                                mapping[name] = name
                    provider_env_index[str(provider)] = mapping
            return _sanitize_llm_env_names(health, provider_env_index)  # type: ignore[return-value]
        except Exception:
            return health

    @app.get("/api/llm-config")
    def llm_config() -> dict:
        cfg = resolved_service.llm_config()
        try:
            return _sanitize_llm_config(cfg)
        except Exception:
            return cfg

    @app.get("/api/config")
    def get_config() -> dict:
        def _sanitize(obj):
            if isinstance(obj, dict):
                sanitized = {}
                for key, value in obj.items():
                    if key == "api_key_envs" and isinstance(value, list):
                        rendered = []
                        for item in value:
                            raw = str(item or "").strip()
                            if re.fullmatch(r"[A-Z_][A-Z0-9_]*", raw):
                                rendered.append(raw)
                            elif raw:
                                # Never return inline secrets or invalid config entries.
                                rendered.append("<redacted>")
                        sanitized[key] = rendered
                        continue
                    sanitized[key] = _sanitize(value)
                return sanitized
            if isinstance(obj, list):
                return [_sanitize(item) for item in obj]
            return obj

        payload = _sanitize(read_config_payload())
        validation = config_validator.validate(get_settings())
        return {"payload": payload, "validation": validation}

    @app.post("/api/config")
    def update_config(payload: ConfigUpdateRequest) -> dict:
        try:
            path = write_config_payload(payload.payload)
            fresh_settings = get_settings()
            validation = config_validator.validate(fresh_settings)
            return {
                "status": "saved",
                "config_path": str(path),
                "payload": read_config_payload(),
                "validation": validation,
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Config update failed: {exc}") from exc

    @app.post("/api/config/test")
    def test_config(payload: ConfigUpdateRequest | None = None) -> dict:
        try:
            if payload is not None:
                path = write_config_payload(payload.payload)
            else:
                path = None
            fresh_settings = get_settings()
            validation = config_validator.validate(fresh_settings)
            return {
                "status": "tested",
                "config_path": str(path or fresh_settings.config_path),
                "validation": validation,
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Config test failed: {exc}") from exc

    @app.post("/api/config/test-item")
    def test_single_config_item(payload: ConfigSingleTestRequest) -> dict:
        try:
            if payload.payload is not None:
                path = write_config_payload(payload.payload)
            else:
                path = None
            fresh_settings = get_settings()
            validation = config_validator.validate_target(fresh_settings, payload.family, payload.provider)
            return {
                "status": "tested",
                "config_path": str(path or fresh_settings.config_path),
                "validation": validation,
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Single config test failed: {exc}") from exc

    @app.get("/api/market-template-campaign")
    def market_template_campaign(
        day_count: int = 40,
        required_shapes: str | None = None,
        required_regimes: str | None = None,
        baseline_open: float = 100.0,
        seed: int = 11,
    ) -> dict:
        shapes = [item.strip() for item in required_shapes.split(",")] if required_shapes else None
        regimes = [item.strip() for item in required_regimes.split(",")] if required_regimes else None
        days = resolved_service.compose_market_template_campaign(
            day_count=day_count,
            required_shapes=shapes,
            required_regimes=regimes,
            baseline_open=baseline_open,
            seed=seed,
        )
        return {"days": days, "day_count": len(days), "baseline_open": baseline_open, "seed": seed}

    @app.get("/api/market-template-coverage")
    def market_template_coverage() -> dict:
        return resolved_service.market_template_coverage()

    @app.get("/api/market-data/providers")
    def market_data_providers() -> dict:
        return {
            "default_provider": settings.market_data_default_provider,
            "providers": market_data.provider_matrix(),
            "fundamentals_default_provider": settings.fundamentals_default_provider,
            "fundamentals_providers": market_data.fundamentals_provider_matrix(),
            "dark_pool_default_provider": settings.dark_pool_default_provider,
            "dark_pool_providers": market_data.dark_pool_provider_matrix(),
            "options_default_provider": settings.options_default_provider,
            "options_providers": market_data.options_provider_matrix(),
        }

    @app.get("/api/market-data/quote")
    def market_data_quote(symbol: str, provider: str | None = None) -> dict:
        try:
            return market_data.fetch_quote(symbol=symbol, provider=provider)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Market data quote request failed: {exc}") from exc

    @app.get("/api/market-data/history")
    def market_data_history(
        symbol: str,
        interval: str = "1d",
        lookback: str = "6mo",
        provider: str | None = None,
    ) -> dict:
        try:
            return market_data.fetch_history(symbol=symbol, interval=interval, lookback=lookback, provider=provider)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Market data history request failed: {exc}") from exc

    @app.get("/api/market-data/financials")
    def market_data_financials(symbol: str, provider: str | None = None) -> dict:
        try:
            return market_data.fetch_financials(symbol=symbol, provider=provider)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Fundamentals request failed: {exc}") from exc

    @app.get("/api/market-data/dark-pool")
    def market_data_dark_pool(symbol: str, provider: str | None = None) -> dict:
        try:
            return market_data.fetch_dark_pool(symbol=symbol, provider=provider)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Dark pool request failed: {exc}") from exc

    @app.get("/api/market-data/options")
    def market_data_options(symbol: str, provider: str | None = None, expiration: str | None = None) -> dict:
        try:
            return market_data.fetch_options(symbol=symbol, provider=provider, expiration=expiration)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Options request failed: {exc}") from exc

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
                    execution_status=payload.execution_status,
                    execution_reason=payload.execution_reason,
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
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

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
            resolved_service.iterate_strategy(
                session_id,
                payload.feedback,
                payload.strategy_type,
                auto_iterations=payload.auto_iterations,
                iteration_mode=payload.iteration_mode,
                objective_metric=payload.objective_metric,
                objective_targets={
                    "target_return_pct": payload.target_return_pct,
                    "target_win_rate_pct": payload.target_win_rate_pct,
                    "target_drawdown_pct": payload.target_drawdown_pct,
                    "target_max_loss_pct": payload.target_max_loss_pct,
                },
            )
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

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
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/intelligence/financials", response_model=SessionSnapshot)
    def fetch_financials_data(session_id: UUID, payload: MarketDataLookupRequest) -> SessionSnapshot:
        try:
            resolved_service.fetch_financials_data(session_id, payload.symbol, payload.provider)
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/intelligence/dark-pool", response_model=SessionSnapshot)
    def fetch_dark_pool_data(session_id: UUID, payload: MarketDataLookupRequest) -> SessionSnapshot:
        try:
            resolved_service.fetch_dark_pool_data(session_id, payload.symbol, payload.provider)
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/intelligence/options", response_model=SessionSnapshot)
    def fetch_options_data(session_id: UUID, payload: MarketDataLookupRequest) -> SessionSnapshot:
        try:
            resolved_service.fetch_options_data(session_id, payload.symbol, payload.provider, payload.expiration)
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/information-events", response_model=SessionSnapshot)
    def append_information_events(session_id: UUID, payload: InformationEventBatchRequest) -> SessionSnapshot:
        try:
            resolved_service.append_information_events(
                session_id,
                [
                    {
                        "channel": item.channel,
                        "source": item.source,
                        "title": item.title,
                        "body": item.body,
                        "trading_day": item.trading_day,
                        "author": item.author,
                        "handle": item.handle,
                        "info_tag": item.info_tag,
                        "sentiment_score": item.sentiment_score,
                        "metadata": item.metadata,
                    }
                    for item in payload.events
                ],
            )
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

    @app.post("/api/sessions/{session_id}/programmer/execute", response_model=SessionSnapshot)
    def execute_programmer_task(session_id: UUID, payload: ProgrammerTaskRequest) -> SessionSnapshot:
        try:
            resolved_service.execute_programmer_task(
                session_id,
                payload.instruction,
                payload.target_files,
                payload.context,
                payload.commit_changes,
            )
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/data-source/expand", response_model=SessionSnapshot)
    def expand_data_source(session_id: UUID, payload: DataSourceExpansionRequestIn) -> SessionSnapshot:
        try:
            resolved_service.expand_data_source(
                session_id=session_id,
                provider_name=payload.provider_name,
                category=payload.category,
                base_url=payload.base_url,
                api_key_envs=payload.api_key_envs,
                docs_summary=payload.docs_summary,
                docs_url=payload.docs_url,
                sample_endpoint=payload.sample_endpoint,
                auth_style=payload.auth_style,
                response_format=payload.response_format,
            )
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/data-source/apply", response_model=SessionSnapshot)
    def apply_data_source(session_id: UUID, payload: DataSourceApplyRequest) -> SessionSnapshot:
        try:
            resolved_service.apply_data_source_expansion(
                session_id=session_id,
                run_id=payload.run_id,
                commit_changes=payload.commit_changes,
            )
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/terminal/expand", response_model=SessionSnapshot)
    def expand_trading_terminal(session_id: UUID, payload: TradingTerminalIntegrationRequestIn) -> SessionSnapshot:
        try:
            resolved_service.expand_trading_terminal(
                session_id=session_id,
                terminal_name=payload.terminal_name,
                terminal_type=payload.terminal_type,
                official_docs_url=payload.official_docs_url,
                docs_search_url=payload.docs_search_url,
                api_base_url=payload.api_base_url,
                api_key_envs=payload.api_key_envs,
                auth_style=payload.auth_style,
                order_endpoint=payload.order_endpoint,
                cancel_endpoint=payload.cancel_endpoint,
                order_status_endpoint=payload.order_status_endpoint,
                positions_endpoint=payload.positions_endpoint,
                balances_endpoint=payload.balances_endpoint,
                docs_summary=payload.docs_summary,
                user_notes=payload.user_notes,
                response_field_map=payload.response_field_map,
            )
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/terminal/apply", response_model=SessionSnapshot)
    def apply_trading_terminal(session_id: UUID, payload: TradingTerminalApplyRequest) -> SessionSnapshot:
        try:
            resolved_service.apply_trading_terminal_integration(
                session_id=session_id,
                run_id=payload.run_id,
                commit_changes=payload.commit_changes,
            )
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/terminal/test", response_model=SessionSnapshot)
    def test_trading_terminal(session_id: UUID, payload: TradingTerminalTestRequest) -> SessionSnapshot:
        try:
            resolved_service.test_trading_terminal_integration(
                session_id=session_id,
                run_id=payload.run_id,
            )
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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
            return {
                "behavioral_report": session.behavioral_report,
                "behavioral_user_report": session.behavioral_user_report,
                "behavioral_system_report": session.behavioral_system_report,
            }
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    @app.get("/api/sessions/{session_id}/profile-evolution-json")
    def get_profile_evolution_json(session_id: UUID) -> dict:
        try:
            session = resolved_service.get_session(session_id)
            return {"profile_evolution": session.profile_evolution}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    @app.get("/api/sessions/{session_id}/history")
    def get_session_history(session_id: UUID) -> dict:
        try:
            return {"history_events": resolved_service.history(session_id)}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    @app.get("/api/sessions/{session_id}/reports")
    def get_session_reports(session_id: UUID) -> dict:
        try:
            return {"report_history": resolved_service.reports(session_id)}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    return app


app = create_app()
