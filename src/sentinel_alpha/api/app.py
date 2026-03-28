from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import re

from sentinel_alpha.api.schemas import (
    BehaviorEventIn,
    CompleteSimulationRequest,
    SimulationRetrainRequest,
    SimulationMarketAdvanceRequest,
    SimulationMarketInitializeRequest,
    ConfigSingleTestRequest,
    ConfigUpdateRequest,
    CreateSessionRequest,
    DataSourceExpansionRequestIn,
    DataSourceApplyRequest,
    DataSourceRunDeleteRequest,
    DataSourceProviderDeleteRequest,
    DataSourceProviderUpdateRequest,
    DataSourceTestRequest,
    DataSourceRunUpdateRequest,
    DeploymentRequest,
    ProgrammerTaskRequest,
    InformationEventBatchRequest,
    IntelligenceSearchRequest,
    MarketDataLookupRequest,
    MarketSnapshotIn,
    SessionSnapshot,
    StrategyActiveSelectionRequest,
    StrategyIterationRequest,
    TradingTerminalApplyRequest,
    TradingTerminalIntegrationRequestIn,
    TradingTerminalRunDeleteRequest,
    TradingTerminalRunUpdateRequest,
    TradingTerminalTestRequest,
    TradeExecutionIn,
    TradingPreferenceRequest,
    TradeUniverseRequest,
)
from sentinel_alpha.config import get_settings, read_config_payload, write_config_payload, write_config_payload_with_backup
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

    def _provider_env_index_from_cfg(cfg: dict) -> dict[str, dict[str, str]]:
        providers = cfg.get("providers") if isinstance(cfg, dict) else None
        provider_env_index: dict[str, dict[str, str]] = {}
        if not isinstance(providers, dict):
            return provider_env_index
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
        return provider_env_index

    def _sanitize_llm_config(cfg: dict) -> dict:
        provider_env_index = _provider_env_index_from_cfg(cfg)
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
            simulation_market=session.simulation_market,
            trading_preferences=session.trading_preferences,
            trade_universe=session.trade_universe,
            strategy_package=session.strategy_package,
            active_trading_strategy=session.active_trading_strategy,
            strategy_status_summary=session.strategy_status_summary,
            strategy_checks=session.strategy_checks,
            execution_mode=session.execution_mode,
            profile_evolution=session.profile_evolution,
            habit_goal_evolution=session.habit_goal_evolution,
            intelligence_history_analysis=session.intelligence_history_analysis,
            simulation_training_state=session.simulation_training_state,
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
            agent_activity=session.agent_activity,
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
            provider_env_index = _provider_env_index_from_cfg(cfg)
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

    @app.get("/api/sessions/{session_id}/agent-activity")
    def session_agent_activity(session_id: UUID, since: str | None = None, limit: int = 200) -> dict:
        """Fetch incremental agent activity for a single session.

        This is designed for "training progress" UIs: while a long synchronous request (like strategy iteration)
        is running, the browser can poll this endpoint to display real-time agent node logs. No fake progress.
        """
        try:
            # Validate session exists so callers get a consistent 404.
            resolved_service.get_session(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

        session = resolved_service.get_session(session_id)
        raw_events = list(session.agent_activity or [])
        if since:
            try:
                # ISO timestamps compare lexicographically when normalized, but we still guard the filter.
                raw_events = [item for item in raw_events if str(item.get("timestamp") or "") > since]
            except Exception:
                pass
        if limit < 1:
            limit = 1
        if limit > 500:
            limit = 500
        return {"events": raw_events[-limit:]}

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
            path, backup_path = write_config_payload_with_backup(payload.payload)
            fresh_settings = get_settings()
            validation = config_validator.validate(fresh_settings)
            return {
                "status": "saved",
                "config_path": str(path),
                "backup_path": str(backup_path) if backup_path else None,
                "payload": read_config_payload(),
                "validation": validation,
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Config update failed: {exc}") from exc

    @app.post("/api/config/test")
    def test_config(payload: ConfigUpdateRequest | None = None) -> dict:
        try:
            if payload is not None:
                path, backup_path = write_config_payload_with_backup(payload.payload)
            else:
                path = None
                backup_path = None
            fresh_settings = get_settings()
            validation = config_validator.validate(fresh_settings)
            return {
                "status": "tested",
                "config_path": str(path or fresh_settings.config_path),
                "backup_path": str(backup_path) if backup_path else None,
                "validation": validation,
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Config test failed: {exc}") from exc

    @app.post("/api/config/test-item")
    def test_single_config_item(payload: ConfigSingleTestRequest) -> dict:
        try:
            if payload.payload is not None:
                path, backup_path = write_config_payload_with_backup(payload.payload)
            else:
                path = None
                backup_path = None
            fresh_settings = get_settings()
            validation = config_validator.validate_target(fresh_settings, payload.family, payload.provider)
            return {
                "status": "tested",
                "config_path": str(path or fresh_settings.config_path),
                "backup_path": str(backup_path) if backup_path else None,
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

    @app.get("/api/data-source/health")
    def data_source_health_global() -> dict:
        validation = config_validator.validate(get_settings())
        configured_providers = {
            "market_data": market_data.provider_matrix(),
            "fundamentals": market_data.fundamentals_provider_matrix(),
            "dark_pool": market_data.dark_pool_provider_matrix(),
            "options_data": market_data.options_provider_matrix(),
        }
        summary = resolved_service.summarize_data_source_health_payload(
            validation=validation,
            provider_matrix=configured_providers,
            expanded_runs=[],
            overall_status=str(validation.get("status") or "warning"),
        )
        return {
            "status": validation.get("status"),
            "configured_validation": validation,
            "configured_providers": configured_providers,
            "summary": summary,
        }

    @app.post("/api/config/data-source/provider")
    def update_data_source_provider(payload: DataSourceProviderUpdateRequest) -> dict:
        try:
            config_payload = read_config_payload()
            family_section = config_payload.setdefault(payload.family, {})
            providers = family_section.setdefault("providers", {})
            enabled_providers = list(family_section.get("enabled_providers", []))
            provider_config = dict(providers.get(payload.provider, {}))
            provider_config["enabled"] = payload.enabled
            if payload.base_url is not None:
                provider_config["base_url"] = payload.base_url
            if payload.base_path is not None:
                provider_config["base_path"] = payload.base_path
            if payload.api_key_envs:
                provider_config["api_key_envs"] = list(payload.api_key_envs)
            if payload.docs_url is not None:
                provider_config["docs_url"] = payload.docs_url
            if payload.quote_filename is not None:
                provider_config["quote_filename"] = payload.quote_filename
            if payload.history_filename is not None:
                provider_config["history_filename"] = payload.history_filename
            if payload.financials_filename is not None:
                provider_config["financials_filename"] = payload.financials_filename
            if payload.dark_pool_filename is not None:
                provider_config["dark_pool_filename"] = payload.dark_pool_filename
            if payload.options_filename is not None:
                provider_config["options_filename"] = payload.options_filename
            providers[payload.provider] = provider_config
            if payload.enabled and payload.provider not in enabled_providers:
                enabled_providers.append(payload.provider)
            if not payload.enabled and payload.provider in enabled_providers:
                enabled_providers = [item for item in enabled_providers if item != payload.provider]
            family_section["enabled_providers"] = enabled_providers
            if payload.set_as_default:
                family_section["default_provider"] = payload.provider
            path, backup_path = write_config_payload_with_backup(config_payload)
            fresh_settings = get_settings()
            validation = config_validator.validate_target(fresh_settings, payload.family, payload.provider)
            return {
                "status": "saved",
                "config_path": str(path),
                "backup_path": str(backup_path) if backup_path else None,
                "family": payload.family,
                "provider": payload.provider,
                "payload": read_config_payload(),
                "validation": validation,
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Data-source provider update failed: {exc}") from exc

    @app.post("/api/config/data-source/provider/delete")
    def delete_data_source_provider(payload: DataSourceProviderDeleteRequest) -> dict:
        try:
            config_payload = read_config_payload()
            family_section = config_payload.setdefault(payload.family, {})
            providers = family_section.setdefault("providers", {})
            if payload.provider not in providers:
                raise ValueError(f"{payload.provider} is not defined under {payload.family}.")
            providers.pop(payload.provider, None)
            enabled_providers = [item for item in list(family_section.get("enabled_providers", [])) if item != payload.provider]
            family_section["enabled_providers"] = enabled_providers
            if family_section.get("default_provider") == payload.provider:
                family_section["default_provider"] = enabled_providers[0] if enabled_providers else ""
            path, backup_path = write_config_payload_with_backup(config_payload)
            fresh_settings = get_settings()
            validation = config_validator.validate(fresh_settings)
            return {
                "status": "deleted",
                "config_path": str(path),
                "backup_path": str(backup_path) if backup_path else None,
                "family": payload.family,
                "provider": payload.provider,
                "payload": read_config_payload(),
                "validation": validation,
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Data-source provider delete failed: {exc}") from exc

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
                    price_drawdown_pct=float(payload.price_drawdown_pct or 0.0),
                    action=payload.action,
                    noise_level=float(payload.noise_level or 0.0),
                    sentiment_pressure=float(payload.sentiment_pressure or 0.0),
                    latency_seconds=float(payload.latency_seconds or 0.0),
                    chart_focus_seconds=(
                        float(payload.chart_focus_seconds)
                        if payload.chart_focus_seconds is not None
                        else None
                    ),
                    loss_refresh_count=payload.loss_refresh_count,
                    loss_refresh_drawdown_trigger_pct=payload.loss_refresh_drawdown_trigger_pct,
                    manual_intervention_count=payload.manual_intervention_count,
                    manual_intervention_rate=payload.manual_intervention_rate,
                    trust_decay_score=payload.trust_decay_score,
                    execution_status=payload.execution_status or ("hold" if payload.action == "hold" else "filled"),
                    execution_reason=payload.execution_reason,
                ),
            )
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    @app.post("/api/sessions/{session_id}/simulation/market/initialize", response_model=SessionSnapshot)
    def initialize_simulation_market(session_id: UUID, payload: SimulationMarketInitializeRequest) -> SessionSnapshot:
        try:
            resolved_service.initialize_simulation_market(
                session_id=session_id,
                symbol=payload.symbol,
                provider=payload.provider,
                daily_lookback=payload.daily_lookback,
                intraday_lookback=payload.intraday_lookback,
                intraday_interval=payload.intraday_interval,
            )
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/simulation/market/advance", response_model=SessionSnapshot)
    def advance_simulation_market(session_id: UUID, payload: SimulationMarketAdvanceRequest) -> SessionSnapshot:
        try:
            resolved_service.advance_simulation_market(
                session_id=session_id,
                steps=payload.steps,
            )
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/simulation/complete", response_model=SessionSnapshot)
    def complete_simulation(session_id: UUID, payload: CompleteSimulationRequest) -> SessionSnapshot:
        try:
            resolved_service.complete_simulation(session_id, payload.symbol)
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/simulation/retrain", response_model=SessionSnapshot)
    def retrain_simulation(session_id: UUID, payload: SimulationRetrainRequest) -> SessionSnapshot:
        try:
            resolved_service.retrain_simulation_profile(session_id, payload.symbol)
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
                strategy_method=payload.strategy_method,
                strategy_description=payload.strategy_description,
                auto_iterations=payload.auto_iterations,
                iteration_mode=payload.iteration_mode,
                objective_metric=payload.objective_metric,
                objective_targets={
                    "target_return_pct": payload.target_return_pct,
                    "target_win_rate_pct": payload.target_win_rate_pct,
                    "target_drawdown_pct": payload.target_drawdown_pct,
                    "target_max_loss_pct": payload.target_max_loss_pct,
                },
                training_window={
                    "start": payload.training_start_date.isoformat() if payload.training_start_date else None,
                    "end": payload.training_end_date.isoformat() if payload.training_end_date else None,
                },
                trade_execution_limits={
                    "max_trade_allocation_pct": payload.max_trade_allocation_pct,
                    "max_trade_amount": payload.max_trade_amount,
                },
            )
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/strategy/active", response_model=SessionSnapshot)
    def set_active_strategy(session_id: UUID, payload: StrategyActiveSelectionRequest) -> SessionSnapshot:
        try:
            resolved_service.set_active_trading_strategy(session_id, strategy_ref=payload.strategy_ref)
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
                interface_documentation=payload.interface_documentation,
                api_key=payload.api_key,
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

    @app.post("/api/sessions/{session_id}/data-source/test", response_model=SessionSnapshot)
    def test_data_source(session_id: UUID, payload: DataSourceTestRequest) -> SessionSnapshot:
        try:
            resolved_service.test_data_source_expansion(
                session_id=session_id,
                run_id=payload.run_id,
                symbol=payload.symbol,
                api_key=payload.api_key,
            )
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/sessions/{session_id}/data-source/health")
    def get_session_data_source_health(session_id: UUID) -> dict:
        try:
            return resolved_service.data_source_health(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/data-source/update", response_model=SessionSnapshot)
    def update_data_source(session_id: UUID, payload: DataSourceRunUpdateRequest) -> SessionSnapshot:
        try:
            resolved_service.update_data_source_expansion(
                session_id,
                run_id=payload.run_id,
                interface_documentation=payload.interface_documentation,
                api_key=payload.api_key,
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

    @app.post("/api/sessions/{session_id}/data-source/delete", response_model=SessionSnapshot)
    def delete_data_source(session_id: UUID, payload: DataSourceRunDeleteRequest) -> SessionSnapshot:
        try:
            resolved_service.delete_data_source_expansion(session_id, run_id=payload.run_id)
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
                interface_documentation=payload.interface_documentation,
                api_key=payload.api_key,
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
                trade_records_endpoint=payload.trade_records_endpoint,
                docs_summary=payload.docs_summary,
                user_notes=payload.user_notes,
                response_field_map=payload.response_field_map,
            )
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/terminal/update", response_model=SessionSnapshot)
    def update_trading_terminal(session_id: UUID, payload: TradingTerminalRunUpdateRequest) -> SessionSnapshot:
        try:
            resolved_service.update_trading_terminal_integration(
                session_id=session_id,
                run_id=payload.run_id,
                interface_documentation=payload.interface_documentation,
                api_key=payload.api_key,
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
                trade_records_endpoint=payload.trade_records_endpoint,
                docs_summary=payload.docs_summary,
                user_notes=payload.user_notes,
                response_field_map=payload.response_field_map,
            )
            return snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/terminal/delete", response_model=SessionSnapshot)
    def delete_trading_terminal(session_id: UUID, payload: TradingTerminalRunDeleteRequest) -> SessionSnapshot:
        try:
            resolved_service.delete_trading_terminal_integration(session_id=session_id, run_id=payload.run_id)
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
