from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
from urllib.error import URLError
from uuid import UUID, uuid4

from sentinel_alpha.agents.behavioral_profiler import BehavioralProfilerAgent
from sentinel_alpha.agents.data_source_expansion_agent import DataSourceExpansionAgent, DataSourceExpansionRequest
from sentinel_alpha.agents.intent_aligner import IntentAlignerAgent
from sentinel_alpha.agents.intelligence_agent import IntelligenceAgent
from sentinel_alpha.agents.market_asset_monitor_agent import MarketAssetMonitorAgent
from sentinel_alpha.agents.noise_agent import NoiseAgent
from sentinel_alpha.agents.portfolio_manager import PortfolioManagerAgent
from sentinel_alpha.agents.programmer_agent import ProgrammerAgent
from sentinel_alpha.agents.risk_guardian import RiskGuardianAgent
from sentinel_alpha.agents.scenario_director import ScenarioDirectorAgent
from sentinel_alpha.agents.strategy_evolver import StrategyEvolverAgent
from sentinel_alpha.agents.strategy_integrity_checker import StrategyIntegrityCheckerAgent
from sentinel_alpha.agents.strategy_monitor_agent import StrategyMonitorAgent
from sentinel_alpha.agents.strategy_stress_checker import StrategyStressCheckerAgent
from sentinel_alpha.agents.trading_terminal_integration_agent import TradingTerminalIntegrationAgent, TradingTerminalIntegrationRequest
from sentinel_alpha.agents.user_monitor_agent import UserMonitorAgent
from dataclasses import asdict

from sentinel_alpha.config import get_settings
from sentinel_alpha.analysis import SessionFeaturePipeline
from sentinel_alpha.backtesting import DefaultStrategyMetricsEngine
from sentinel_alpha.backtesting import SimpleBacktestEngine
from sentinel_alpha.infra.free_market_data import FreeMarketDataService
from sentinel_alpha.infra.llm_runtime import LLMRuntime
from sentinel_alpha.strategies.registry import StrategyRegistry
from sentinel_alpha.domain.models import BehaviorEvent, MarketDataPoint, MarketSnapshot, ProfileEvolutionEvent, TradeExecutionRecord, UserProfile
from sentinel_alpha.domain.models import BehavioralReport
from sentinel_alpha.research.scenario_generator import ScenarioGenerator


@dataclass
class WorkflowSession:
    session_id: UUID
    user_name: str
    starting_capital: float
    phase: str = "created"
    status: str = "active"
    scenarios: list[dict] = field(default_factory=list)
    behavior_events: list[BehaviorEvent] = field(default_factory=list)
    behavioral_report: dict | None = None
    behavioral_user_report: dict | None = None
    behavioral_system_report: dict | None = None
    simulation_market: dict | None = None
    trading_preferences: dict | None = None
    trade_universe: dict | None = None
    strategy_package: dict | None = None
    strategy_checks: list[dict] = field(default_factory=list)
    execution_mode: str | None = None
    profile_evolution: dict | None = None
    market_snapshots: list[dict] = field(default_factory=list)
    trade_records: list[dict] = field(default_factory=list)
    strategy_feedback_log: list[dict] = field(default_factory=list)
    strategy_training_log: list[dict] = field(default_factory=list)
    scenario_packages: list[dict] = field(default_factory=list)
    intelligence_documents: list[dict] = field(default_factory=list)
    information_events: list[dict] = field(default_factory=list)
    data_bundles: list[dict] = field(default_factory=list)
    history_events: list[dict] = field(default_factory=list)
    report_history: list[dict] = field(default_factory=list)
    intelligence_runs: list[dict] = field(default_factory=list)
    programmer_runs: list[dict] = field(default_factory=list)
    data_source_runs: list[dict] = field(default_factory=list)
    terminal_integration_runs: list[dict] = field(default_factory=list)
    financials_runs: list[dict] = field(default_factory=list)
    dark_pool_runs: list[dict] = field(default_factory=list)
    options_runs: list[dict] = field(default_factory=list)


class WorkflowService:
    def __init__(self) -> None:
        self.sessions: dict[UUID, WorkflowSession] = {}
        self.settings = get_settings()
        self._session_store_dir = self._resolve_session_store_dir()
        self._session_store_dir.mkdir(parents=True, exist_ok=True)
        self._data_source_registry_dir = self._resolve_data_source_registry_dir()
        self._data_source_registry_dir.mkdir(parents=True, exist_ok=True)
        self._redis_client = self._resolve_redis_client()
        self.session_store_backend = "redis" if self._redis_client is not None else "file"
        self._load_persisted_sessions()
        self.generator = ScenarioGenerator(seed=11)
        self.scenario_director = ScenarioDirectorAgent(self.generator)
        self.noise_agent = NoiseAgent()
        self.profiler = BehavioralProfilerAgent()
        self.intent_aligner = IntentAlignerAgent()
        self.intelligence = IntelligenceAgent()
        self.portfolio_manager = PortfolioManagerAgent()
        self.risk_guardian = RiskGuardianAgent()
        self.user_monitor = UserMonitorAgent()
        self.strategy_monitor = StrategyMonitorAgent()
        self.market_asset_monitor = MarketAssetMonitorAgent()
        self.strategy_integrity_checker = StrategyIntegrityCheckerAgent()
        self.strategy_stress_checker = StrategyStressCheckerAgent()
        self.programmer = ProgrammerAgent(self.settings)
        self.data_source_expander = DataSourceExpansionAgent()
        self.terminal_integrator = TradingTerminalIntegrationAgent()
        self.evolver = StrategyEvolverAgent()
        self.strategy_registry = StrategyRegistry()
        self.backtest_engine = SimpleBacktestEngine()
        self.metrics_engine = DefaultStrategyMetricsEngine()
        self.feature_pipeline = SessionFeaturePipeline()
        self.market_data = FreeMarketDataService(self.settings)
        self.llm_runtime = LLMRuntime(self.settings)
        self.agent_activity_log: list[dict] = []
        self._dataset_plan_cache: dict[int, dict] = {}
        self._iteration_context_cache: dict[tuple, dict] = {}
        self._candidate_eval_cache: dict[tuple, dict] = {}
        self._intelligence_cache: dict[tuple, dict] = {}
        self._performance_counters = {
            "iteration_context_hits": 0,
            "iteration_context_misses": 0,
            "dataset_plan_hits": 0,
            "dataset_plan_misses": 0,
            "candidate_eval_hits": 0,
            "candidate_eval_misses": 0,
            "intelligence_hits": 0,
            "intelligence_misses": 0,
        }

    def _resolve_session_store_dir(self) -> Path:
        # Default to a repo-local directory next to settings.toml so sessions survive API restarts.
        # This is intentionally lightweight and avoids Postgres/Redis/Qdrant dependencies.
        try:
            config_path = Path(str(self.settings.config_path)).expanduser().resolve()
            return config_path.parent / "session_store"
        except Exception:
            return Path.cwd() / "config" / "session_store"

    def _session_store_path(self, session_id: UUID) -> Path:
        return self._session_store_dir / f"{session_id}.json"

    def _resolve_data_source_registry_dir(self) -> Path:
        try:
            config_path = Path(str(self.settings.config_path)).expanduser().resolve()
            return config_path.parent / "data_source_registry"
        except Exception:
            return Path.cwd() / "config" / "data_source_registry"

    def _redis_key(self, session_id: UUID) -> str:
        return f"sentinel_alpha:session:{session_id}"

    def _redis_index_key(self) -> str:
        return "sentinel_alpha:sessions:index"

    def _resolve_redis_client(self):
        redis_url = str(getattr(self.settings, "redis_url", "") or "").strip()
        if not redis_url:
            return None
        try:
            import redis  # type: ignore
        except Exception:
            return None
        try:
            client = redis.Redis.from_url(redis_url, socket_timeout=0.5, decode_responses=True)
            client.ping()
            return client
        except Exception:
            return None

    def _serialize_session(self, session: WorkflowSession) -> dict:
        payload = asdict(session)
        payload["session_id"] = str(session.session_id)
        return payload

    def _deserialize_session(self, payload: dict) -> WorkflowSession | None:
        if not isinstance(payload, dict) or "session_id" not in payload:
            return None
        try:
            session_id = UUID(str(payload.get("session_id")))
        except Exception:
            return None
        fields = WorkflowSession.__dataclass_fields__.keys()
        data: dict[str, object] = {key: payload.get(key) for key in fields if key in payload}
        data["session_id"] = session_id
        events_raw = payload.get("behavior_events") or []
        if isinstance(events_raw, list):
            events: list[BehaviorEvent] = []
            for item in events_raw:
                if isinstance(item, dict):
                    try:
                        events.append(BehaviorEvent(**item))
                    except Exception:
                        continue
            data["behavior_events"] = events
        try:
            return WorkflowSession(**data)  # type: ignore[arg-type]
        except Exception:
            return None

    def _persist_session(self, session: WorkflowSession) -> None:
        try:
            path = self._session_store_path(session.session_id)
            tmp_path = path.with_suffix(".json.tmp")
            payload = self._serialize_session(session)
            tmp_path.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
            os.replace(tmp_path, path)
            if self._redis_client is not None:
                key = self._redis_key(session.session_id)
                self._redis_client.set(key, json.dumps(payload, ensure_ascii=False, default=str))
                self._redis_client.sadd(self._redis_index_key(), str(session.session_id))
        except Exception:
            # Persistence must never break the workflow path.
            return

    def _data_source_provider_dir(self, provider_slug: str) -> Path:
        path = self._data_source_registry_dir / provider_slug
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _persist_data_source_record(self, *, run: dict, stage: str, payload: dict) -> list[str]:
        provider_slug = str(run.get("provider_slug") or "unknown_provider")
        run_id = str(run.get("run_id") or f"{provider_slug}-{stage}")
        provider_dir = self._data_source_provider_dir(provider_slug)
        specific_path = provider_dir / f"{run_id}.{stage}.json"
        latest_path = provider_dir / f"latest.{stage}.json"
        sanitized_payload = json.loads(json.dumps(payload, ensure_ascii=False, default=str))
        specific_path.write_text(json.dumps(sanitized_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        latest_path.write_text(json.dumps(sanitized_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return [str(specific_path), str(latest_path)]

    def _sanitize_data_source_run_for_local_storage(self, run: dict) -> dict:
        payload = json.loads(json.dumps(run, ensure_ascii=False, default=str))
        inference = payload.get("inference") or {}
        inference.pop("api_key_preview", None)
        payload["inference"] = inference
        analysis = payload.get("analysis") or {}
        payload["analysis"] = analysis
        return payload

    def _sanitize_programmer_apply_for_local_storage(self, apply_result: dict) -> dict:
        payload = json.loads(json.dumps(apply_result, ensure_ascii=False, default=str))
        return payload

    def _category_method_name(self, category: str, kind: str) -> str:
        if category == "market_data":
            return "fetch_quote" if kind == "quote" else "fetch_history"
        if category == "fundamentals":
            return "fetch_fundamentals" if kind == "quote" else "fetch_filing_history"
        if category == "dark_pool":
            return "fetch_dark_pool_snapshot" if kind == "quote" else "fetch_dark_pool_history"
        return "fetch_options_chain" if kind == "quote" else "fetch_options_history"

    def _classify_data_source_live_fetch_failure(self, exc: Exception) -> dict:
        message = str(exc).strip() or exc.__class__.__name__
        lowered = message.lower()
        classification = "provider_or_contract_error"
        status = "warning"
        next_action = "检查接口文档、endpoint、参数映射和返回结构是否与生成代码匹配。"
        retryable = False
        provider_support_needed = False

        if any(token in lowered for token in {"401", "unauthorized", "invalid api key", "bad api key", "apikey invalid", "authentication failed"}):
            classification = "invalid_api_key"
            status = "blocked"
            next_action = "当前 API KEY 无效，请让用户更换正确的 API KEY 后重新测试。"
        elif any(token in lowered for token in {"402", "payment", "billing", "plan", "upgrade", "quota", "credit", "credits", "subscription"}):
            classification = "billing_or_plan_required"
            status = "blocked"
            next_action = "该接口需要付费套餐、额度或已开通权限。提示用户升级套餐、开通权限，或改用本地数据/其他数据源。"
            provider_support_needed = True
        elif any(token in lowered for token in {"403", "forbidden", "permission", "not entitled", "access denied"}):
            classification = "insufficient_permission"
            status = "blocked"
            next_action = "当前账户没有访问该接口的权限。提示用户检查套餐权限、白名单或 endpoint 授权范围。"
            provider_support_needed = True
        elif any(token in lowered for token in {"404", "not found", "unknown endpoint", "no route", "path not found"}):
            classification = "documentation_or_endpoint_mismatch"
            status = "warning"
            next_action = "接口地址或文档描述与生成代码不匹配，请修正文档或 endpoint 映射后重试。"
        elif any(token in lowered for token in {"timeout", "timed out", "temporarily unavailable", "connection refused", "name or service not known", "network is unreachable", "connection reset"}):
            classification = "network_or_provider_unavailable"
            status = "warning"
            next_action = "网络或供应商暂时不可用，可稍后重试；如果持续失败，建议切换本地数据或其他供应商。"
            retryable = True

        return {
            "classification": classification,
            "status": status,
            "detail": message,
            "next_action": next_action,
            "retryable": retryable,
            "provider_support_needed": provider_support_needed,
        }

    def _build_data_source_smoke_test(self, run: dict, *, symbol: str, api_key: str | None) -> dict:
        generated_code = str(run.get("generated_module_code") or "")
        if not generated_code.strip():
            raise ValueError("Selected data-source run does not contain generated module code.")

        category = str(run.get("category") or "market_data")
        quote_method_name = self._category_method_name(category, "quote")
        history_method_name = self._category_method_name(category, "history")

        def resolve_generated_adapter(namespace: dict[str, object]) -> type:
            module_name = str(namespace.get("__name__") or "")
            candidates = [
                value
                for value in namespace.values()
                if isinstance(value, type)
                and getattr(value, "__module__", "") == module_name
                and hasattr(value, quote_method_name)
                and hasattr(value, history_method_name)
            ]
            if not candidates:
                raise ValueError("Generated adapter code does not expose the expected adapter class for smoke testing.")
            return candidates[0]

        namespace: dict[str, object] = {"__name__": "generated_data_source_smoke"}
        exec(generated_code, namespace)
        adapter_class = resolve_generated_adapter(namespace)

        adapter = adapter_class(base_url=(run.get("inference") or {}).get("base_url") or (run.get("config_candidate") or {}).get("provider_config", {}).get("base_url") or "")
        if api_key:
            try:
                setattr(adapter, "api_key", api_key)
            except Exception:
                pass

        quote_method = getattr(adapter, quote_method_name, None)
        history_method = getattr(adapter, history_method_name, None)
        if quote_method is None or history_method is None:
            raise ValueError("Generated adapter does not expose the expected quote/history methods.")

        request_calls: list[tuple[str, dict[str, str]]] = []

        def fake_request(path: str, params: dict[str, str] | None = None) -> dict:
            request_calls.append((path, dict(params or {})))
            return {"ok": True, "path": path, "params": params or {}}

        adapter._request_json = fake_request  # type: ignore[attr-defined]
        quote_preview = quote_method(symbol)
        history_preview = history_method(symbol, interval="1d", lookback="1mo")

        config_candidate = run.get("config_candidate") or {}
        provider_config = config_candidate.get("provider_config") or {}
        config_ok = bool(provider_config.get("base_url")) and bool(config_candidate.get("structured_integration_spec"))

        live_fetch = {
            "status": "skipped",
            "detail": "No API KEY supplied for live smoke test.",
            "quote_result": None,
            "history_result": None,
            "classification": "not_requested",
            "next_action": "如果需要验证真实接口，请提供 API KEY 后重新执行 smoke test。",
            "retryable": True,
            "provider_support_needed": False,
        }
        if api_key:
            live_namespace: dict[str, object] = {"__name__": "generated_data_source_live_smoke"}
            exec(generated_code, live_namespace)
            live_class = resolve_generated_adapter(live_namespace)
            live_adapter = live_class(base_url=(run.get("inference") or {}).get("base_url") or provider_config.get("base_url") or "")
            try:
                setattr(live_adapter, "api_key", api_key)
            except Exception:
                pass
            live_quote = getattr(live_adapter, quote_method_name)
            live_history = getattr(live_adapter, history_method_name)
            try:
                live_fetch = {
                    "status": "ok",
                    "detail": "Live fetch completed.",
                    "quote_result": live_quote(symbol),
                    "history_result": live_history(symbol, interval="1d", lookback="1mo"),
                    "classification": "live_fetch_ok",
                    "next_action": "Live fetch 已通过，可继续应用该数据源。",
                    "retryable": False,
                    "provider_support_needed": False,
                }
            except Exception as exc:
                classified = self._classify_data_source_live_fetch_failure(exc)
                live_fetch = {
                    "status": classified["status"],
                    "detail": classified["detail"],
                    "quote_result": None,
                    "history_result": None,
                    "classification": classified["classification"],
                    "next_action": classified["next_action"],
                    "retryable": classified["retryable"],
                    "provider_support_needed": classified["provider_support_needed"],
                }

        overall_status = "ok" if config_ok and live_fetch["status"] in {"ok", "skipped"} else "warning"
        return {
            "timestamp": self._now_iso(),
            "status": overall_status,
            "symbol": symbol,
            "adapter_class": adapter_class.__name__,
            "structure": {
                "import_ok": True,
                "instantiate_ok": True,
                "config_ok": config_ok,
                "quote_method": quote_method_name,
                "history_method": history_method_name,
                "quote_preview": quote_preview,
                "history_preview": history_preview,
                "request_call_count": len(request_calls),
            },
            "live_fetch": live_fetch,
        }

    def _load_persisted_sessions(self) -> None:
        if self._redis_client is not None:
            try:
                ids = list(self._redis_client.smembers(self._redis_index_key()) or [])
                for raw_id in ids:
                    try:
                        session_id = UUID(str(raw_id))
                    except Exception:
                        continue
                    blob = self._redis_client.get(self._redis_key(session_id))
                    if not blob:
                        continue
                    try:
                        payload = json.loads(blob)
                    except Exception:
                        continue
                    session = self._deserialize_session(payload)
                    if session is not None:
                        self.sessions[session.session_id] = session
                return
            except Exception:
                # Fall back to file store
                pass

        try:
            for path in sorted(self._session_store_dir.glob("*.json")):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                session = self._deserialize_session(payload)
                if session is not None:
                    self.sessions[session.session_id] = session
        except Exception:
            return

    def create_session(self, user_name: str, starting_capital: float) -> WorkflowSession:
        session = WorkflowSession(session_id=uuid4(), user_name=user_name, starting_capital=starting_capital)
        self.sessions[session.session_id] = session
        self._record_agent_activity("workflow_service", "ok", "create_session", "Created workflow session.", session.session_id, request_payload={"user_name": user_name, "starting_capital": starting_capital}, response_payload={"session_id": str(session.session_id), "phase": session.phase, "status": session.status})
        self._append_history_event(
            session,
            "session_created",
            "会话已创建。",
            {"starting_capital": starting_capital, "user_name": user_name},
        )
        self._persist_session(session)
        return session

    def get_session(self, session_id: UUID) -> WorkflowSession:
        session = self.sessions.get(session_id)
        if session is not None:
            return session
        # Lazy-load from disk in case the process restarted and a session is referenced by URL.
        try:
            if self._redis_client is not None:
                blob = self._redis_client.get(self._redis_key(session_id))
                if blob:
                    payload = json.loads(blob)
                    restored = self._deserialize_session(payload)
                    if restored is not None:
                        self.sessions[restored.session_id] = restored
                        return restored
            path = self._session_store_path(session_id)
            if path.exists():
                payload = json.loads(path.read_text(encoding="utf-8"))
                restored = self._deserialize_session(payload)
                if restored is not None:
                    self.sessions[restored.session_id] = restored
                    return restored
        except Exception:
            pass
        raise KeyError(session_id)

    def generate_scenarios(self, session_id: UUID) -> WorkflowSession:
        session = self.get_session(session_id)
        packages = self.scenario_director.generate_default_campaign()
        session.scenario_packages = packages
        session.scenarios = [
            {
                "scenario_id": package.scenario_id,
                "playbook": package.playbook,
                "cohort": package.cohort,
                "tags": package.tags,
            }
            for package in packages
        ]
        session.phase = "simulation_in_progress"
        self._record_agent_activity("scenario_director", "ok", "generate_scenarios", f"Generated {len(session.scenarios)} scenarios.", session.session_id, request_payload={"campaign": "default"}, response_payload={"scenario_count": len(session.scenarios), "scenario_ids": [item["scenario_id"] for item in session.scenarios[:5]]})
        self._append_history_event(
            session,
            "scenarios_generated",
            "模拟测试场景已生成。",
            {"scenario_count": len(session.scenarios)},
        )
        return session

    def append_behavior_event(self, session_id: UUID, event: BehaviorEvent) -> WorkflowSession:
        session = self.get_session(session_id)
        enriched_event = self._enrich_behavior_event_with_market(session, event)
        session.behavior_events.append(enriched_event)
        self._record_agent_activity("behavioral_profiler", "ok", "append_behavior_event", f"Recorded action={event.action} for {event.scenario_id}.", session.session_id, request_payload={"scenario_id": event.scenario_id, "action": event.action, "drawdown_pct": event.price_drawdown_pct, "noise_level": event.noise_level, "latency_seconds": event.latency_seconds, "execution_status": event.execution_status, "execution_reason": event.execution_reason}, response_payload={"phase": session.phase, "event_count": len(session.behavior_events)})
        self._append_history_event(
            session,
            "behavior_event_recorded",
            "记录了一次模拟交易行为。",
            {
                "scenario_id": enriched_event.scenario_id,
                "action": enriched_event.action,
                "drawdown_pct": enriched_event.price_drawdown_pct,
                "market_timestamp": enriched_event.timestamp,
                "market_price": enriched_event.market_price,
                "intraday_progress_pct": enriched_event.intraday_progress_pct,
            },
        )
        return session

    def initialize_simulation_market(
        self,
        session_id: UUID,
        symbol: str,
        provider: str | None = None,
        daily_lookback: str = "6mo",
        intraday_lookback: str = "5d",
        intraday_interval: str = "5m",
    ) -> WorkflowSession:
        session = self.get_session(session_id)
        resolved_symbol = symbol.strip().upper()
        if not resolved_symbol:
            raise ValueError("Simulation market initialization requires a symbol.")
        daily_raw = self.market_data.fetch_history(
            symbol=resolved_symbol,
            interval="1d",
            lookback=daily_lookback,
            provider=provider,
        )
        intraday_raw = self.market_data.fetch_history(
            symbol=resolved_symbol,
            interval=intraday_interval,
            lookback=intraday_lookback,
            provider=provider,
        )
        daily_bars = self._normalize_simulation_bars(daily_raw.get("bars") or [], timeframe="1d")
        intraday_bars = self._normalize_simulation_bars(intraday_raw.get("bars") or [], timeframe=intraday_interval)
        if not daily_bars:
            raise RuntimeError("Daily history is empty; cannot initialize simulation market.")
        if not intraday_bars:
            raise RuntimeError("Intraday history is empty; cannot initialize simulation market.")
        session.simulation_market = {
            "symbol": resolved_symbol,
            "provider": provider or daily_raw.get("provider") or intraday_raw.get("provider") or "unknown",
            "daily_interval": "1d",
            "daily_lookback": daily_lookback,
            "intraday_interval": intraday_interval,
            "intraday_lookback": intraday_lookback,
            "daily_bars": daily_bars,
            "intraday_bars": intraday_bars,
            "cursor": 0,
        }
        self._refresh_simulation_market_state(session, append_snapshot=True)
        session.phase = "simulation_market_ready"
        self._record_agent_activity(
            "market_asset_monitor",
            "ok",
            "initialize_simulation_market",
            f"Loaded simulation market data for {resolved_symbol}.",
            session.session_id,
            request_payload={
                "symbol": resolved_symbol,
                "provider": provider,
                "daily_lookback": daily_lookback,
                "intraday_lookback": intraday_lookback,
                "intraday_interval": intraday_interval,
            },
            response_payload={
                "daily_bar_count": len(daily_bars),
                "intraday_bar_count": len(intraday_bars),
                "current_timestamp": (session.simulation_market or {}).get("current_timestamp"),
            },
        )
        self._append_history_event(
            session,
            "simulation_market_initialized",
            "模拟市场数据已加载。",
            {
                "symbol": resolved_symbol,
                "daily_bar_count": len(daily_bars),
                "intraday_bar_count": len(intraday_bars),
                "intraday_interval": intraday_interval,
            },
        )
        return session

    def advance_simulation_market(self, session_id: UUID, steps: int = 1) -> WorkflowSession:
        session = self.get_session(session_id)
        market = session.simulation_market or {}
        intraday_bars = market.get("intraday_bars") or []
        if not intraday_bars:
            raise ValueError("Simulation market is not initialized.")
        cursor = int(market.get("cursor") or 0)
        max_index = max(0, len(intraday_bars) - 1)
        next_cursor = min(cursor + max(1, int(steps)), max_index)
        market["cursor"] = next_cursor
        session.simulation_market = market
        self._refresh_simulation_market_state(session, append_snapshot=True)
        current = (session.simulation_market or {}).get("current_bar") or {}
        self._record_agent_activity(
            "market_asset_monitor",
            "ok",
            "advance_simulation_market",
            f"Advanced simulation market by {steps} step(s).",
            session.session_id,
            request_payload={"steps": steps},
            response_payload={
                "cursor": next_cursor,
                "current_timestamp": current.get("timestamp"),
                "current_price": current.get("close"),
            },
        )
        self._append_history_event(
            session,
            "simulation_market_advanced",
            "模拟时钟已推进。",
            {
                "steps": steps,
                "cursor": next_cursor,
                "current_timestamp": current.get("timestamp"),
                "current_price": current.get("close"),
                "progress_pct": (session.simulation_market or {}).get("progress_pct"),
            },
        )
        return session

    def complete_simulation(self, session_id: UUID, symbol: str) -> WorkflowSession:
        session = self.get_session(session_id)
        market = session.simulation_market or {}
        if not market:
            raise ValueError("Simulation market must be initialized before completing simulation.")
        if int(market.get("cursor") or 0) <= 0:
            raise ValueError("Simulation market must be advanced before completing simulation.")
        if not session.behavior_events:
            raise ValueError("At least one simulated action is required before completing simulation.")
        user = UserProfile(
            user_id=str(session.session_id),
            preferred_assets=[symbol],
            capital_base=session.starting_capital,
            target_holding_days=10,
            self_reported_risk_tolerance=0.5,
            confidence_level=0.5,
        )
        report = self.profiler.profile(session.behavior_events)
        market_context = self._simulation_market_analysis_context(session)
        market = MarketSnapshot(symbol=symbol, expected_return_pct=16.0, realized_volatility_pct=35.0, trend_score=0.45, event_risk_score=0.35, liquidity_score=0.9)
        policy = self.evolver.derive_risk_policy(user, report)
        brief = self.evolver.synthesize(user, market, report, policy)
        trading_recommendation = self._recommend_trading_preferences(report)
        strategy_recommendation = self._recommend_strategy_type(report, trading_recommendation)
        total_events = max(1, len(session.behavior_events))
        executed_events = [event for event in session.behavior_events if event.execution_status in {"filled", "partial_fill"}]
        partial_events = [event for event in session.behavior_events if event.execution_status == "partial_fill"]
        rejected_events = [event for event in session.behavior_events if event.execution_status == "rejected"]
        unfilled_events = [event for event in session.behavior_events if event.execution_status == "unfilled"]
        high_noise_events = [event for event in session.behavior_events if event.noise_level >= 0.7]
        high_noise_executed_events = [event for event in high_noise_events if event.execution_status in {"filled", "partial_fill"}]
        high_noise_hold_events = [event for event in high_noise_events if event.action == "hold" or event.execution_status == "hold"]
        clean_execution_ratio = max(0.0, min(1.0, (len(executed_events) - len(partial_events)) / total_events))
        fast_event_ratio = round(sum(1 for event in session.behavior_events if event.latency_seconds < 45) / total_events, 4)
        slow_event_ratio = round(sum(1 for event in session.behavior_events if event.latency_seconds > 240) / total_events, 4)
        behavior_tags: list[str] = []
        if fast_event_ratio > 0.4:
            behavior_tags.append("impulsive_execution")
        if slow_event_ratio > 0.35:
            behavior_tags.append("hesitant_execution")
        if len(unfilled_events) / total_events > 0.3:
            behavior_tags.append("probing_limit_orders")
        if len(rejected_events) / total_events > 0.3:
            behavior_tags.append("constraint_blind_submission")
        if len(partial_events) / total_events > 0.2:
            behavior_tags.append("size_liquidity_mismatch")
        if len(high_noise_executed_events) / max(1, len(high_noise_events)) > 0.45:
            behavior_tags.append("noise_driven_execution")
        if len(high_noise_hold_events) / max(1, len(high_noise_events)) > 0.45:
            behavior_tags.append("noise_resistant_patience")
        if len(rejected_events) / total_events > 0.3:
            execution_note = "用户存在较多被拒单行为，说明下单约束感知偏弱。"
        elif len(unfilled_events) / total_events > 0.3:
            execution_note = "用户频繁挂单未触发，更像试探式参与而非直接成交。"
        elif len(partial_events) / total_events > 0.2:
            execution_note = "用户成交经常受到流动性约束，交易规模与时段流动性匹配不足。"
        elif len(high_noise_executed_events) / max(1, len(high_noise_events)) > 0.45:
            execution_note = "用户在高噪音条件下仍频繁直接成交，存在明显的叙事驱动执行倾向。"
        elif len(high_noise_hold_events) / max(1, len(high_noise_events)) > 0.45:
            execution_note = "用户在高噪音条件下更常选择观望，说明对情绪叙事有一定抵抗力。"
        elif fast_event_ratio > 0.4:
            execution_note = "用户经常在短时间内快速出手，存在冲动执行倾向。"
        elif slow_event_ratio > 0.35:
            execution_note = "用户决策等待时间偏长，更像犹豫后再执行。"
        else:
            execution_note = "用户的成交质量总体稳定，执行结果与指令一致性较高。"
        llm_strict = bool(getattr(self.settings, "llm_strict", True)) and bool(self.settings.llm_enabled)
        rule_based_warning = (
            None
            if llm_strict
            else "当前未经过 live LLM 个性化分析，以下内容仅为规则统计与启发式建议，不是完整智能分析。"
        )
        system_report = {
            "report_generation_mode": "rule_based",
            "source_of_truth": "behavior_event_statistics",
            "analysis_status": "heuristic_only",
            "analysis_warning": rule_based_warning,
            "loss_tolerance": -report.max_comfort_drawdown_pct,
            "noise_sensitivity": report.noise_susceptibility,
            "panic_sell_tendency": report.panic_sell_score,
            "bottom_fishing_tendency": report.averaging_down_score,
            "hold_strength": report.discipline_score,
            "overtrading_tendency": report.intervention_risk,
            "max_drawdown_endured": report.max_comfort_drawdown_pct,
            "recommended_risk_ceiling": policy.max_position_pct,
            "strategy_compatibility_preview": brief.utility_score,
            "recommended_trading_frequency": trading_recommendation["trading_frequency"],
            "recommended_timeframe": trading_recommendation["preferred_timeframe"],
            "trading_preference_recommendation_note": trading_recommendation["note"],
            "recommended_strategy_type": strategy_recommendation["strategy_type"],
            "strategy_type_recommendation_note": strategy_recommendation["note"],
            "execution_event_count": len(session.behavior_events),
            "executed_trade_ratio": round(len(executed_events) / total_events, 4),
            "partial_fill_ratio": round(len(partial_events) / total_events, 4),
            "rejected_order_ratio": round(len(rejected_events) / total_events, 4),
            "unfilled_order_ratio": round(len(unfilled_events) / total_events, 4),
            "clean_execution_ratio": round(clean_execution_ratio, 4),
            "fast_event_ratio": fast_event_ratio,
            "slow_event_ratio": slow_event_ratio,
            "behavior_tags": behavior_tags,
            "high_noise_execution_ratio": round(len(high_noise_executed_events) / max(1, len(high_noise_events)), 4),
            "high_noise_hold_ratio": round(len(high_noise_hold_events) / max(1, len(high_noise_events)), 4),
            "execution_quality_note": execution_note,
            "simulation_market_context": market_context,
        }
        user_report = {
            "report_generation_mode": "rule_based",
            "source_of_truth": "behavior_event_statistics",
            "analysis_status": "factual_summary_only",
            "analysis_warning": rule_based_warning,
            "user_summary": self._build_behavioral_user_summary(system_report),
            "execution_event_count": system_report["execution_event_count"],
            "executed_trade_ratio": system_report["executed_trade_ratio"],
            "partial_fill_ratio": system_report["partial_fill_ratio"],
            "rejected_order_ratio": system_report["rejected_order_ratio"],
            "unfilled_order_ratio": system_report["unfilled_order_ratio"],
            "clean_execution_ratio": system_report["clean_execution_ratio"],
            "execution_quality_note": system_report["execution_quality_note"],
            "behavior_tags": list(system_report["behavior_tags"]),
            "high_noise_execution_ratio": system_report["high_noise_execution_ratio"],
            "high_noise_hold_ratio": system_report["high_noise_hold_ratio"],
            "fast_event_ratio": system_report["fast_event_ratio"],
            "slow_event_ratio": system_report["slow_event_ratio"],
            "simulation_market_context": market_context,
        }
        llm_user_report, llm_system_report = self._generate_behavioral_llm_reports(
            symbol=symbol,
            report=report,
            system_report=system_report,
            user_report=user_report,
            behavior_events=session.behavior_events,
        )
        if llm_strict and (not llm_user_report or not llm_system_report):
            raise RuntimeError("LLM strict mode is enabled but behavioral LLM reports were not produced.")
        if llm_user_report:
            user_report = llm_user_report
        if llm_system_report:
            system_report = llm_system_report
        session.behavioral_report = system_report
        session.behavioral_user_report = user_report
        session.behavioral_system_report = system_report
        session.profile_evolution = {
            "base_profile": dict(system_report),
            "effective_profile": dict(system_report),
            "confidence_level": user.confidence_level,
            "events": [
                {
                    "source_type": "simulation",
                    "source_ref": symbol,
                    "timestamp": self._now_iso(),
                    "note": "Behavioral profile initialized from simulation trading.",
                }
            ],
        }
        session.phase = "profiler_ready"
        self._record_agent_activity("behavioral_profiler", "ok", "complete_simulation", "Generated behavioral reports for user and system views.", session.session_id, request_payload={"symbol": symbol, "event_count": len(session.behavior_events)}, response_payload={"recommended_strategy_type": strategy_recommendation["strategy_type"], "recommended_frequency": trading_recommendation["trading_frequency"], "execution_quality_note": execution_note, "behavior_tags": behavior_tags, "user_report_ready": session.behavioral_user_report is not None, "system_report_ready": session.behavioral_system_report is not None})
        self._archive_report(
            session,
            report_type="behavioral_profiler_user",
            title="Behavioral Profiler User Report",
            body=session.behavioral_user_report or {},
            related_refs=[symbol],
        )
        self._archive_report(
            session,
            report_type="behavioral_profiler_system",
            title="Behavioral Profiler System Report",
            body=session.behavioral_system_report or {},
            related_refs=[symbol],
        )
        self._append_history_event(
            session,
            "simulation_completed",
            "模拟测试完成并生成心理侧写报告。",
            {
                "symbol": symbol,
                "user_report_ready": session.behavioral_user_report is not None,
                "system_report_ready": session.behavioral_system_report is not None,
            },
        )
        return session

    def _enrich_behavior_event_with_market(self, session: WorkflowSession, event: BehaviorEvent) -> BehaviorEvent:
        market = session.simulation_market or {}
        current_bar = market.get("current_bar") or {}
        current_daily_bar = market.get("current_daily_bar") or {}
        if not market:
            return event
        daily_open = self._safe_float(current_daily_bar.get("open"))
        daily_close = self._safe_float(current_daily_bar.get("close"))
        current_close = self._safe_float(current_bar.get("close"))
        day_return = None
        if daily_open not in (None, 0) and daily_close is not None:
            day_return = round(((daily_close / daily_open) - 1.0) * 100.0, 4)
        daily_prev = None
        for bar in reversed(market.get("daily_visible_bars") or []):
            if bar.get("timestamp") != current_daily_bar.get("timestamp"):
                daily_prev = bar
                break
        daily_trend = None
        prev_close = self._safe_float((daily_prev or {}).get("close"))
        if prev_close not in (None, 0) and daily_close is not None:
            daily_trend = round(((daily_close / prev_close) - 1.0) * 100.0, 4)
        progress_pct = self._safe_float(market.get("progress_pct")) or 0.0
        current_drawdown = self._safe_float(market.get("current_drawdown_pct"))
        inferred_noise = round(min(1.0, abs((current_drawdown or 0.0)) / 8.0 + progress_pct / 200.0), 4)
        inferred_sentiment = round(max(-1.0, min(1.0, ((daily_trend or 0.0) / 5.0) + ((current_drawdown or 0.0) / 10.0))), 4)
        inferred_latency = max(0.0, round((100.0 - progress_pct) * 0.9, 2))
        inferred_status = "hold" if event.action == "hold" else (event.execution_status or "filled")
        return BehaviorEvent(
            scenario_id=event.scenario_id,
            price_drawdown_pct=event.price_drawdown_pct if event.price_drawdown_pct not in (None, 0.0) else float(current_drawdown or 0.0),
            action=event.action,
            noise_level=event.noise_level if event.noise_level not in (None, 0.0) else inferred_noise,
            sentiment_pressure=event.sentiment_pressure if event.sentiment_pressure not in (None, 0.0) else inferred_sentiment,
            latency_seconds=event.latency_seconds if event.latency_seconds not in (None, 0.0) else inferred_latency,
            execution_status=inferred_status,
            execution_reason=event.execution_reason,
            symbol=str(market.get("symbol") or event.symbol or ""),
            timestamp=str(market.get("current_timestamp") or event.timestamp or self._now_iso()),
            market_price=current_close,
            market_open_price=self._safe_float(current_bar.get("open")),
            market_high_price=self._safe_float(current_bar.get("high")),
            market_low_price=self._safe_float(current_bar.get("low")),
            intraday_timeframe=str(market.get("intraday_interval") or event.intraday_timeframe or ""),
            intraday_progress_pct=progress_pct,
            market_regime=str((current_bar.get("regime_tag") or market.get("market_regime") or current_daily_bar.get("regime_tag") or "")),
            current_drawdown_pct=current_drawdown,
            daily_trend_pct=daily_trend,
            current_day_return_pct=day_return,
        )

    def _simulation_market_analysis_context(self, session: WorkflowSession) -> dict:
        market = session.simulation_market or {}
        current_bar = market.get("current_bar") or {}
        current_daily_bar = market.get("current_daily_bar") or {}
        return {
            "symbol": market.get("symbol"),
            "provider": market.get("provider"),
            "intraday_interval": market.get("intraday_interval"),
            "daily_bar_count": market.get("daily_bar_count"),
            "intraday_bar_count": market.get("intraday_bar_count"),
            "current_timestamp": market.get("current_timestamp"),
            "progress_pct": market.get("progress_pct"),
            "current_drawdown_pct": market.get("current_drawdown_pct"),
            "current_price": current_bar.get("close"),
            "day_open": current_daily_bar.get("open"),
            "day_close": current_daily_bar.get("close"),
            "day_high": current_daily_bar.get("high"),
            "day_low": current_daily_bar.get("low"),
            "is_complete": market.get("is_complete"),
        }

    def _refresh_simulation_market_state(self, session: WorkflowSession, *, append_snapshot: bool) -> None:
        market = session.simulation_market or {}
        daily_bars = market.get("daily_bars") or []
        intraday_bars = market.get("intraday_bars") or []
        if not daily_bars or not intraday_bars:
            return
        cursor = min(max(int(market.get("cursor") or 0), 0), len(intraday_bars) - 1)
        current_bar = dict(intraday_bars[cursor])
        previous_bar = dict(intraday_bars[cursor - 1]) if cursor > 0 else None
        current_date = str(current_bar.get("timestamp") or "")[:10]
        current_day_bars = [dict(item) for item in intraday_bars if str(item.get("timestamp") or "")[:10] == current_date]
        current_day_visible = [dict(item) for item in intraday_bars[: cursor + 1] if str(item.get("timestamp") or "")[:10] == current_date]
        current_daily_bar = None
        for bar in daily_bars:
            if str(bar.get("timestamp") or "")[:10] <= current_date:
                current_daily_bar = dict(bar)
        if current_daily_bar is None:
            current_daily_bar = dict(daily_bars[min(len(daily_bars) - 1, cursor)])
        closes = [float(item.get("close") or 0.0) for item in current_day_visible if item.get("close") is not None]
        peak = max(closes) if closes else float(current_bar.get("close") or 0.0)
        current_close = float(current_bar.get("close") or 0.0)
        current_drawdown_pct = round(((current_close / peak) - 1.0) * 100.0, 4) if peak else 0.0
        progress_pct = round(((cursor + 1) / max(1, len(intraday_bars))) * 100.0, 2)
        market.update(
            {
                "cursor": cursor,
                "current_bar": current_bar,
                "previous_bar": previous_bar,
                "current_daily_bar": current_daily_bar,
                "current_timestamp": current_bar.get("timestamp"),
                "current_date": current_date,
                "current_price": current_close,
                "current_drawdown_pct": current_drawdown_pct,
                "current_day_bars": current_day_bars,
                "current_day_visible_bars": current_day_visible,
                "daily_visible_bars": [dict(item) for item in daily_bars if str(item.get("timestamp") or "")[:10] <= current_date],
                "progress_pct": progress_pct,
                "remaining_steps": max(0, len(intraday_bars) - cursor - 1),
                "is_complete": cursor >= len(intraday_bars) - 1,
                "daily_bar_count": len(daily_bars),
                "intraday_bar_count": len(intraday_bars),
            }
        )
        session.simulation_market = market
        if append_snapshot:
            session.market_snapshots.append(
                {
                    "timestamp": current_bar.get("timestamp"),
                    "symbol": market.get("symbol"),
                    "timeframe": market.get("intraday_interval"),
                    "open_price": current_bar.get("open"),
                    "high_price": current_bar.get("high"),
                    "low_price": current_bar.get("low"),
                    "close_price": current_bar.get("close"),
                    "volume": current_bar.get("volume"),
                    "source": f"simulation_market:{market.get('provider', 'unknown')}",
                    "regime_tag": f"simulation_progress_{progress_pct}",
                }
            )

    def _normalize_simulation_bars(self, bars: list[dict], *, timeframe: str) -> list[dict]:
        normalized: list[dict] = []
        for item in bars:
            try:
                timestamp = self._bar_timestamp_iso(item.get("timestamp"))
                normalized.append(
                    {
                        "timestamp": timestamp,
                        "timeframe": timeframe,
                        "open": self._safe_float(item.get("open")),
                        "high": self._safe_float(item.get("high")),
                        "low": self._safe_float(item.get("low")),
                        "close": self._safe_float(item.get("close")),
                        "volume": self._safe_float(item.get("volume")),
                    }
                )
            except Exception:
                continue
        normalized.sort(key=lambda item: item.get("timestamp") or "")
        return [item for item in normalized if item.get("close") is not None]

    def _bar_timestamp_iso(self, raw: object) -> str:
        if raw is None:
            raise ValueError("Missing bar timestamp.")
        if isinstance(raw, (int, float)):
            return datetime.fromtimestamp(float(raw), timezone.utc).isoformat()
        text = str(raw).strip()
        if not text:
            raise ValueError("Empty bar timestamp.")
        if text.isdigit():
            return datetime.fromtimestamp(float(text), timezone.utc).isoformat()
        if "T" in text:
            normalized = text.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized).astimezone(timezone.utc).isoformat()
        if len(text) == 10 and text.count("-") == 2:
            return datetime.fromisoformat(f"{text}T00:00:00+00:00").isoformat()
        return datetime.fromisoformat(text).astimezone(timezone.utc).isoformat()

    def _safe_float(self, value: object) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except Exception:
            return None

    def _build_behavioral_user_summary(self, report: dict) -> str:
        clean = float(report.get("clean_execution_ratio", 0.0))
        fast = float(report.get("fast_event_ratio", 0.0))
        noise_exec = float(report.get("high_noise_execution_ratio", 0.0))
        if noise_exec >= 0.45:
            style_note = "你在高噪音环境下更容易直接执行。"
        elif fast >= 0.4:
            style_note = "你的下单节奏偏快。"
        elif clean >= 0.7:
            style_note = "你的执行结果整体较稳定。"
        else:
            style_note = "你的执行行为存在明显波动。"
        return f"当前报告仅展示规则统计结果，不代表完整智能分析。{style_note}"

    def _generate_behavioral_llm_reports(
        self,
        *,
        symbol: str,
        report: BehavioralReport,
        system_report: dict,
        user_report: dict,
        behavior_events: list[BehaviorEvent],
    ) -> tuple[dict, dict]:
        def _is_placeholder_rule_summary(summary: object) -> bool:
            if not isinstance(summary, str):
                return True
            text = summary.strip()
            if not text:
                return True
            # If the LLM output still contains our rule-based disclaimer, treat it as invalid output.
            red_flags = [
                "仅展示规则统计结果",
                "不代表完整智能分析",
                "未经过 live LLM",
                "规则统计与启发式建议",
            ]
            return any(flag in text for flag in red_flags)

        event_digest = [
            {
                "scenario_id": item.scenario_id,
                "action": item.action,
                "drawdown_pct": item.price_drawdown_pct,
                "noise_level": item.noise_level,
                "sentiment_pressure": item.sentiment_pressure,
                "latency_seconds": item.latency_seconds,
                "execution_status": item.execution_status,
                "execution_reason": item.execution_reason,
            }
            for item in behavior_events[-12:]
        ]
        prompt_payload = {
            "symbol": symbol,
            "rule_report": system_report,
            "behavioral_scores": {
                "panic_sell_score": report.panic_sell_score,
                "averaging_down_score": report.averaging_down_score,
                "noise_susceptibility": report.noise_susceptibility,
                "intervention_risk": report.intervention_risk,
                "max_comfort_drawdown_pct": report.max_comfort_drawdown_pct,
                "discipline_score": report.discipline_score,
                "notes": list(report.notes),
            },
            "recent_events": event_digest,
        }
        # Seed user/system reports are used only for fallback; do not leak rule-based disclaimer into a "live_llm" result.
        fallback_text = json.dumps({"user_report": user_report, "system_report": system_report}, ensure_ascii=False)
        system_prompt = (
            "Return strict JSON only with keys user_report and system_report (no markdown, no prose). "
            "Write concise Chinese analysis grounded only in the provided behavior payload; do not invent data. "
            "Do NOT repeat numeric metrics from rule_report; those will remain in the merged report. "
            "Output MINIFIED JSON (no pretty printing, no indentation, no extra newlines). "
            "Output only compact analysis fields with these allowed keys:\n"
            "user_report: user_summary, recommended_trading_frequency, recommended_timeframe, recommended_strategy_type, "
            "recommended_risk_ceiling, trading_pace_note, execution_quality_note, behavior_tags.\n"
            "system_report: execution_quality_note, behavior_tags, risk_notes, guardrails.\n"
            "user_report must include a non-empty user_summary that is personalized and MUST NOT contain any rule-based disclaimer "
            "(forbidden phrases include: 仅展示规则统计结果 / 不代表完整智能分析 / 未经过 live LLM / 规则统计与启发式建议). "
            "Keep values short. Set report_generation_mode=live_llm, source_of_truth=live_llm_behavior_analysis, analysis_status=live_llm_completed."
        )
        # Do not cache behavior_analysis: a single invalid formatting response would get stuck in cache and force rule-based fallback.
        llm_result = self.llm_runtime.invoke_text_task(
            "behavior_analysis",
            json.dumps(prompt_payload, ensure_ascii=False),
            fallback_agent="behavioral_profiler",
            fallback_text=fallback_text,
            system_prompt=system_prompt,
        )
        profile = llm_result["profile"]
        invocation = llm_result["invocation"]
        raw_text = str(llm_result.get("text", "") or "")
        parsed = self._parse_llm_json(raw_text)
        invalid_reason = None
        if not isinstance(parsed, dict) or not isinstance(parsed.get("user_report"), dict) or not isinstance(parsed.get("system_report"), dict):
            invalid_reason = "invalid_json_shape"
        elif _is_placeholder_rule_summary(parsed["user_report"].get("user_summary")):
            invalid_reason = "missing_or_placeholder_user_summary"

        if invalid_reason:
            # If the LLM call succeeded but formatting was invalid, try one strict repair attempt.
            # This reduces intermittent formatting failures without pretending the output is valid.
            if invocation.get("actual_generation_mode") == "live_llm" and invocation.get("fallback_reason") is None:
                repair_payload = {
                    "symbol": symbol,
                    "original_payload": prompt_payload,
                    "invalid_output_excerpt": raw_text[:2000],
                    "instruction": "Repair the output into strict JSON only with keys user_report and system_report.",
                }
                repaired = self.llm_runtime.invoke_text_task(
                    "behavior_analysis",
                    json.dumps(repair_payload, ensure_ascii=False),
                    fallback_agent="behavioral_profiler",
                    fallback_text=fallback_text,
                    system_prompt=system_prompt + " If you cannot comply, return an empty JSON object {}.",
                )
                raw_text = str(repaired.get("text", "") or "")
                invocation = repaired["invocation"]
                profile = repaired["profile"]
                parsed = self._parse_llm_json(raw_text)
                if isinstance(parsed, dict) and isinstance(parsed.get("user_report"), dict) and isinstance(parsed.get("system_report"), dict):
                    if not _is_placeholder_rule_summary(parsed["user_report"].get("user_summary")):
                        invalid_reason = None
                    else:
                        invalid_reason = "missing_or_placeholder_user_summary"
                else:
                    invalid_reason = "invalid_json_shape"

            if invalid_reason:
                if bool(getattr(self.settings, "llm_strict", True)) and bool(self.settings.llm_enabled):
                    # Strict mode forbids silently returning rule-based reports when LLM output is invalid.
                    raise ValueError(
                        "Behavior analysis LLM returned invalid JSON. "
                        f"reason={invalid_reason}; generation_mode={invocation.get('actual_generation_mode')}; "
                        f"fallback_reason={invocation.get('fallback_reason')}; excerpt={raw_text[:200]}"
                    )
                invocation = dict(invocation)
                invocation["raw_text_excerpt"] = raw_text[:800]
                warning = (
                    "行为分析 LLM 未成功完成，当前回退为规则统计。"
                    f"reason={invalid_reason};fallback_reason={invocation.get('fallback_reason') or 'unknown'}。"
                )
                fallback_user = dict(user_report)
                fallback_user["report_generation_mode"] = "rule_based"
                fallback_user["analysis_status"] = "factual_summary_only"
                fallback_user["analysis_warning"] = warning
                fallback_user["source_of_truth"] = "behavior_event_statistics"
                fallback_user["llm_invocation"] = invocation
                fallback_system = dict(system_report)
                fallback_system["report_generation_mode"] = "rule_based"
                fallback_system["analysis_status"] = "heuristic_only"
                fallback_system["analysis_warning"] = warning
                fallback_system["source_of_truth"] = "behavior_event_statistics"
                fallback_system["llm_invocation"] = invocation
                return fallback_user, fallback_system
        final_user = dict(user_report)
        final_user.update(parsed["user_report"])
        final_user["report_generation_mode"] = profile.generation_mode
        final_user["source_of_truth"] = "live_llm_behavior_analysis" if profile.generation_mode == "live_llm" else "behavior_event_statistics"
        final_user["analysis_status"] = "live_llm_completed" if profile.generation_mode == "live_llm" else "factual_summary_only"
        final_user["analysis_warning"] = None if profile.generation_mode == "live_llm" else user_report.get("analysis_warning")
        final_user["llm_invocation"] = invocation
        final_system = dict(system_report)
        final_system.update(parsed["system_report"])
        final_system["report_generation_mode"] = profile.generation_mode
        final_system["source_of_truth"] = "live_llm_behavior_analysis" if profile.generation_mode == "live_llm" else "behavior_event_statistics"
        final_system["analysis_status"] = "live_llm_completed" if profile.generation_mode == "live_llm" else "heuristic_only"
        final_system["analysis_warning"] = None if profile.generation_mode == "live_llm" else system_report.get("analysis_warning")
        final_system["llm_invocation"] = invocation
        return final_user, final_system

    def _parse_llm_json(self, raw_text: str) -> dict | None:
        text = (raw_text or "").strip()
        if not text:
            return None
        if text.startswith("```"):
            parts = [part.strip() for part in text.split("```") if part.strip()]
            for part in parts:
                if part.lower() == "json":
                    continue
                if part.lower().startswith("json\n"):
                    part = part[5:]
                text = part
                break
        try:
            payload = json.loads(text)
            return payload if isinstance(payload, dict) else None
        except Exception:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    payload = json.loads(text[start : end + 1])
                    return payload if isinstance(payload, dict) else None
                except Exception:
                    return None
            return None

    def set_trading_preferences(
        self,
        session_id: UUID,
        trading_frequency: str,
        preferred_timeframe: str,
        rationale: str | None,
    ) -> WorkflowSession:
        session = self.get_session(session_id)
        session.trading_preferences = self.intent_aligner.build_trading_preferences(
            trading_frequency=trading_frequency,
            preferred_timeframe=preferred_timeframe,
            rationale=rationale,
        )
        conflict = self.intent_aligner.detect_preference_conflict(
            session.behavioral_report,
            session.trading_preferences,
        )
        if conflict:
            session.trading_preferences["conflict_warning"] = conflict["warning"]
            session.trading_preferences["conflict_level"] = conflict["level"]
        session.phase = "preferences_ready"
        self._record_agent_activity("intent_aligner", "ok", "set_trading_preferences", "Updated trading preferences and checked conflicts.", session.session_id, request_payload={"trading_frequency": trading_frequency, "preferred_timeframe": preferred_timeframe}, response_payload={"preferences": session.trading_preferences})
        self._append_history_event(
            session,
            "trading_preferences_updated",
            "交易频次与周期偏好已更新。",
            {
                "trading_frequency": trading_frequency,
                "preferred_timeframe": preferred_timeframe,
            },
        )
        return session

    def set_trade_universe(self, session_id: UUID, input_type: str, symbols: list[str], allow_overfit_override: bool) -> WorkflowSession:
        session = self.get_session(session_id)
        expanded = list(dict.fromkeys(symbols))
        minimum_universe_size = self.settings.minimum_universe_size
        if len(expanded) < minimum_universe_size and not allow_overfit_override:
            base = expanded[0] if expanded else "QQQ"
            filler = [f"{base}_PEER_{index}" for index in range(1, minimum_universe_size + 1)]
            expanded = list(dict.fromkeys(expanded + filler))[:minimum_universe_size]
            expansion_reason = f"Expanded to minimum {minimum_universe_size} tradeable objects to reduce overfitting."
        else:
            expansion_reason = "No expansion required."
        session.trade_universe = {
            "input_type": input_type,
            "requested": symbols,
            "expanded": expanded,
            "minimum_universe_size": minimum_universe_size,
            "expansion_reason": expansion_reason,
        }
        session.phase = "universe_ready"
        self._record_agent_activity("intelligence_agent", "ok", "set_trade_universe", f"Prepared universe size={len(expanded)}.", session.session_id, request_payload={"input_type": input_type, "symbols": symbols, "allow_overfit_override": allow_overfit_override}, response_payload={"expanded": expanded[:10], "expanded_count": len(expanded), "expansion_reason": expansion_reason})
        self._append_history_event(
            session,
            "trade_universe_updated",
            "交易标的池已更新。",
            {
                "input_type": input_type,
                "requested_count": len(symbols),
                "expanded_count": len(expanded),
            },
        )
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
        training_window: dict | None = None,
    ) -> WorkflowSession:
        session = self.get_session(session_id)
        if session.trade_universe is None or session.behavioral_report is None:
            raise ValueError("Trade universe and behavioral report must exist before strategy iteration.")
        expanded = session.trade_universe["expanded"]
        targets = self._normalize_objective_targets(objective_metric, objective_targets or {})
        if feedback:
            self._apply_feedback_evolution(session, feedback, strategy_type)
        iteration_context = self._get_iteration_context(
            session=session,
            strategy_type=strategy_type,
            expanded=expanded,
        )
        last_error: str | None = None
        for loop_index in range(max(1, auto_iterations)):
            iteration_no = 1 if session.strategy_package is None else session.strategy_package["iteration_no"] + 1
            try:
                compatibility = max(0.35, min(0.95, 0.78 - 0.04 * max(0, iteration_no - 1)))
                market = iteration_context["market"]
                user = iteration_context["user"]
                behavior = iteration_context["behavior"]
                policy = iteration_context["policy"]
                self._record_agent_activity("strategy_evolver", "ok", "derive_risk_policy", "Derived risk policy for iteration.", session.session_id, request_payload={"strategy_type": strategy_type, "objective_metric": objective_metric, "feedback": feedback or ""}, response_payload={"selected_universe_size": len(expanded), "feature_snapshot": iteration_context["features"].get("meta", {})})
                baseline_candidate = self.evolver.build_strategy_candidate(
                    user=user,
                    market=market,
                    report=behavior,
                    policy=policy,
                    selected_universe=expanded,
                    feedback=None,
                    strategy_type="rule_based_aligned",
                    features=iteration_context["features"],
                )
                baseline_payload = asdict(baseline_candidate)
                baseline_payload["version"] = self._strategy_version_label(1, iteration_no, 0, "baseline_rule_based")
                candidate = self.evolver.build_strategy_candidate(
                    user=user,
                    market=market,
                    report=behavior,
                    policy=policy,
                    selected_universe=expanded,
                    feedback=feedback,
                    strategy_type=strategy_type,
                    features=iteration_context["features"],
                )
                candidate_payload = asdict(candidate)
                candidate_payload["version"] = self._strategy_version_label(1, iteration_no, 0, strategy_type)
                self._record_agent_activity("strategy_evolver", "ok", "build_strategy_candidate", f"Built candidate {candidate_payload['version']}.", session.session_id, request_payload={"strategy_type": strategy_type, "objective_metric": objective_metric, "feedback": feedback or ""}, response_payload={"version": candidate_payload["version"], "signal_count": len(candidate_payload.get("signals", [])), "parameter_keys": list(candidate_payload.get("parameters", {}).keys())[:10]})
                previous_failure = self._previous_failure_summary(session)
                dataset_plan = self._build_strategy_dataset_plan(iteration_no, training_window)
                dataset_plan = self._resolve_real_training_dataset_plan(session=session, selected_universe=expanded, dataset_plan=dataset_plan)
                analysis = self._analyze_strategy_iteration(
                    session=session,
                    strategy_type=strategy_type,
                    objective_metric=objective_metric,
                    objective_targets=targets,
                    current_candidate=candidate_payload,
                    previous_failure=previous_failure,
                    feedback=feedback,
                )
                iteration_hypothesis = self.evolver.propose_iteration_hypothesis(
                    strategy_type=strategy_type,
                    objective_metric=objective_metric,
                    analysis=analysis,
                    previous_failure=previous_failure,
                    feedback=feedback,
                )
                plans = self._build_upgrade_plans(strategy_type, analysis, behavior, targets, iteration_hypothesis)
                variant_hypotheses = self.evolver.derive_variant_hypotheses(iteration_hypothesis, plans)
                variants = []
                for variant_index, plan in enumerate(plans, start=1):
                    variant_candidate = self._build_variant_candidate(candidate, plan, variant_index)
                    artifact = self.llm_runtime.generate_strategy_code(
                        strategy_type=strategy_type,
                        selected_universe=expanded,
                        candidate_payload=asdict(variant_candidate),
                        feedback=f"{feedback or ''} | plan={plan['plan_name']}".strip(),
                    )
                    evaluation = self._evaluate_strategy_candidate(
                        asdict(variant_candidate),
                        objective_metric,
                        targets,
                        variant_index,
                        dataset_plan,
                    )
                    variants.append(
                        {
                            "variant_id": plan["variant_id"],
                            "plan": plan,
                            "candidate": asdict(variant_candidate),
                            "generated_code": artifact["code"],
                            "llm_profile": artifact["profile"],
                            "llm_generation_summary": artifact["summary"],
                            "evaluation": evaluation,
                            "hypothesis": next((item for item in variant_hypotheses if item["variant_id"] == plan["variant_id"]), {}),
                        }
                    )
                baseline_evaluation = self._evaluate_strategy_candidate(
                    asdict(baseline_candidate),
                    objective_metric,
                    targets,
                    0,
                    dataset_plan,
                )
                self._assert_real_strategy_training_evaluations(
                    baseline_evaluation=baseline_evaluation,
                    variants=variants,
                )
                winner = self._compare_variant_results(baseline_evaluation, variants)
                selected_check_target = self._resolve_check_target(winner, baseline_payload, baseline_evaluation, variants)
                input_manifest = self._build_input_manifest(
                    selected_universe=expanded,
                    dataset_plan=dataset_plan,
                    features=iteration_context["features"],
                    objective_metric=objective_metric,
                )
                research_summary = self._build_research_summary(
                    strategy_type=strategy_type,
                    objective_metric=objective_metric,
                    baseline_candidate=baseline_payload,
                    baseline_evaluation=baseline_evaluation,
                    variants=variants,
                    winner=winner,
                    selected_check_target=selected_check_target,
                    dataset_plan=dataset_plan,
                )
                self._register_data_bundle(session, input_manifest)
                session.strategy_package = {
                    "iteration_no": iteration_no,
                    "version_label": self._strategy_version_label(1, iteration_no, 0, strategy_type),
                    "strategy_type": strategy_type,
                    "selected_universe": expanded,
                    "feedback": feedback,
                    "iteration_mode": iteration_mode,
                    "auto_iterations_requested": auto_iterations,
                    "objective_metric": objective_metric,
                    "objective_targets": targets,
                    "training_window": training_window or {},
                    "expected_return_range": [0.10, 0.22],
                    "max_potential_loss": -0.12,
                    "expected_drawdown": -0.08,
                    "position_limit": 0.18,
                    "behavioral_compatibility": compatibility,
                    "candidate": candidate_payload,
                    "baseline_candidate": baseline_payload,
                    "dataset_plan": dataset_plan,
                    "feature_snapshot": iteration_context["features"],
                    "feature_snapshot_version": iteration_context["features"].get("meta", {}).get("snapshot_hash"),
                    "data_bundle_id": iteration_context["features"].get("meta", {}).get("data_bundle_id"),
                    "input_manifest": input_manifest,
                    "research_summary": research_summary,
                    "evaluation_protocol": {
                        "selection_target": "highest test objective score",
                        "guardrails": [
                            "validation objective score must remain within tolerance",
                            "walk-forward stability must remain above threshold",
                            "integrity and stress/overfit checks must pass before approval",
                        ],
                    },
                    "baseline_evaluation": baseline_evaluation,
                    "analysis": analysis,
                    "autoresearch_state": {
                        "iteration_hypothesis": iteration_hypothesis,
                        "variant_hypotheses": variant_hypotheses,
                    },
                    "previous_failure_summary": previous_failure,
                    "upgrade_plans": plans,
                    "candidate_variants": variants,
                    "recommended_variant": winner,
                    "selected_check_target": selected_check_target,
                    "llm_profile": variants[0]["llm_profile"] if variants else {},
                    "generated_strategy_code": variants[0]["generated_code"] if variants else "",
                    "llm_generation_summary": variants[0]["llm_generation_summary"] if variants else "",
                    "agent_model_map": self.llm_runtime.agent_matrix(),
                    "task_model_map": self.llm_runtime.describe().get("tasks", {}),
                    "trading_preferences": session.trading_preferences,
                }
                session.strategy_checks = self._run_strategy_checks(session)
                failed_checks = [check for check in session.strategy_checks if check["status"] == "fail"]
                research_summary = self._finalize_research_summary(research_summary, session.strategy_checks)
                repair_route_summary = self._build_unified_repair_route_summary(
                    research_summary,
                    session.programmer_runs[-1] if session.programmer_runs else None,
                )
                autoresearch_cycle_summary = self._build_autoresearch_cycle_summary(
                    iteration_hypothesis=iteration_hypothesis,
                    winner=winner,
                    failed_checks=failed_checks,
                    repair_route_summary=repair_route_summary,
                    research_summary=research_summary,
                )
                autoresearch_memory = self._build_autoresearch_memory(
                    session=session,
                    iteration_hypothesis=iteration_hypothesis,
                    autoresearch_cycle_summary=autoresearch_cycle_summary,
                    failed_checks=failed_checks,
                )
                research_summary["repair_route_summary"] = repair_route_summary
                research_summary["autoresearch_cycle_summary"] = autoresearch_cycle_summary
                research_summary["autoresearch_memory_summary"] = autoresearch_memory
                session.strategy_package["research_summary"] = research_summary
                session.strategy_package["autoresearch_state"]["cycle_summary"] = autoresearch_cycle_summary
                session.strategy_package["autoresearch_state"]["memory"] = autoresearch_memory
                self._record_agent_activity(
                    "strategy_integrity_checker",
                    "error" if any(check["check_type"] == "integrity" and check["status"] == "fail" for check in session.strategy_checks) else "ok",
                    "run_integrity_check",
                    "Completed strategy integrity validation.",
                    session.session_id,
                )
                self._record_agent_activity(
                    "strategy_stress_checker",
                    "error" if any(check["check_type"] == "stress_overfit" and check["status"] == "fail" for check in session.strategy_checks) else "ok",
                    "run_stress_check",
                    "Completed stress and overfit validation.",
                    session.session_id,
                )
                session.strategy_training_log.append(
                    {
                        "timestamp": self._now_iso(),
                        "iteration_no": iteration_no,
                        "loop_index": loop_index + 1,
                        "strategy_type": strategy_type,
                        "iteration_mode": iteration_mode,
                        "objective_metric": objective_metric,
                        "objective_targets": targets,
                        "training_window": training_window or {},
                        "dataset_plan": dataset_plan,
                        "feature_snapshot": iteration_context["features"],
                        "feature_snapshot_version": iteration_context["features"].get("meta", {}).get("snapshot_hash"),
                        "data_bundle_id": iteration_context["features"].get("meta", {}).get("data_bundle_id"),
                        "input_manifest": input_manifest,
                        "research_summary": research_summary,
                        "status": "rework_required" if failed_checks else "checked",
                        "feedback": feedback or "",
                        "analysis_summary": analysis["summary"],
                        "recommended_variant": winner["variant_id"],
                        "selected_check_target": selected_check_target["variant_id"],
                        "recommended_test_score": winner["evaluation"].get("test_objective_score"),
                        "recommended_stability_score": winner["evaluation"].get("stability_score"),
                        "failed_checks": [check["check_type"] for check in failed_checks],
                        "repair_route_summary": repair_route_summary,
                        "iteration_hypothesis": iteration_hypothesis,
                        "autoresearch_cycle_summary": autoresearch_cycle_summary,
                        "autoresearch_memory": autoresearch_memory,
                    }
                )
                research_export = self._build_research_export_manifest(
                    session.strategy_package,
                    session.strategy_training_log[-1],
                )
                self._archive_report(
                    session,
                    report_type="strategy_iteration",
                    title=f"Strategy Iteration {session.strategy_package['version_label']}",
                    body={
                        "strategy_package": session.strategy_package,
                        "strategy_checks": session.strategy_checks,
                        "training_log_entry": session.strategy_training_log[-1],
                        "research_export": research_export,
                    },
                    related_refs=expanded,
                )
                self._append_history_event(
                    session,
                    "strategy_iteration_completed",
                    "策略训练完成一轮迭代。",
                    {
                        "iteration_no": iteration_no,
                        "version_label": session.strategy_package["version_label"],
                        "status": "rework_required" if failed_checks else "checked",
                        "data_bundle_id": session.strategy_package.get("data_bundle_id"),
                        "quality_grade": input_manifest.get("data_quality", {}).get("quality_grade"),
                        "training_readiness": input_manifest.get("data_quality", {}).get("training_readiness", {}).get("status"),
                        "winner_variant_id": research_export.get("winner_variant_id"),
                        "gate_status": research_export.get("gate_status"),
                        "evaluation_source": research_export.get("evaluation_source"),
                        "robustness_grade": research_export.get("robustness_grade"),
                        "research_reliability_status": research_export.get("research_reliability_summary", {}).get("status"),
                        "research_reliability_confidence": research_export.get("research_reliability_summary", {}).get("confidence"),
                        "train_objective_score": research_export.get("research_summary", {}).get("evaluation_snapshot", {}).get("train", {}).get("objective_score"),
                        "validation_objective_score": research_export.get("research_summary", {}).get("evaluation_snapshot", {}).get("validation", {}).get("objective_score"),
                        "test_objective_score": research_export.get("research_summary", {}).get("evaluation_snapshot", {}).get("test", {}).get("objective_score"),
                        "walk_forward_score": research_export.get("research_summary", {}).get("evaluation_snapshot", {}).get("walk_forward_score"),
                        "train_test_gap": research_export.get("research_summary", {}).get("evaluation_snapshot", {}).get("train_test_gap"),
                        "coverage_symbol_count": research_export.get("coverage_summary", {}).get("symbol_count"),
                        "coverage_total_bar_count": research_export.get("coverage_summary", {}).get("total_bar_count"),
                        "coverage_walk_forward_window_count": research_export.get("coverage_summary", {}).get("walk_forward_window_count"),
                        "coverage_grade": research_export.get("coverage_summary", {}).get("coverage_grade"),
                        "coverage_warnings": research_export.get("coverage_summary", {}).get("coverage_warnings"),
                        "repair_route_lane": (research_export.get("primary_repair_route") or {}).get("lane"),
                        "repair_route_priority": (research_export.get("primary_repair_route") or {}).get("priority"),
                        "hypothesis_id": iteration_hypothesis.get("hypothesis_id"),
                        "next_hypothesis": autoresearch_cycle_summary.get("next_hypothesis"),
                        "hypothesis_quality": autoresearch_memory.get("hypothesis_quality"),
                        "hypothesis_convergence": autoresearch_memory.get("convergence_status"),
                    },
                )
                if not failed_checks and iteration_mode != "free":
                    break
            except Exception as exc:
                last_error = str(exc)
                self._record_agent_activity("strategy_evolver", "error", "iterate_strategy", last_error, session.session_id, request_payload={"strategy_type": strategy_type, "objective_metric": objective_metric, "feedback": feedback or "", "loop_index": loop_index + 1}, response_payload={"error": last_error})
                session.strategy_training_log.append(
                    {
                        "timestamp": self._now_iso(),
                        "iteration_no": iteration_no,
                        "loop_index": loop_index + 1,
                        "strategy_type": strategy_type,
                        "iteration_mode": iteration_mode,
                        "status": "error",
                        "feedback": feedback or "",
                        "error": last_error,
                    }
                )
                session.phase = "strategy_rework_required"
                self._append_history_event(
                    session,
                    "strategy_iteration_failed",
                    "策略训练迭代失败。",
                    {
                        "loop_index": loop_index + 1,
                        "strategy_type": strategy_type,
                        "error": last_error,
                    },
                )
                raise ValueError(f"Strategy iteration failed: {last_error}") from exc
        if last_error:
            raise ValueError(last_error)
        session.phase = (
            "strategy_rework_required"
            if any(check["status"] == "fail" for check in session.strategy_checks)
            else "strategy_checked"
        )
        return session

    def _build_strategy_dataset_plan(self, iteration_no: int, training_window: dict | None = None) -> dict:
        normalized_window = self._normalize_training_window(training_window)
        if normalized_window:
            return self._build_strategy_dataset_plan_from_window(normalized_window)
        if self.settings.performance_enabled:
            cached_plan = self._dataset_plan_cache.get(iteration_no)
            if cached_plan is not None:
                self._performance_counters["dataset_plan_hits"] += 1
                return {
                    "cache_mode": "memory_incremental",
                    "cache_hit": True,
                    **cached_plan,
                }
            self._performance_counters["dataset_plan_misses"] += 1

        end_date = datetime.now(timezone.utc).date()
        test_end = end_date - timedelta(days=(iteration_no - 1) * 7)
        test_start = test_end - timedelta(days=89)
        validation_end = test_start - timedelta(days=1)
        validation_start = validation_end - timedelta(days=89)
        train_end = validation_start - timedelta(days=1)
        train_start = train_end - timedelta(days=729)

        walk_forward_windows = []
        for index in range(3):
            anchor_end = validation_end - timedelta(days=index * 90)
            anchor_start = anchor_end - timedelta(days=179)
            eval_end = anchor_end + timedelta(days=45)
            eval_start = anchor_end + timedelta(days=1)
            walk_forward_windows.append(
                {
                    "window_id": f"wf_{index + 1}",
                    "train_start": anchor_start.isoformat(),
                    "train_end": anchor_end.isoformat(),
                    "validation_start": eval_start.isoformat(),
                    "validation_end": eval_end.isoformat(),
                }
            )

        plan = {
            "protocol": "time_series_split_with_walk_forward",
            "train": {
                "start": train_start.isoformat(),
                "end": train_end.isoformat(),
                "days": (train_end - train_start).days + 1,
            },
            "validation": {
                "start": validation_start.isoformat(),
                "end": validation_end.isoformat(),
                "days": (validation_end - validation_start).days + 1,
            },
            "test": {
                "start": test_start.isoformat(),
                "end": test_end.isoformat(),
                "days": (test_end - test_start).days + 1,
            },
            "walk_forward_windows": walk_forward_windows,
            "comparison_rule": "select by test objective score, reject if validation or walk-forward stability falls below threshold",
            "cache_mode": "memory_incremental" if self.settings.performance_enabled else "disabled",
            "cache_hit": False,
        }
        if self.settings.performance_enabled:
            self._dataset_plan_cache[iteration_no] = dict(plan)
            while len(self._dataset_plan_cache) > self.settings.performance_dataset_plan_cache_size:
                first_key = next(iter(self._dataset_plan_cache))
                self._dataset_plan_cache.pop(first_key, None)
        return plan

    def _normalize_training_window(self, training_window: dict | None) -> dict | None:
        if not training_window:
            return None
        start = training_window.get("start")
        end = training_window.get("end")
        if not start or not end:
            return None
        try:
            start_date = date.fromisoformat(str(start))
            end_date = date.fromisoformat(str(end))
        except ValueError as exc:
            raise ValueError("Training start/end dates must use YYYY-MM-DD.") from exc
        if end_date <= start_date:
            raise ValueError("Training end date must be later than training start date.")
        total_days = (end_date - start_date).days + 1
        if total_days < 180:
            raise ValueError("Training window must cover at least 180 days.")
        return {"start": start_date.isoformat(), "end": end_date.isoformat()}

    def _build_strategy_dataset_plan_from_window(self, training_window: dict) -> dict:
        start_date = date.fromisoformat(training_window["start"])
        end_date = date.fromisoformat(training_window["end"])
        total_days = (end_date - start_date).days + 1
        test_days = max(30, min(120, total_days // 6))
        validation_days = max(30, min(120, total_days // 6))
        remaining_train_days = total_days - test_days - validation_days
        if remaining_train_days < 90:
            shortfall = 90 - remaining_train_days
            reduce_validation = min(shortfall // 2 + shortfall % 2, max(0, validation_days - 30))
            reduce_test = min(shortfall - reduce_validation, max(0, test_days - 30))
            validation_days -= reduce_validation
            test_days -= reduce_test
            remaining_train_days = total_days - test_days - validation_days
        if remaining_train_days < 90:
            raise ValueError("Training window is too short to derive train/validation/test splits safely.")

        train_start = start_date
        train_end = train_start + timedelta(days=remaining_train_days - 1)
        validation_start = train_end + timedelta(days=1)
        validation_end = validation_start + timedelta(days=validation_days - 1)
        test_start = validation_end + timedelta(days=1)
        test_end = end_date

        walk_forward_windows = []
        window_count = 3
        validation_span = max(20, min(60, validation_days // 2))
        train_anchor_span = max(120, min(365, remaining_train_days))
        for index in range(window_count):
            eval_end = validation_end - timedelta(days=index * validation_span)
            eval_start = eval_end - timedelta(days=validation_span - 1)
            if eval_start < validation_start:
                continue
            anchor_end = eval_start - timedelta(days=1)
            anchor_start = max(train_start, anchor_end - timedelta(days=train_anchor_span - 1))
            if anchor_end <= anchor_start:
                continue
            walk_forward_windows.append(
                {
                    "window_id": f"wf_{index + 1}",
                    "train_start": anchor_start.isoformat(),
                    "train_end": anchor_end.isoformat(),
                    "validation_start": eval_start.isoformat(),
                    "validation_end": eval_end.isoformat(),
                }
            )

        return {
            "protocol": "time_series_split_with_walk_forward",
            "train": {
                "start": train_start.isoformat(),
                "end": train_end.isoformat(),
                "days": (train_end - train_start).days + 1,
            },
            "validation": {
                "start": validation_start.isoformat(),
                "end": validation_end.isoformat(),
                "days": (validation_end - validation_start).days + 1,
            },
            "test": {
                "start": test_start.isoformat(),
                "end": test_end.isoformat(),
                "days": (test_end - test_start).days + 1,
            },
            "user_selected_window": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": total_days,
            },
            "walk_forward_windows": walk_forward_windows,
            "comparison_rule": "select by test objective score, reject if validation or walk-forward stability falls below threshold",
            "cache_mode": "user_defined_window",
            "cache_hit": False,
        }

    def _build_recent_listing_dataset_plan_from_window(self, training_window: dict) -> dict:
        start_date = date.fromisoformat(training_window["start"])
        end_date = date.fromisoformat(training_window["end"])
        total_days = (end_date - start_date).days + 1
        if total_days < 60:
            raise ValueError(
                "Recent listing data exists, but the available real history is still below 60 days. "
                "Training cannot start yet because there is not enough real data even for a shortened recent-listing split."
            )

        validation_days = max(20, min(40, total_days // 4))
        test_days = max(20, min(40, total_days // 4))
        remaining_train_days = total_days - validation_days - test_days
        if remaining_train_days < 20:
            shortfall = 20 - remaining_train_days
            reduce_validation = min(shortfall // 2 + shortfall % 2, max(0, validation_days - 20))
            reduce_test = min(shortfall - reduce_validation, max(0, test_days - 20))
            validation_days -= reduce_validation
            test_days -= reduce_test
            remaining_train_days = total_days - validation_days - test_days
        if remaining_train_days < 20:
            raise ValueError(
                "Recent listing history is available, but there is still not enough real data to derive safe train/validation/test splits."
            )

        train_start = start_date
        train_end = train_start + timedelta(days=remaining_train_days - 1)
        validation_start = train_end + timedelta(days=1)
        validation_end = validation_start + timedelta(days=validation_days - 1)
        test_start = validation_end + timedelta(days=1)
        test_end = end_date
        walk_forward_windows = []
        eval_span = max(10, min(20, validation_days))
        anchor_span = max(20, min(remaining_train_days, 90))
        eval_start = validation_end - timedelta(days=eval_span - 1)
        anchor_end = eval_start - timedelta(days=1)
        anchor_start = max(train_start, anchor_end - timedelta(days=anchor_span - 1))
        if anchor_end > anchor_start:
            walk_forward_windows.append(
                {
                    "window_id": "wf_recent_1",
                    "train_start": anchor_start.isoformat(),
                    "train_end": anchor_end.isoformat(),
                    "validation_start": eval_start.isoformat(),
                    "validation_end": validation_end.isoformat(),
                }
            )
        return {
            "protocol": "time_series_split_with_walk_forward_recent_listing",
            "train": {
                "start": train_start.isoformat(),
                "end": train_end.isoformat(),
                "days": (train_end - train_start).days + 1,
            },
            "validation": {
                "start": validation_start.isoformat(),
                "end": validation_end.isoformat(),
                "days": (validation_end - validation_start).days + 1,
            },
            "test": {
                "start": test_start.isoformat(),
                "end": test_end.isoformat(),
                "days": (test_end - test_start).days + 1,
            },
            "user_selected_window": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": total_days,
            },
            "walk_forward_windows": walk_forward_windows,
            "comparison_rule": "select by test objective score using the available recent-listing history window; reject if validation or walk-forward stability falls below threshold",
            "cache_mode": "recent_listing_real_data",
            "cache_hit": False,
            "recent_listing_mode": True,
        }

    def _resolve_real_training_dataset_plan(self, *, session: WorkflowSession, selected_universe: list[str], dataset_plan: dict) -> dict:
        history_summary = self._collect_real_training_history(selected_universe)
        common_window = self._common_real_history_window(history_summary)
        if common_window is None:
            raise ValueError(
                "Strategy training requires real market data, but no shared real historical window is available. "
                "Please open the Data Source Expansion workbench, provide API KEY and interface documentation, "
                "let the system generate and apply the data-source integration, then fetch the missing stock history before training."
            )

        requested_start = dataset_plan.get("train", {}).get("start")
        requested_end = dataset_plan.get("test", {}).get("end")
        requested_days = (
            (date.fromisoformat(requested_end) - date.fromisoformat(requested_start)).days + 1
            if requested_start and requested_end
            else 0
        )
        common_days = common_window["days"]
        if requested_start and requested_end and common_window["start"] <= requested_start and common_window["end"] >= requested_end:
            return dataset_plan

        is_recent_listing = common_days < 180 and (date.today() - date.fromisoformat(common_window["start"])).days <= 365
        if is_recent_listing:
            return self._build_recent_listing_dataset_plan_from_window(
                {"start": common_window["start"], "end": common_window["end"]}
            )

        missing_symbols = [item["symbol"] for item in history_summary if not item.get("available")]
        if missing_symbols:
            raise ValueError(
                "Strategy training stopped because real market data is missing for: "
                + ", ".join(missing_symbols)
                + ". Open the Data Source Expansion workbench, provide API KEY and interface documentation, "
                "then let the system call the provider and fetch the missing stock data before retrying."
            )

        raise ValueError(
            "Strategy training stopped because real historical market data is insufficient for the requested training window. "
            f"Requested {requested_days} days, but only {common_days} shared real-data days are available across the selected universe. "
            "Please supplement stock history through the Data Source Expansion workbench by providing API KEY and interface documentation. "
            "The system will use the configured real provider to fetch the required stock data before training."
        )

    def _collect_real_training_history(self, selected_universe: list[str]) -> list[dict]:
        summaries: list[dict] = []
        for symbol in selected_universe:
            resolved = self._fetch_real_training_history(symbol)
            summaries.append(resolved)
        return summaries

    def _fetch_real_training_history(self, symbol: str) -> dict:
        for provider in self.settings.market_data_enabled_providers:
            try:
                history = self.market_data.fetch_history(symbol=symbol, interval="1d", lookback="10y", provider=provider)
            except Exception:
                continue
            bars = history.get("bars") or []
            normalized_dates = [
                str(item.get("timestamp") or item.get("date") or "")[:10]
                for item in bars
                if str(item.get("timestamp") or item.get("date") or "")[:10]
            ]
            if not normalized_dates:
                continue
            sorted_dates = sorted(normalized_dates)
            return {
                "symbol": symbol,
                "available": True,
                "provider": provider,
                "start": sorted_dates[0],
                "end": sorted_dates[-1],
                "days": len(sorted_dates),
            }
        return {
            "symbol": symbol,
            "available": False,
            "provider": None,
            "start": None,
            "end": None,
            "days": 0,
        }

    def _common_real_history_window(self, history_summary: list[dict]) -> dict | None:
        available = [item for item in history_summary if item.get("available") and item.get("start") and item.get("end")]
        if len(available) != len(history_summary):
            return None
        start = max(item["start"] for item in available)
        end = min(item["end"] for item in available)
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
        if end_date < start_date:
            return None
        return {
            "start": start,
            "end": end,
            "days": (end_date - start_date).days + 1,
        }

    def _normalize_objective_targets(self, objective_metric: str, objective_targets: dict) -> dict[str, float]:
        defaults = {
            "target_return_pct": 18.0,
            "target_win_rate_pct": 58.0,
            "target_drawdown_pct": 12.0,
            "target_max_loss_pct": 6.0,
        }
        normalized = {}
        for key, default in defaults.items():
            value = objective_targets.get(key)
            normalized[key] = float(value) if value is not None else default
        normalized["objective_metric"] = objective_metric
        return normalized

    def _strategy_version_label(self, major: int, minor: int, test_no: int, strategy_name: str) -> str:
        normalized_name = str(strategy_name).replace(" ", "_").replace("/", "_")
        return f"V{major}.{minor}-{test_no}-{normalized_name}"

    def _previous_failure_summary(self, session: WorkflowSession) -> dict:
        previous_failures = [
            item for item in reversed(session.strategy_training_log)
            if item.get("status") in {"rework_required", "error"}
        ]
        if not previous_failures:
            return {"exists": False, "summary": "No previous failed iteration.", "failed_checks": [], "last_error": ""}
        latest = previous_failures[0]
        return {
            "exists": True,
            "summary": latest.get("analysis_summary") or latest.get("error") or "Previous strategy iteration failed review.",
            "failed_checks": latest.get("failed_checks", []),
            "last_error": latest.get("error", ""),
        }

    def _analyze_strategy_iteration(
        self,
        session: WorkflowSession,
        strategy_type: str,
        objective_metric: str,
        objective_targets: dict[str, float],
        current_candidate: dict,
        previous_failure: dict,
        feedback: str | None,
    ) -> dict:
        profile = (session.profile_evolution or {}).get("effective_profile") or session.behavioral_report or {}
        issues: list[str] = []
        if float(profile.get("noise_sensitivity", 0.0)) > 0.65:
            issues.append("user is highly sensitive to narrative noise, so signal gating needs to be stricter")
        if float(profile.get("overtrading_tendency", 0.0)) > 0.55:
            issues.append("user tends to overtrade, so turnover and re-entry frequency should be reduced")
        if strategy_type == "mean_reversion_aligned" and float(profile.get("bottom_fishing_tendency", 0.0)) > 0.4:
            issues.append("mean reversion can amplify the user's bottom-fishing bias")
        if previous_failure.get("exists"):
            issues.append(f"previous failure reasons must be addressed: {', '.join(previous_failure.get('failed_checks', [])) or previous_failure.get('summary')}")
        if not issues:
            issues.append("current strategy needs stronger objective alignment and cleaner validation path")
        return {
            "summary": f"Optimize for {objective_metric} while respecting user behavior and previous failures.",
            "objective_metric": objective_metric,
            "objective_targets": objective_targets,
            "current_strategy_problems": issues,
            "previous_failure_reasons": previous_failure,
            "feedback": feedback or "",
            "current_strategy_snapshot": {
                "strategy_type": strategy_type,
                "signal_count": len(current_candidate.get('signals', [])),
                "parameter_count": len(current_candidate.get('parameters', {})),
            },
        }

    def _build_upgrade_plans(
        self,
        strategy_type: str,
        analysis: dict,
        behavior: BehavioralReport,
        objective_targets: dict[str, float],
        iteration_hypothesis: dict,
    ) -> list[dict]:
        return [
            {
                "variant_id": "structural_upgrade",
                "plan_name": "结构化升级方案",
                "focus": "Reduce false positives, tighten entry confirmation, and harden loss containment.",
                "changes": [
                    "raise signal confirmation threshold",
                    "tighten hard stop and drawdown guard",
                    "reduce re-entry frequency after failed setup",
                ],
                "reasoning": analysis["current_strategy_problems"],
                "objective_targets": objective_targets,
                "hypothesis_id": f"{iteration_hypothesis.get('hypothesis_id', 'hyp')}-structural_upgrade",
                "hypothesis_statement": f"Test whether tighter structure can validate: {iteration_hypothesis.get('statement', 'unknown')}",
                "behavior_anchor": {
                    "noise_sensitivity": behavior.noise_susceptibility,
                    "overtrading_tendency": behavior.intervention_risk,
                },
            },
            {
                "variant_id": "strategy_improvement",
                "plan_name": "策略改进方案",
                "focus": "Improve edge capture around the chosen objective without ignoring behavior constraints.",
                "changes": [
                    "reweight signal conviction toward objective metric",
                    "reshape position sizing around target metric",
                    "align exits with current user drawdown tolerance",
                ],
                "reasoning": analysis["current_strategy_problems"],
                "objective_targets": objective_targets,
                "hypothesis_id": f"{iteration_hypothesis.get('hypothesis_id', 'hyp')}-strategy_improvement",
                "hypothesis_statement": f"Test whether edge capture improvements can validate: {iteration_hypothesis.get('statement', 'unknown')}",
                "behavior_anchor": {
                    "panic_sell_tendency": behavior.panic_sell_score,
                    "hold_strength": behavior.discipline_score,
                },
            },
        ]

    def _build_variant_candidate(self, base_candidate, plan: dict, variant_index: int):
        candidate = asdict(base_candidate)
        candidate["version"] = self._strategy_version_label(1, 1, variant_index, plan["variant_id"])
        candidate["metadata"] = dict(candidate.get("metadata", {}))
        candidate["metadata"]["variant_id"] = plan["variant_id"]
        candidate["metadata"]["plan_name"] = plan["plan_name"]
        candidate["metadata"]["focus"] = plan["focus"]
        candidate["metadata"]["hypothesis_id"] = plan.get("hypothesis_id")
        candidate["parameters"] = dict(candidate.get("parameters", {}))
        if plan["variant_id"] == "structural_upgrade":
            for key in ("max_position_pct", "portfolio_drawdown_limit_pct", "hard_stop_loss_pct"):
                if key in candidate["parameters"]:
                    candidate["parameters"][key] = round(float(candidate["parameters"][key]) * 0.9, 4)
        else:
            for signal in candidate.get("signals", []):
                signal["conviction"] = round(min(0.95, float(signal.get("conviction", 0.5)) + 0.06), 4)
            candidate["parameters"]["objective_bias"] = "aggressive_edge_capture"
        candidate["metadata"]["generated_plan_changes"] = " | ".join(plan["changes"])
        from sentinel_alpha.strategies.base import StrategyCandidate, StrategySignal
        return StrategyCandidate(
            strategy_id=candidate["strategy_id"],
            version=candidate["version"],
            strategy_type=candidate["strategy_type"],
            signals=[StrategySignal(**signal) for signal in candidate["signals"]],
            parameters=candidate["parameters"],
            metadata=candidate["metadata"],
        )

    def _evaluate_strategy_candidate(
        self,
        candidate: dict,
        objective_metric: str,
        targets: dict[str, float],
        variant_index: int,
        dataset_plan: dict,
    ) -> dict:
        cache_key = (
            repr(candidate),
            objective_metric,
            repr(targets),
            variant_index,
            repr(dataset_plan),
        )
        if self.settings.performance_enabled:
            cached = self._candidate_eval_cache.get(cache_key)
            if cached is not None:
                self._performance_counters["candidate_eval_hits"] += 1
                return dict(cached)
            self._performance_counters["candidate_eval_misses"] += 1

        evaluation = self.metrics_engine.evaluate_candidate(
            candidate=candidate,
            objective_metric=objective_metric,
            targets=targets,
            variant_index=variant_index,
            dataset_plan=dataset_plan,
            backtest_engine=self.backtest_engine,
            market_data=self.market_data,
            settings=self.settings,
        )
        if self.settings.performance_enabled:
            self._candidate_eval_cache[cache_key] = dict(evaluation)
            while len(self._candidate_eval_cache) > self.settings.performance_dataset_plan_cache_size * 8:
                first_key = next(iter(self._candidate_eval_cache))
                self._candidate_eval_cache.pop(first_key, None)
        return evaluation

    def _assert_real_strategy_training_evaluations(
        self,
        *,
        baseline_evaluation: dict,
        variants: list[dict],
    ) -> None:
        invalid_sources: list[str] = []
        baseline_source = str(baseline_evaluation.get("evaluation_source") or "unknown")
        if baseline_source != "local_history_backtest":
            invalid_sources.append(f"baseline={baseline_source}")
        for variant in variants:
            source = str((variant.get("evaluation") or {}).get("evaluation_source") or "unknown")
            if source != "local_history_backtest":
                invalid_sources.append(f"{variant.get('variant_id', 'unknown')}={source}")
        if invalid_sources:
            raise ValueError(
                "Strategy training requires real historical backtest data only. "
                "Surrogate, heuristic, simulated, stub, or other non-real evaluation sources are forbidden. "
                f"Invalid evaluation sources: {', '.join(invalid_sources)}."
            )

    def _training_market_snapshots(self, session: WorkflowSession) -> list[dict]:
        filtered: list[dict] = []
        for item in session.market_snapshots:
            source = str(item.get("source") or "").strip().lower()
            regime_tag = str(item.get("regime_tag") or "").strip().lower()
            if source.startswith("simulation_market"):
                continue
            if source == "manual":
                continue
            if "simulation" in regime_tag:
                continue
            filtered.append(item)
        return filtered

    def _validate_programmer_changes(self, target_files: list[str]) -> tuple[bool, str]:
        python_targets = [item for item in target_files if str(item).endswith(".py")]
        if python_targets:
            result = subprocess.run(
                ["python", "-m", "py_compile", *python_targets],
                cwd=self.settings.programmer_agent_repo_path,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return False, result.stderr.strip() or result.stdout.strip() or "py_compile failed"
            contract_ok, contract_detail = self._validate_programmer_python_contracts(python_targets)
            if not contract_ok:
                return False, contract_detail

        test_targets = self._candidate_test_targets(target_files)
        if not test_targets:
            return True, "py_compile and contract checks passed; no mapped pytest targets."

        pytest_result = subprocess.run(
            ["python", "-m", "pytest", *test_targets, "-q"],
            cwd=self.settings.programmer_agent_repo_path,
            capture_output=True,
            text=True,
        )
        if pytest_result.returncode == 0:
            return True, f"py_compile, contract checks, and pytest passed for {', '.join(test_targets)}"
        return False, pytest_result.stderr.strip() or pytest_result.stdout.strip() or "pytest failed"

    def _validate_programmer_python_contracts(self, python_targets: list[str]) -> tuple[bool, str]:
        repo_root = Path(self.settings.programmer_agent_repo_path)
        for item in python_targets:
            path = repo_root / item
            if not path.exists():
                return False, f"contract check failed: missing target file {item}"
            try:
                source = path.read_text(encoding="utf-8")
            except OSError as exc:
                return False, f"contract check failed: unable to read {item}: {exc}"
            stripped = source.strip()
            if not stripped:
                return False, f"contract check failed: empty python target {item}"
            if item.startswith("src/") and "class " not in source and "def " not in source and "=" not in source:
                return False, f"contract check failed: no class/function/assignment definitions found in {item}"
        return True, "contract checks passed"

    def _candidate_test_targets(self, target_files: list[str]) -> list[str]:
        repo_root = Path(self.settings.programmer_agent_repo_path)
        discovered: list[str] = []
        for item in target_files:
            path = Path(item)
            if path.parts and path.parts[0] == "tests" and path.suffix == ".py":
                discovered.append(str(path))
                continue
            if path.suffix != ".py":
                continue
            stem = path.stem
            candidate_paths = [
                repo_root / "tests" / f"test_{stem}.py",
                repo_root / "tests" / "agents" / f"test_{stem}.py",
                repo_root / "tests" / "backtesting" / f"test_{stem}.py",
            ]
            for candidate in candidate_paths:
                if candidate.exists():
                    discovered.append(str(candidate.relative_to(repo_root)))
        return list(dict.fromkeys(discovered))

    def _compare_variant_results(self, baseline_evaluation: dict, variants: list[dict]) -> dict:
        def adjusted_score(evaluation: dict) -> float:
            raw = float(evaluation.get("objective_score") or 0.0)
            source = evaluation.get("evaluation_source")
            coverage = evaluation.get("coverage_summary") or {}
            coverage_grade = coverage.get("coverage_grade") or "healthy"
            if source != "local_history_backtest":
                raw -= 0.08
            if coverage_grade == "warning":
                raw -= 0.04
            elif coverage_grade == "degraded":
                raw -= 0.1
            return round(raw, 4)

        best = {
            "variant_id": "baseline",
            "objective_score": baseline_evaluation["objective_score"],
            "adjusted_score": adjusted_score(baseline_evaluation),
            "evaluation": baseline_evaluation,
            "reason": "Baseline remains the strongest current reference.",
        }
        for variant in variants:
            variant_adjusted = adjusted_score(variant["evaluation"])
            if variant_adjusted > best["adjusted_score"]:
                best = {
                    "variant_id": variant["variant_id"],
                    "objective_score": variant["evaluation"]["objective_score"],
                    "adjusted_score": variant_adjusted,
                    "evaluation": variant["evaluation"],
                    "reason": f"{variant['plan']['plan_name']} beats baseline on the adjusted research score after source and coverage penalties.",
                }
        return best

    def _build_research_summary(
        self,
        strategy_type: str,
        objective_metric: str,
        baseline_candidate: dict,
        baseline_evaluation: dict,
        variants: list[dict],
        winner: dict,
        selected_check_target: dict,
        dataset_plan: dict,
    ) -> dict:
        def _result_summary(name: str, version: str, evaluation: dict, plan: dict | None = None) -> dict:
            dataset = evaluation.get("dataset_evaluation") or {}
            return {
                "name": name,
                "version": version,
                "source": evaluation.get("evaluation_source"),
                "objective_score": evaluation.get("objective_score"),
                "test_objective_score": evaluation.get("test_objective_score"),
                "validation_objective_score": evaluation.get("validation_objective_score"),
                "stability_score": evaluation.get("stability_score"),
                "train_test_gap": evaluation.get("train_test_gap"),
                "focus": plan.get("focus") if plan else None,
                "changes": plan.get("changes") if plan else [],
                "train": dataset.get("train"),
                "validation": dataset.get("validation"),
                "test": dataset.get("test"),
            }

        candidates = [
            _result_summary(
                name="baseline",
                version=baseline_candidate.get("version", "baseline"),
                evaluation=baseline_evaluation,
            )
        ]
        for variant in variants:
            candidates.append(
                _result_summary(
                    name=variant.get("variant_id", "unknown"),
                    version=variant.get("candidate", {}).get("version", variant.get("variant_id", "unknown")),
                    evaluation=variant.get("evaluation", {}),
                    plan=variant.get("plan") or {},
                )
            )

        sorted_candidates = sorted(
            candidates,
            key=lambda item: (
                float(item.get("test_objective_score") or 0.0),
                float(item.get("validation_objective_score") or 0.0),
                float(item.get("stability_score") or 0.0),
            ),
            reverse=True,
        )
        winner_id = winner.get("variant_id", "baseline")
        winner_entry = next((item for item in sorted_candidates if item["name"] == winner_id), sorted_candidates[0] if sorted_candidates else {})
        baseline_test = float(baseline_evaluation.get("test_objective_score") or 0.0)
        winner_test = float(winner_entry.get("test_objective_score") or 0.0)
        winner_gain = round(winner_test - baseline_test, 4)
        check_target_eval = selected_check_target.get("evaluation") or {}
        check_target_dataset = check_target_eval.get("dataset_evaluation") or {}
        coverage_summary = self._assess_backtest_coverage(
            check_target_eval.get("coverage_summary") or {},
            check_target_eval.get("evaluation_source"),
        )
        backtest_binding_summary = self._build_backtest_binding_summary(
            evaluation_source=check_target_eval.get("evaluation_source"),
            coverage_summary=coverage_summary,
            robustness_grade="acceptable",
        )
        backtest_quality_summary = self._assess_backtest_quality(
            evaluation_source=check_target_eval.get("evaluation_source"),
            dataset_evaluation=check_target_dataset,
        )
        winner_gap = abs(float(winner_entry.get("train_test_gap") or 0.0))
        winner_stability = float(winner_entry.get("stability_score") or 0.0)
        coverage_warnings = coverage_summary.get("coverage_warnings") or []
        sparse_warning_present = any(item in {"sparse_validation_observations", "sparse_test_observations"} for item in coverage_warnings)
        quality_warnings = backtest_quality_summary.get("warnings") or []
        degraded_quality = backtest_quality_summary.get("grade") == "degraded"
        if (
            winner_stability >= 0.8
            and winner_gap <= 0.12
            and backtest_binding_summary.get("grade") == "strong"
            and coverage_summary.get("coverage_grade") == "healthy"
            and backtest_quality_summary.get("grade") == "healthy"
            and not sparse_warning_present
        ):
            robustness_grade = "strong"
            robustness_note = "The winner remains stable across out-of-sample evaluation and the train-test gap is controlled."
        elif (
            winner_stability >= 0.6
            and winner_gap <= 0.2
            and backtest_binding_summary.get("grade") in {"strong", "partial"}
            and coverage_summary.get("coverage_grade") != "degraded"
            and backtest_quality_summary.get("grade") != "degraded"
            and "sparse_test_observations" not in coverage_warnings
        ):
            robustness_grade = "acceptable"
            robustness_note = "The winner is usable, but stability, sample coverage, or portfolio concentration still needs monitoring."
        else:
            robustness_grade = "fragile"
            robustness_note = "The winner is currently ahead, but robustness is weak, sample coverage may be thin, and backtest quality signals still look too fragile for stronger confidence."
        rejection_summary = []
        for item in sorted_candidates:
            if item["name"] == winner_id:
                continue
            reasons = []
            if float(item.get("test_objective_score") or 0.0) < winner_test:
                reasons.append("weaker out-of-sample test score")
            if float(item.get("validation_objective_score") or 0.0) < float(winner_entry.get("validation_objective_score") or 0.0):
                reasons.append("weaker validation score")
            if float(item.get("stability_score") or 0.0) < winner_stability:
                reasons.append("lower stability")
            if abs(float(item.get("train_test_gap") or 0.0)) > winner_gap:
                reasons.append("larger train-test gap")
            if not reasons:
                reasons.append("lost on the composite ranking tie-breaker")
            rejection_summary.append(
                {
                    "name": item["name"],
                    "version": item["version"],
                    "reason": ", ".join(reasons),
                    "test_objective_score": item.get("test_objective_score"),
                    "validation_objective_score": item.get("validation_objective_score"),
                    "stability_score": item.get("stability_score"),
                    "train_test_gap": item.get("train_test_gap"),
                }
            )
        evaluation_snapshot = {
            "evaluation_source": check_target_eval.get("evaluation_source"),
            "train": check_target_dataset.get("train"),
            "validation": check_target_dataset.get("validation"),
            "test": check_target_dataset.get("test"),
            "walk_forward_windows": len(check_target_dataset.get("walk_forward") or []),
            "walk_forward_score": check_target_dataset.get("stability", {}).get("walk_forward_score"),
            "stability_score": check_target_eval.get("stability_score"),
            "train_test_gap": check_target_dataset.get("stability", {}).get("train_test_gap"),
            "coverage_summary": coverage_summary,
            "backtest_quality_summary": backtest_quality_summary,
        }
        evaluation_highlights = []
        if evaluation_snapshot["test"]:
            evaluation_highlights.append(
                f"Test score {evaluation_snapshot['test'].get('objective_score', 'unknown')} with return {evaluation_snapshot['test'].get('expected_return_pct', 'unknown')}% and drawdown {evaluation_snapshot['test'].get('drawdown_pct', 'unknown')}%."
            )
            evaluation_highlights.append(
                f"Test exposure gross/net {evaluation_snapshot['test'].get('gross_exposure_pct', 'unknown')}%/{evaluation_snapshot['test'].get('net_exposure_pct', 'unknown')}% with turnover proxy {evaluation_snapshot['test'].get('avg_daily_turnover_proxy_pct', 'unknown')}%."
            )
        if evaluation_snapshot["validation"]:
            evaluation_highlights.append(
                f"Validation score {evaluation_snapshot['validation'].get('objective_score', 'unknown')} confirms out-of-sample consistency."
            )
        if evaluation_snapshot["walk_forward_score"] is not None:
            evaluation_highlights.append(
                f"Walk-forward score {evaluation_snapshot['walk_forward_score']} across {evaluation_snapshot['walk_forward_windows']} windows."
            )
        if evaluation_snapshot["train_test_gap"] is not None:
            evaluation_highlights.append(f"Train-test gap is {evaluation_snapshot['train_test_gap']}.")
        if coverage_summary:
            evaluation_highlights.append(
                f"Coverage includes {coverage_summary.get('symbol_count', 'unknown')} symbols and {coverage_summary.get('walk_forward_window_count', 0)} walk-forward windows."
            )
        if backtest_quality_summary:
            evaluation_highlights.append(
                f"Backtest quality is {backtest_quality_summary.get('grade', 'unknown')}: {backtest_quality_summary.get('note', 'no note')}"
            )
            evaluation_highlights.append(
                f"Test active symbols {backtest_quality_summary.get('test_active_symbol_count', 'unknown')} / effective weights {backtest_quality_summary.get('effective_weight_count', 'unknown')} / concentration HHI {backtest_quality_summary.get('concentration_hhi', 'unknown')} / gross exposure {backtest_quality_summary.get('gross_exposure_pct', 'unknown')}% / turnover proxy {backtest_quality_summary.get('avg_daily_turnover_proxy_pct', 'unknown')}%."
            )
        if coverage_summary:
            split_metrics = coverage_summary.get("split_metrics") or {}
            test_metrics = split_metrics.get("test") or {}
            if test_metrics.get("observation_count") is not None:
                evaluation_highlights.append(
                    f"Test observations {test_metrics.get('observation_count')} with sample density {test_metrics.get('sample_density', 'unknown')}."
                )
            if coverage_summary.get("total_bar_count") is not None:
                evaluation_highlights.append(f"Historical bars covered: {coverage_summary.get('total_bar_count')}.")
            if coverage_summary.get("coverage_grade"):
                evaluation_highlights.append(
                    f"Coverage health is {coverage_summary.get('coverage_grade')}: {coverage_summary.get('coverage_health_note', 'no note')}."
                )
        backtest_binding_summary = self._build_backtest_binding_summary(
            evaluation_source=check_target_eval.get("evaluation_source"),
            coverage_summary=coverage_summary,
            robustness_grade=robustness_grade,
        )
        research_reliability_summary = self._build_research_reliability_summary(
            evaluation_source=check_target_eval.get("evaluation_source"),
            coverage_summary=coverage_summary,
            backtest_quality_summary=backtest_quality_summary,
            backtest_binding_summary=backtest_binding_summary,
            robustness_grade=robustness_grade,
        )
        return {
            "objective_metric": objective_metric,
            "strategy_type": strategy_type,
            "dataset_protocol": dataset_plan.get("protocol"),
            "selection_rule": "Select the candidate with the best out-of-sample test score, then validate stability and send only the winner for integrity/stress checks.",
            "candidate_count": len(candidates),
            "winner_selection_summary": {
                "winner_variant_id": winner_id,
                "winner_version": winner_entry.get("version"),
                "winner_test_objective_score": winner_entry.get("test_objective_score"),
                "winner_validation_objective_score": winner_entry.get("validation_objective_score"),
                "winner_stability_score": winner_entry.get("stability_score"),
                "baseline_test_objective_score": baseline_test,
                "winner_advantage_vs_baseline": winner_gain,
                "winner_adjusted_research_score": winner.get("adjusted_score"),
                "reason": winner.get("reason"),
            },
            "check_target_summary": {
                "variant_id": selected_check_target.get("variant_id"),
                "source": selected_check_target.get("source"),
                "evaluation_source": check_target_eval.get("evaluation_source"),
                "test_objective_score": check_target_eval.get("test_objective_score"),
                "stability_score": check_target_eval.get("stability_score"),
                "coverage_summary": coverage_summary,
                "reason": (
                    f"Only the current best candidate ({selected_check_target.get('variant_id')}) proceeds to integrity and stress/overfit validation."
                ),
            },
            "robustness_summary": {
                "grade": robustness_grade,
                "stability_score": winner_stability,
                "train_test_gap": winner_entry.get("train_test_gap"),
                "test_objective_score": winner_entry.get("test_objective_score"),
                "validation_objective_score": winner_entry.get("validation_objective_score"),
                "note": robustness_note,
            },
            "evaluation_snapshot": evaluation_snapshot,
            "evaluation_highlights": evaluation_highlights,
            "backtest_binding_summary": backtest_binding_summary,
            "research_reliability_summary": research_reliability_summary,
            "rejection_summary": rejection_summary,
            "candidate_rankings": [
                {
                    "rank": index + 1,
                    "name": item["name"],
                    "version": item["version"],
                    "source": item.get("source"),
                    "objective_score": item.get("objective_score"),
                    "test_objective_score": item.get("test_objective_score"),
                    "validation_objective_score": item.get("validation_objective_score"),
                    "stability_score": item.get("stability_score"),
                    "train_test_gap": item.get("train_test_gap"),
                    "focus": item.get("focus"),
                    "changes": item.get("changes"),
                }
                for index, item in enumerate(sorted_candidates)
            ],
            "research_summary": (
                f"Using {dataset_plan.get('protocol', 'unknown protocol')}, the current winner is {winner_id} "
                f"with test score {winner_entry.get('test_objective_score', 'unknown')}, "
                f"validation score {winner_entry.get('validation_objective_score', 'unknown')}, "
                f"and stability {winner_entry.get('stability_score', 'unknown')}. "
                f"Relative to baseline, the winner changes the test objective by {winner_gain}."
            ),
        }

    def _assess_backtest_coverage(self, coverage_summary: dict, evaluation_source: str | None) -> dict:
        coverage = dict(coverage_summary or {})
        warnings: list[str] = []
        grade = "healthy"
        note = "Historical coverage is broad enough for research review."
        symbol_count = coverage.get("symbol_count")
        total_bar_count = coverage.get("total_bar_count")
        walk_forward_window_count = coverage.get("walk_forward_window_count") or 0
        split_bar_counts = coverage.get("split_bar_counts") or {}
        validation_bar_count = (split_bar_counts.get("validation") or {}).get("bar_count")
        test_bar_count = (split_bar_counts.get("test") or {}).get("bar_count")
        train_observation_count = ((coverage.get("split_metrics") or {}).get("train") or {}).get("observation_count")
        validation_observation_count = ((coverage.get("split_metrics") or {}).get("validation") or {}).get("observation_count")
        test_observation_count = ((coverage.get("split_metrics") or {}).get("test") or {}).get("observation_count")

        if evaluation_source != "local_history_backtest":
            grade = "warning"
            warnings.append("heuristic_only_no_real_bar_coverage")
            note = "This evaluation used surrogate scoring, so historical bar coverage is not available."
        else:
            if symbol_count is not None and symbol_count < 2:
                warnings.append("narrow_symbol_coverage")
            if total_bar_count is not None and total_bar_count < 120:
                warnings.append("limited_bar_history")
            if walk_forward_window_count < 2:
                warnings.append("limited_walk_forward_windows")
            if validation_bar_count is not None and validation_bar_count < 20:
                warnings.append("short_validation_window")
            if test_bar_count is not None and test_bar_count < 20:
                warnings.append("short_test_window")
            if validation_observation_count is not None and validation_observation_count < 10:
                warnings.append("sparse_validation_observations")
            if test_observation_count is not None and test_observation_count < 10:
                warnings.append("sparse_test_observations")

            if len(warnings) >= 3 or "limited_bar_history" in warnings:
                grade = "degraded"
                note = "Historical coverage is thin, so research conclusions should be treated cautiously."
            elif warnings:
                grade = "warning"
                note = "Historical coverage is usable, but the current dataset is still narrower than ideal."

        coverage["coverage_grade"] = grade
        coverage["coverage_warnings"] = warnings
        coverage["coverage_health_note"] = note
        return coverage

    def _assess_backtest_quality(self, evaluation_source: str | None, dataset_evaluation: dict | None) -> dict:
        source = evaluation_source or "unknown"
        dataset = dataset_evaluation or {}
        test_metrics = dataset.get("test") or {}
        validation_metrics = dataset.get("validation") or {}
        warnings: list[str] = []
        grade = "healthy"
        note = "Backtest quality signals look consistent enough for research review."

        if source != "local_history_backtest":
            grade = "warning"
            warnings.append("heuristic_quality_proxy_only")
            note = "Backtest quality is inferred from surrogate evaluation, so concentration and turnover signals are only provisional."
        else:
            test_active_symbols = int(test_metrics.get("active_symbol_count") or 0)
            validation_active_symbols = int(validation_metrics.get("active_symbol_count") or 0)
            gross_exposure_pct = float(test_metrics.get("gross_exposure_pct") or 0.0)
            net_exposure_pct = abs(float(test_metrics.get("net_exposure_pct") or 0.0))
            turnover_proxy_pct = float(test_metrics.get("avg_daily_turnover_proxy_pct") or 0.0)
            avg_volume = float(test_metrics.get("avg_volume") or 0.0)
            concentration_hhi = float(test_metrics.get("concentration_hhi") or 0.0)
            effective_weight_count = float(test_metrics.get("effective_weight_count") or 0.0)

            if test_active_symbols and test_active_symbols < 2:
                warnings.append("concentrated_test_book")
            if validation_active_symbols and validation_active_symbols < 2:
                warnings.append("concentrated_validation_book")
            if concentration_hhi >= 0.6:
                warnings.append("high_position_concentration")
            if effective_weight_count and effective_weight_count < 2.0:
                warnings.append("thin_effective_weight_count")
            if gross_exposure_pct > 95.0 or net_exposure_pct > 90.0:
                warnings.append("excessive_test_exposure")
            if turnover_proxy_pct > 35.0:
                warnings.append("excessive_turnover_proxy")
            if avg_volume <= 0.0:
                warnings.append("missing_volume_signal")

            if any(item in warnings for item in ("excessive_test_exposure", "high_position_concentration")) or len(warnings) >= 3:
                grade = "degraded"
                note = "Backtest quality is weak because the evaluated book is too concentrated, too exposed, or too noisy in turnover."
            elif warnings:
                grade = "warning"
                note = "Backtest quality is usable, but concentration, effective breadth, exposure, or turnover still limits confidence."

        return {
            "grade": grade,
            "warnings": warnings,
            "note": note,
            "evaluation_source": source,
            "test_active_symbol_count": (dataset.get("test") or {}).get("active_symbol_count"),
            "validation_active_symbol_count": (dataset.get("validation") or {}).get("active_symbol_count"),
            "gross_exposure_pct": (dataset.get("test") or {}).get("gross_exposure_pct"),
            "net_exposure_pct": (dataset.get("test") or {}).get("net_exposure_pct"),
            "avg_daily_turnover_proxy_pct": (dataset.get("test") or {}).get("avg_daily_turnover_proxy_pct"),
            "avg_volume": (dataset.get("test") or {}).get("avg_volume"),
            "concentration_hhi": (dataset.get("test") or {}).get("concentration_hhi"),
            "effective_weight_count": (dataset.get("test") or {}).get("effective_weight_count"),
        }

    def _build_research_reliability_summary(
        self,
        *,
        evaluation_source: str | None,
        coverage_summary: dict,
        backtest_quality_summary: dict,
        backtest_binding_summary: dict,
        robustness_grade: str,
        gate_status: str | None = None,
    ) -> dict:
        coverage_grade = coverage_summary.get("coverage_grade") or "unknown"
        quality_grade = backtest_quality_summary.get("grade") or "unknown"
        binding_grade = backtest_binding_summary.get("grade") or "unknown"
        coverage_warnings = coverage_summary.get("coverage_warnings") or []
        quality_warnings = backtest_quality_summary.get("warnings") or []
        warnings = list(dict.fromkeys([*coverage_warnings, *quality_warnings]))

        if (
            evaluation_source == "local_history_backtest"
            and coverage_grade == "healthy"
            and quality_grade == "healthy"
            and binding_grade == "strong"
            and robustness_grade == "strong"
            and gate_status != "blocked"
        ):
            status = "healthy"
            confidence = "high"
            note = "Research is strongly backed by real historical coverage, healthy backtest quality, broad enough portfolio construction, and a robust winner."
        elif (
            evaluation_source == "heuristic_surrogate"
            or coverage_grade == "degraded"
            or quality_grade == "degraded"
            or robustness_grade == "fragile"
            or gate_status == "blocked"
        ):
            status = "fragile"
            confidence = "low"
            note = "Research is still too provisional because gate blockers, weak backtest quality, thin coverage, or surrogate evaluation remain in play."
        else:
            status = "warning"
            confidence = "medium"
            note = "Research is usable, but still needs another validation pass before it should be treated as a strong baseline, especially when breadth or concentration warnings remain."

        return {
            "status": status,
            "confidence": confidence,
            "evaluation_source": evaluation_source or "unknown",
            "coverage_grade": coverage_grade,
            "quality_grade": quality_grade,
            "binding_grade": binding_grade,
            "robustness_grade": robustness_grade,
            "warnings": warnings,
            "note": note,
        }

    def _build_backtest_binding_summary(self, evaluation_source: str | None, coverage_summary: dict, robustness_grade: str) -> dict:
        source = evaluation_source or "unknown"
        coverage_grade = coverage_summary.get("coverage_grade") or "unknown"
        if source == "local_history_backtest" and coverage_grade == "healthy" and robustness_grade in {"strong", "acceptable"}:
            grade = "strong"
            note = "Research conclusions are anchored by real historical backtest coverage."
        elif source == "local_history_backtest" and coverage_grade in {"healthy", "warning"}:
            grade = "partial"
            note = "Research conclusions use real historical bars, but coverage or robustness still limits confidence."
        elif source == "heuristic_surrogate":
            grade = "weak"
            note = "Research conclusions rely on surrogate evaluation and should not be treated as fully backtest-backed."
        else:
            grade = "weak"
            note = "Backtest linkage is limited, so research conclusions remain provisional."
        return {
            "grade": grade,
            "evaluation_source": source,
            "coverage_grade": coverage_grade,
            "note": note,
        }

    def _finalize_research_summary(self, research_summary: dict, strategy_checks: list[dict]) -> dict:
        failed_checks = [check for check in strategy_checks if check.get("status") == "fail"]
        passed_checks = [check for check in strategy_checks if check.get("status") != "fail"]
        merged = dict(research_summary)
        coverage_summary = merged.get("evaluation_snapshot", {}).get("coverage_summary") or {}
        backtest_quality_summary = merged.get("evaluation_snapshot", {}).get("backtest_quality_summary") or merged.get("backtest_quality_summary") or {}
        gate_blockers: list[str] = []
        if coverage_summary.get("coverage_grade") == "degraded":
            gate_blockers.append("degraded_backtest_coverage")
        coverage_warnings = coverage_summary.get("coverage_warnings") or []
        if "sparse_test_observations" in coverage_warnings:
            gate_blockers.append("sparse_test_observations")
        quality_grade = backtest_quality_summary.get("grade")
        quality_warnings = backtest_quality_summary.get("warnings") or []
        if quality_grade == "degraded":
            gate_blockers.append("degraded_backtest_quality")
        for warning in ("concentrated_test_book", "high_position_concentration", "excessive_test_exposure", "excessive_turnover_proxy"):
            if warning in quality_warnings:
                gate_blockers.append(warning)
        release_ready = not failed_checks and not gate_blockers
        final_release_gate_summary = {
            "release_ready": release_ready,
            "failed_check_count": len(failed_checks),
            "passed_check_count": len(passed_checks),
            "gate_status": "passed" if release_ready else "blocked",
            "coverage_gate_blocked": bool(gate_blockers),
            "gate_blockers": gate_blockers,
            "reason": (
                "The selected winner passed integrity, stress/overfit, and backtest-quality validation."
                if release_ready
                else "The selected winner is blocked by integrity, stress-overfit, and/or backtest-quality validation and must be reworked."
            ),
        }
        check_failure_summary = [
            {
                "check_type": check.get("check_type"),
                "summary": check.get("summary"),
                "score": check.get("score"),
                "required_fix_actions": list(check.get("required_fix_actions") or []),
            }
            for check in failed_checks
        ]
        next_iteration_focus = []
        for check in failed_checks:
            next_iteration_focus.extend(list(check.get("required_fix_actions") or []))
        merged["final_release_gate_summary"] = final_release_gate_summary
        merged["check_failure_summary"] = check_failure_summary
        merged["next_iteration_focus"] = list(dict.fromkeys(next_iteration_focus))
        merged["research_reliability_summary"] = self._build_research_reliability_summary(
            evaluation_source=(merged.get("evaluation_snapshot") or {}).get("evaluation_source"),
            coverage_summary=coverage_summary,
            backtest_quality_summary=backtest_quality_summary,
            backtest_binding_summary=merged.get("backtest_binding_summary") or {},
            robustness_grade=(merged.get("robustness_summary") or {}).get("grade") or "unknown",
            gate_status=final_release_gate_summary.get("gate_status"),
        )
        return merged

    def _build_research_export_manifest(self, strategy_package: dict, training_log_entry: dict) -> dict:
        research = strategy_package.get("research_summary") or training_log_entry.get("research_summary") or {}
        winner = research.get("winner_selection_summary") or {}
        gate = research.get("final_release_gate_summary") or {}
        robustness = research.get("robustness_summary") or {}
        check_target = research.get("check_target_summary") or {}
        quality = strategy_package.get("input_manifest", {}).get("data_quality", {})
        training_quality = training_log_entry.get("input_manifest", {}).get("data_quality", {})
        return {
            "version": strategy_package.get("version_label"),
            "strategy_type": strategy_package.get("strategy_type"),
            "data_bundle_id": strategy_package.get("data_bundle_id") or training_log_entry.get("data_bundle_id"),
            "feature_snapshot_version": strategy_package.get("feature_snapshot_version") or training_log_entry.get("feature_snapshot_version"),
            "quality_grade": quality.get("quality_grade") or training_quality.get("quality_grade"),
            "training_readiness": (
                quality.get("training_readiness", {}).get("status")
                or training_quality.get("training_readiness", {}).get("status")
            ),
            "winner_variant_id": winner.get("winner_variant_id"),
            "gate_status": gate.get("gate_status"),
            "robustness_grade": robustness.get("grade"),
            "check_target_variant_id": check_target.get("variant_id"),
            "evaluation_source": check_target.get("evaluation_source"),
            "coverage_summary": check_target.get("coverage_summary") or {},
            "backtest_binding_summary": research.get("backtest_binding_summary") or {},
            "research_reliability_summary": research.get("research_reliability_summary") or {},
            "next_iteration_focus": research.get("next_iteration_focus") or [],
            "repair_route_summary": research.get("repair_route_summary") or [],
            "primary_repair_route": (research.get("repair_route_summary") or [None])[0],
            "failed_checks": training_log_entry.get("failed_checks") or [],
            "research_summary": research,
        }

    def _build_unified_repair_route_summary(self, research_summary: dict, programmer_run: dict | None) -> list[dict]:
        failed_checks = [item.get("check_type") for item in research_summary.get("check_failure_summary") or [] if item.get("check_type")]
        next_focus = list(research_summary.get("next_iteration_focus") or [])
        final_gate = research_summary.get("final_release_gate_summary") or {}
        programmer_run = programmer_run or {}
        programmer_failure = programmer_run.get("failure_type") or (
            "success" if programmer_run.get("status") == "ok" else programmer_run.get("status") or "unknown"
        )
        programmer_plan = programmer_run.get("repair_plan") or {}
        routes: list[dict] = []

        def add_route(lane: str, priority: str, summary: str, actions: list[str], source: str) -> None:
            routes.append(
                {
                    "lane": lane,
                    "priority": priority,
                    "summary": summary,
                    "actions": list(dict.fromkeys([item for item in actions if item])),
                    "source": source,
                }
            )

        if "integrity" in failed_checks:
            if programmer_failure == "compile_failure":
                add_route(
                    "结构修复",
                    "P0",
                    "先修编译和代码结构，再处理 integrity 规则。",
                    ["修正导入、语法、命名和返回结构", "确保策略输出字段完整", "重新跑 compile + pytest 后再送 integrity 检查"],
                    "research",
                )
            elif programmer_failure in {"validation_failure", "execution_failure"}:
                add_route(
                    "契约修复",
                    "P0",
                    "当前更像契约或运行时不匹配，先对齐接口和 candidate 结构。",
                    ["检查 StrategyCandidate 字段", "检查版本命名和输出契约", "检查 check_target/candidate 对应关系"],
                    "research",
                )
            else:
                add_route(
                    "完整性修复",
                    "P1",
                    "优先按 integrity 失败项修正未来函数、作弊痕迹、硬编码和可疑 rationale。",
                    ["检查 future/leakage 线索", "减少可疑高置信度硬编码", "根据 required_fix_actions 逐项修正"],
                    "research",
                )

        if "stress_overfit" in failed_checks:
            if programmer_failure == "test_failure":
                add_route(
                    "行为修复",
                    "P0",
                    "策略行为和测试预期同时有问题，先修可测试行为，再降复杂度。",
                    ["降低参数密度", "减少过窄 universe 依赖", "优先修复测试暴露出的行为偏差"],
                    "research",
                )
            else:
                add_route(
                    "稳健性修复",
                    "P1",
                    "优先处理过拟合和稳健性问题，降低 train-test gap，提升 walk-forward 稳定性。",
                    ["简化规则和参数", "减少对单一 regime 的依赖", "优先看 validation/test/walk-forward 弱点"],
                    "research",
                )

        if not routes and final_gate.get("gate_status") == "passed":
            add_route(
                "通过态",
                "P2",
                "当前最优版本已通过门控，不需要强制修复，可进入下一轮研究增强。",
                ["保留当前版本作为稳定基线", "如继续迭代，优先探索增益而非修复"],
                "research",
            )

        if not routes and next_focus:
            add_route(
                "默认修复",
                "P1",
                "优先按研究摘要给出的 next_iteration_focus 执行。",
                next_focus,
                "research",
            )

        if not routes:
            add_route(
                "观察",
                "P2",
                "当前没有足够的失败信号，先继续积累更多训练和修复记录。",
                ["继续训练或执行一次 Programmer Agent", "观察 release gate 和失败类型是否收敛"],
                "research",
            )

        if programmer_plan.get("actions"):
            dominant_failure = (
                programmer_run.get("failure_summary", {}).get("dominant_failure_type")
                or programmer_failure
                or "unknown"
            )
            programmer_route = {
                "lane": "代码修复计划",
                "priority": programmer_plan.get("priority") or "P1",
                "summary": f"Programmer Agent 判断当前主导失败为 {dominant_failure}，建议先执行代码侧修复计划。",
                "actions": list(dict.fromkeys(programmer_plan.get("actions") or [])),
                "source": "programmer",
            }
            if routes:
                primary = routes[0]
                priority_order = {"P0": 0, "P1": 1, "P2": 2}
                if priority_order.get(programmer_route["priority"], 2) < priority_order.get(primary["priority"], 2):
                    primary["priority"] = programmer_route["priority"]
                primary["summary"] = f"{primary['summary']} 代码侧主导失败={dominant_failure}。"
                primary["actions"] = list(dict.fromkeys((programmer_route["actions"] or []) + (primary.get("actions") or [])))
                primary["source"] = "research+programmer" if primary.get("source") == "research" else (primary.get("source") or "research+programmer")
                if dominant_failure not in {"success", "unknown"}:
                    routes.append(programmer_route)
            else:
                routes.append(programmer_route)

        return routes

    def _build_autoresearch_cycle_summary(
        self,
        iteration_hypothesis: dict,
        winner: dict,
        failed_checks: list[dict],
        repair_route_summary: list[dict],
        research_summary: dict,
    ) -> dict:
        failed_names = [item.get("check_type") for item in failed_checks if item.get("check_type")]
        primary_route = (repair_route_summary or [None])[0] or {}
        learned = (
            "The current hypothesis produced a releasable winner."
            if not failed_names
            else f"The current hypothesis improved ranking, but the winner still failed: {', '.join(failed_names)}."
        )
        return {
            "hypothesis_id": iteration_hypothesis.get("hypothesis_id"),
            "winner_variant_id": winner.get("variant_id"),
            "learned": learned,
            "failed_checks": failed_names,
            "next_hypothesis": (
                f"Next iteration should stress {primary_route.get('lane', 'the current repair lane')} "
                f"while preserving {winner.get('variant_id', 'winner')} test advantage."
            ),
            "next_focus": list(research_summary.get("next_iteration_focus") or []),
        }

    def _build_autoresearch_memory(
        self,
        session: WorkflowSession,
        iteration_hypothesis: dict,
        autoresearch_cycle_summary: dict,
        failed_checks: list[dict],
    ) -> dict:
        recent_entries = [
            {
                "iteration_no": item.get("iteration_no"),
                "hypothesis_id": (item.get("iteration_hypothesis") or {}).get("hypothesis_id"),
                "focus_problem": (item.get("iteration_hypothesis") or {}).get("focus_problem"),
                "winner_variant_id": (item.get("autoresearch_cycle_summary") or {}).get("winner_variant_id"),
                "failed_checks": (item.get("autoresearch_cycle_summary") or {}).get("failed_checks") or [],
                "next_hypothesis": (item.get("autoresearch_cycle_summary") or {}).get("next_hypothesis"),
            }
            for item in session.strategy_training_log[-4:]
            if item.get("iteration_hypothesis") or item.get("autoresearch_cycle_summary")
        ]
        recent_entries.append(
            {
                "iteration_no": None,
                "hypothesis_id": iteration_hypothesis.get("hypothesis_id"),
                "focus_problem": iteration_hypothesis.get("focus_problem"),
                "winner_variant_id": autoresearch_cycle_summary.get("winner_variant_id"),
                "failed_checks": autoresearch_cycle_summary.get("failed_checks") or [],
                "next_hypothesis": autoresearch_cycle_summary.get("next_hypothesis"),
            }
        )
        focus_set = {item.get("focus_problem") for item in recent_entries if item.get("focus_problem")}
        route_set = {
            item.get("next_hypothesis")
            for item in recent_entries
            if item.get("next_hypothesis")
        }
        if len(recent_entries) >= 3 and len(focus_set) == 1:
            convergence_status = "converging"
            convergence_note = "Recent iterations keep refining the same core problem, so the research loop is converging."
        elif len(focus_set) >= 3 or len(route_set) >= 3:
            convergence_status = "diverging"
            convergence_note = "Recent iterations are changing focus quickly, so the research loop is still exploring or drifting."
        else:
            convergence_status = "learning"
            convergence_note = "The loop is accumulating evidence, but the core repair lane is not fully stable yet."

        if not failed_checks:
            hypothesis_quality = "strong"
            quality_note = "The current hypothesis produced a winner that passed the current release gate."
        elif len(failed_checks) == 1:
            hypothesis_quality = "partial"
            quality_note = "The current hypothesis improved the candidate set, but one major blocker remains."
        else:
            hypothesis_quality = "weak"
            quality_note = "The current hypothesis still leaves multiple blockers unresolved."

        return {
            "hypothesis_quality": hypothesis_quality,
            "quality_note": quality_note,
            "convergence_status": convergence_status,
            "convergence_note": convergence_note,
            "recent_hypotheses": recent_entries,
        }

    def approve_strategy(self, session_id: UUID) -> WorkflowSession:
        session = self.get_session(session_id)
        approved, message = self.risk_guardian.approve(session.strategy_checks)
        if not session.strategy_checks or not approved:
            session.phase = "strategy_rework_required"
            self._record_agent_activity("risk_guardian", "error", "approve_strategy", message, session.session_id)
            raise ValueError(message)
        session.phase = "strategy_approved"
        self._record_agent_activity("risk_guardian", "ok", "approve_strategy", message, session.session_id)
        self._append_history_event(
            session,
            "strategy_approved",
            "策略版本已批准。",
            {"version_label": session.strategy_package.get("version_label") if session.strategy_package else None},
        )
        return session

    def set_deployment(self, session_id: UUID, execution_mode: str) -> WorkflowSession:
        session = self.get_session(session_id)
        deployment = self.portfolio_manager.set_execution_mode(execution_mode)
        session.execution_mode = deployment["execution_mode"]
        session.phase = deployment["phase"]
        self._record_agent_activity("portfolio_manager", "ok", "set_deployment", f"Deployment mode set to {execution_mode}.", session.session_id)
        self._append_history_event(
            session,
            "deployment_mode_updated",
            "执行模式已更新。",
            {"execution_mode": execution_mode},
        )
        return session

    def append_market_snapshot(self, session_id: UUID, snapshot: MarketDataPoint) -> WorkflowSession:
        session = self.get_session(session_id)
        session.market_snapshots.append(asdict(snapshot))
        self._record_agent_activity("market_asset_monitor", "ok", "append_market_snapshot", f"Recorded {snapshot.symbol} {snapshot.timeframe} snapshot.", session.session_id)
        self._append_history_event(
            session,
            "market_snapshot_recorded",
            "市场快照已记录。",
            {"symbol": snapshot.symbol, "timeframe": snapshot.timeframe},
        )
        return session

    def append_trade_record(self, session_id: UUID, trade: TradeExecutionRecord) -> WorkflowSession:
        session = self.get_session(session_id)
        session.trade_records.append(asdict(trade))
        self._apply_trade_evolution(session, trade)
        self._record_agent_activity("user_monitor", "ok", "append_trade_record", f"Recorded {trade.side} trade for {trade.symbol}.", session.session_id)
        self._append_history_event(
            session,
            "trade_recorded",
            "交易记录已入档。",
            {
                "symbol": trade.symbol,
                "side": trade.side,
                "strategy_version": trade.strategy_version,
                "realized_pnl_pct": trade.realized_pnl_pct,
            },
        )
        return session

    def search_intelligence(self, session_id: UUID, query: str, max_documents: int | None = None) -> WorkflowSession:
        session = self.get_session(session_id)
        cache_key = ("search_intelligence", str(session.session_id), query, max_documents or 0)
        cached_run = self._get_intelligence_cache(cache_key)
        if cached_run is not None:
            session.intelligence_documents = cached_run["documents"]
            session.intelligence_runs.append(
                {
                    **cached_run,
                    "run_id": f"intel-{len(session.intelligence_runs) + 1}",
                    "generated_at": self._now_iso(),
                    "cache_hit": True,
                }
            )
            self._record_agent_activity("intelligence_agent", "ok", "search_intelligence", f"Cache hit for query={query}.", session.session_id, request_payload={"query": query, "max_documents": max_documents}, response_payload={"cache_hit": True, "document_count": cached_run.get("document_count"), "source_urls": (cached_run.get("report") or {}).get("source_urls", [])[:5]})
            self._auto_enrich_market_intelligence(session, query)
            return session
        try:
            documents = [asdict(item) for item in self.intelligence.search(query, max_documents)]
        except Exception as exc:
            error_detail = f"{exc.__class__.__name__}: {exc}"
            run = {
                "run_id": f"intel-{len(session.intelligence_runs) + 1}",
                "query": query,
                "generated_at": self._now_iso(),
                "document_count": 0,
                "documents": [],
                "report": {
                    "query": query,
                    "summary": "Intelligence search failed before any documents were collected.",
                    "generation_mode": "error",
                    "error": error_detail,
                    "source_urls": [],
                    "factors": {},
                },
                "cache_hit": False,
                "status": "error",
                "error": error_detail,
            }
            session.intelligence_runs.append(run)
            self._record_agent_activity("intelligence_agent", "error", "search_intelligence", error_detail, session.session_id, request_payload={"query": query, "max_documents": max_documents}, response_payload={"status": "error", "error": error_detail})
            self._archive_report(
                session,
                report_type="intelligence_summary_error",
                title=f"Intelligence Summary Failed: {query}",
                body=run["report"],
                related_refs=[query],
            )
            self._append_history_event(
                session,
                "intelligence_search_failed",
                "情报搜索失败。",
                {"query": query, "error": error_detail},
            )
            return session
        report = self.llm_runtime.summarize_intelligence(query, documents)
        report["factors"] = self._extract_intelligence_factors(documents, report)
        self._record_agent_activity("intelligence_agent", "ok", "search_intelligence", f"Collected {len(documents)} documents for query={query}.", session.session_id, request_payload={"query": query, "max_documents": max_documents}, response_payload={"cache_hit": False, "document_count": len(documents), "source_urls": report.get("source_urls", [])[:5], "factors": report.get("factors") or {}})
        session.intelligence_documents = documents
        run = {
            "run_id": f"intel-{len(session.intelligence_runs) + 1}",
            "query": query,
            "generated_at": self._now_iso(),
            "document_count": len(documents),
            "documents": documents,
            "report": report,
            "cache_hit": False,
        }
        session.intelligence_runs.append(run)
        self._record_information_event(
            session,
            anchor=query,
            category="intelligence",
            summary=f"情报搜索完成，共 {len(documents)} 条文档。",
            factors=report.get("factors") or {},
            provider="multi_source",
            related_refs=report.get("source_urls", []),
        )
        self._set_intelligence_cache(
            cache_key,
            {
                "query": query,
                "document_count": len(documents),
                "documents": documents,
                "report": report,
            },
        )
        self._archive_report(
            session,
            report_type="intelligence_summary",
            title=f"Intelligence Summary: {query}",
            body=report,
            related_refs=report.get("source_urls", []),
        )
        self._append_history_event(
            session,
            "intelligence_search_completed",
            "情报搜索与摘要已完成。",
            {"query": query, "document_count": len(documents)},
        )
        self._auto_enrich_market_intelligence(session, query)
        return session

    def _resolve_market_enrichment_symbols(self, session: WorkflowSession, query: str) -> list[str]:
        trade_universe = session.trade_universe or {}
        symbols = [str(item).strip().upper() for item in (trade_universe.get("requested") or []) if str(item).strip()]
        if not symbols:
            symbols = [str(item).strip().upper() for item in (trade_universe.get("expanded") or []) if str(item).strip()]
        if symbols:
            return list(dict.fromkeys(symbols))[:8]
        inferred = (query or "").strip().upper().split()
        if inferred:
            first = inferred[0]
            if first.isalpha() and len(first) <= 8:
                return [first]
        return []

    def _auto_enrich_market_intelligence(self, session: WorkflowSession, query: str) -> None:
        symbols = self._resolve_market_enrichment_symbols(session, query)
        if not symbols:
            return
        enriched: list[str] = []
        for symbol in symbols:
            try:
                self.fetch_financials_data(session.session_id, symbol)
                self.fetch_dark_pool_data(session.session_id, symbol)
                self.fetch_options_data(session.session_id, symbol)
                enriched.append(symbol)
            except Exception as exc:
                self._record_agent_activity(
                    "intelligence_agent",
                    "warning",
                    "auto_enrich_market_intelligence",
                    f"Auto market enrichment partially failed for {symbol}: {exc}",
                    session.session_id,
                    request_payload={"symbol": symbol, "query": query},
                    response_payload={"status": "partial_failure"},
                )
        if enriched:
            self._append_history_event(
                session,
                "intelligence_market_enriched",
                "情报查询后已自动补充最新市场数据。",
                {"symbols": enriched},
            )

    def fetch_financials_data(self, session_id: UUID, symbol: str, provider: str | None = None) -> WorkflowSession:
        session = self.get_session(session_id)
        cache_key = ("financials", str(session.session_id), symbol, provider or "")
        cached_run = self._get_intelligence_cache(cache_key)
        if cached_run is not None:
            session.financials_runs.append(
                {
                    **cached_run,
                    "run_id": f"financials-{len(session.financials_runs) + 1}",
                    "generated_at": self._now_iso(),
                    "cache_hit": True,
                }
            )
            self._record_agent_activity(
                "intelligence_agent",
                "ok",
                "fetch_financials_data",
                f"Cache hit for financials {symbol} via {cached_run.get('provider')}.",
                session.session_id,
                request_payload={"symbol": symbol, "provider": provider},
                response_payload={"cache_hit": True, "provider": cached_run.get("provider"), "has_payload": bool(cached_run.get("payload"))},
            )
            return session
        try:
            payload = self.market_data.fetch_financials(symbol=symbol, provider=provider)
        except Exception as exc:
            error_detail = f"{exc.__class__.__name__}: {exc}"
            run = {
                "run_id": f"financials-{len(session.financials_runs) + 1}",
                "symbol": symbol,
                "provider": provider,
                "generated_at": self._now_iso(),
                "payload": None,
                "factors": {},
                "cache_hit": False,
                "status": "error",
                "error": error_detail,
            }
            session.financials_runs.append(run)
            self._record_agent_activity("intelligence_agent", "error", "fetch_financials_data", error_detail, session.session_id, request_payload={"symbol": symbol, "provider": provider}, response_payload={"status": "error", "error": error_detail})
            self._archive_report(
                session,
                report_type="financials_summary_error",
                title=f"Financials Data Failed: {symbol}",
                body={"symbol": symbol, "provider": provider, "error": error_detail},
                related_refs=[symbol],
            )
            self._append_history_event(
                session,
                "financials_data_failed",
                "财报数据查询失败。",
                {"symbol": symbol, "provider": provider, "error": error_detail},
            )
            return session
        factors = self._extract_financial_factors(payload)
        run = {
            "run_id": f"financials-{len(session.financials_runs) + 1}",
            "symbol": symbol,
            "provider": payload.get("provider"),
            "generated_at": self._now_iso(),
            "payload": payload,
            "factors": factors,
            "cache_hit": False,
        }
        session.financials_runs.append(run)
        self._record_information_event(
            session,
            anchor=symbol,
            category="financials",
            summary="财报数据已更新。",
            factors=factors,
            provider=payload.get("provider"),
            related_refs=[symbol],
        )
        self._set_intelligence_cache(
            cache_key,
            {
                "symbol": symbol,
                "provider": payload.get("provider"),
                "payload": payload,
            },
        )
        self._archive_report(
            session,
            report_type="financials_summary",
            title=f"Financials Data: {symbol}",
            body={"payload": payload, "factors": factors},
            related_refs=[symbol],
        )
        self._append_history_event(
            session,
            "financials_data_fetched",
            "财报数据查询已完成。",
            {"symbol": symbol, "provider": payload.get("provider")},
        )
        self._record_agent_activity(
            "intelligence_agent",
            "ok",
            "fetch_financials_data",
            f"Fetched financials for {symbol} via {payload.get('provider')}.",
            session.session_id,
            request_payload={"symbol": symbol, "provider": provider},
            response_payload={"provider": payload.get("provider"), "factors": factors},
        )
        return session

    def fetch_dark_pool_data(self, session_id: UUID, symbol: str, provider: str | None = None) -> WorkflowSession:
        session = self.get_session(session_id)
        cache_key = ("dark_pool", str(session.session_id), symbol, provider or "")
        cached_run = self._get_intelligence_cache(cache_key)
        if cached_run is not None:
            session.dark_pool_runs.append(
                {
                    **cached_run,
                    "run_id": f"dark-pool-{len(session.dark_pool_runs) + 1}",
                    "generated_at": self._now_iso(),
                    "cache_hit": True,
                }
            )
            self._record_agent_activity(
                "market_asset_monitor",
                "ok",
                "fetch_dark_pool_data",
                f"Cache hit for dark-pool {symbol} via {cached_run.get('provider')}.",
                session.session_id,
                request_payload={"symbol": symbol, "provider": provider},
                response_payload={"cache_hit": True, "provider": cached_run.get("provider"), "has_payload": bool(cached_run.get("payload"))},
            )
            return session
        try:
            payload = self.market_data.fetch_dark_pool(symbol=symbol, provider=provider)
        except Exception as exc:
            error_detail = f"{exc.__class__.__name__}: {exc}"
            run = {
                "run_id": f"dark-pool-{len(session.dark_pool_runs) + 1}",
                "symbol": symbol,
                "provider": provider,
                "generated_at": self._now_iso(),
                "payload": None,
                "factors": {},
                "cache_hit": False,
                "status": "error",
                "error": error_detail,
            }
            session.dark_pool_runs.append(run)
            self._record_agent_activity("market_asset_monitor", "error", "fetch_dark_pool_data", error_detail, session.session_id, request_payload={"symbol": symbol, "provider": provider}, response_payload={"status": "error", "error": error_detail})
            self._archive_report(
                session,
                report_type="dark_pool_summary_error",
                title=f"Dark Pool Data Failed: {symbol}",
                body={"symbol": symbol, "provider": provider, "error": error_detail},
                related_refs=[symbol],
            )
            self._append_history_event(
                session,
                "dark_pool_data_failed",
                "暗池数据查询失败。",
                {"symbol": symbol, "provider": provider, "error": error_detail},
            )
            return session
        factors = self._extract_dark_pool_factors(payload)
        run = {
            "run_id": f"dark-pool-{len(session.dark_pool_runs) + 1}",
            "symbol": symbol,
            "provider": payload.get("provider"),
            "generated_at": self._now_iso(),
            "payload": payload,
            "factors": factors,
            "cache_hit": False,
        }
        session.dark_pool_runs.append(run)
        self._record_information_event(
            session,
            anchor=symbol,
            category="dark_pool",
            summary="暗池数据已更新。",
            factors=factors,
            provider=payload.get("provider"),
            related_refs=[symbol],
        )
        self._set_intelligence_cache(
            cache_key,
            {
                "symbol": symbol,
                "provider": payload.get("provider"),
                "payload": payload,
            },
        )
        self._archive_report(
            session,
            report_type="dark_pool_summary",
            title=f"Dark Pool Data: {symbol}",
            body={"payload": payload, "factors": factors},
            related_refs=[symbol],
        )
        self._append_history_event(
            session,
            "dark_pool_data_fetched",
            "暗池数据查询已完成。",
            {"symbol": symbol, "provider": payload.get("provider")},
        )
        self._record_agent_activity(
            "market_asset_monitor",
            "ok",
            "fetch_dark_pool_data",
            f"Fetched dark-pool data for {symbol} via {payload.get('provider')}.",
            session.session_id,
            request_payload={"symbol": symbol, "provider": provider},
            response_payload={"provider": payload.get("provider"), "factors": factors},
        )
        return session

    def fetch_options_data(
        self,
        session_id: UUID,
        symbol: str,
        provider: str | None = None,
        expiration: str | None = None,
    ) -> WorkflowSession:
        session = self.get_session(session_id)
        cache_key = ("options", str(session.session_id), symbol, provider or "", expiration or "")
        cached_run = self._get_intelligence_cache(cache_key)
        if cached_run is not None:
            session.options_runs.append(
                {
                    **cached_run,
                    "run_id": f"options-{len(session.options_runs) + 1}",
                    "generated_at": self._now_iso(),
                    "cache_hit": True,
                }
            )
            self._record_agent_activity(
                "strategy_monitor",
                "ok",
                "fetch_options_data",
                f"Cache hit for options {symbol} via {cached_run.get('provider')}.",
                session.session_id,
                request_payload={"symbol": symbol, "provider": provider, "expiration": expiration},
                response_payload={"cache_hit": True, "provider": cached_run.get("provider"), "expiration": cached_run.get("expiration")},
            )
            return session
        try:
            payload = self.market_data.fetch_options(symbol=symbol, provider=provider, expiration=expiration)
        except Exception as exc:
            error_detail = f"{exc.__class__.__name__}: {exc}"
            run = {
                "run_id": f"options-{len(session.options_runs) + 1}",
                "symbol": symbol,
                "provider": provider,
                "expiration": expiration,
                "generated_at": self._now_iso(),
                "payload": None,
                "factors": {},
                "cache_hit": False,
                "status": "error",
                "error": error_detail,
            }
            session.options_runs.append(run)
            self._record_agent_activity("strategy_monitor", "error", "fetch_options_data", error_detail, session.session_id, request_payload={"symbol": symbol, "provider": provider, "expiration": expiration}, response_payload={"status": "error", "error": error_detail})
            self._archive_report(
                session,
                report_type="options_summary_error",
                title=f"Options Data Failed: {symbol}",
                body={"symbol": symbol, "provider": provider, "expiration": expiration, "error": error_detail},
                related_refs=[symbol],
            )
            self._append_history_event(
                session,
                "options_data_failed",
                "期权数据查询失败。",
                {"symbol": symbol, "provider": provider, "expiration": expiration, "error": error_detail},
            )
            return session
        factors = self._extract_options_factors(payload)
        run = {
            "run_id": f"options-{len(session.options_runs) + 1}",
            "symbol": symbol,
            "provider": payload.get("provider"),
            "expiration": expiration,
            "generated_at": self._now_iso(),
            "payload": payload,
            "factors": factors,
            "cache_hit": False,
        }
        session.options_runs.append(run)
        self._record_information_event(
            session,
            anchor=symbol,
            category="options",
            summary="期权数据已更新。",
            factors=factors,
            provider=payload.get("provider"),
            related_refs=[symbol, expiration] if expiration else [symbol],
        )
        self._set_intelligence_cache(
            cache_key,
            {
                "symbol": symbol,
                "provider": payload.get("provider"),
                "expiration": expiration,
                "payload": payload,
            },
        )
        self._archive_report(
            session,
            report_type="options_summary",
            title=f"Options Data: {symbol}",
            body={"payload": payload, "factors": factors},
            related_refs=[symbol],
        )
        self._append_history_event(
            session,
            "options_data_fetched",
            "期权数据查询已完成。",
            {"symbol": symbol, "provider": payload.get("provider"), "expiration": expiration},
        )
        self._record_agent_activity(
            "strategy_monitor",
            "ok",
            "fetch_options_data",
            f"Fetched options data for {symbol} via {payload.get('provider')}.",
            session.session_id,
            request_payload={"symbol": symbol, "provider": provider, "expiration": expiration},
            response_payload={"provider": payload.get("provider"), "expiration": expiration, "factors": factors},
        )
        return session

    def append_information_events(self, session_id: UUID, events: list[dict]) -> WorkflowSession:
        session = self.get_session(session_id)
        normalized_events = self.noise_agent.normalize_events(events)
        session.information_events.extend(normalized_events)
        self._record_agent_activity("noise_agent", "ok", "append_information_events", f"Stored {len(normalized_events)} information events.", session.session_id, request_payload={"count": len(events)}, response_payload={"stored_count": len(normalized_events), "channels": [item.get("channel") for item in normalized_events[:5]]})
        self._append_history_event(
            session,
            "information_events_recorded",
            "信息流事件已记录。",
            {"count": len(normalized_events)},
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
        session = self.get_session(session_id)
        result = self.programmer.execute_with_retries(
            instruction=instruction,
            target_files=target_files,
            context=context,
            commit_changes=commit_changes,
            validator=self._validate_programmer_changes,
        )
        result["timestamp"] = self._now_iso()
        session.programmer_runs.append(result)
        self._archive_report(
            session,
            report_type="programmer_run",
            title=f"Programmer Agent Run {len(session.programmer_runs)}",
            body=result,
            related_refs=result.get("target_files", []),
        )
        self._append_history_event(
            session,
            "programmer_task_completed" if result.get("status") == "ok" else "programmer_task_failed",
            "Programmer Agent completed a coding task." if result.get("status") == "ok" else "Programmer Agent failed a coding task.",
            {
                "status": result.get("status"),
                "commit_hash": result.get("commit_hash"),
                "changed_files": result.get("changed_files", []),
                "repair_chain_status": (result.get("repair_chain_summary") or {}).get("chain_status"),
                "repair_chain_decision": (result.get("repair_chain_summary") or {}).get("primary_decision"),
                "repair_chain_next_mode": (result.get("repair_chain_summary") or {}).get("next_mode"),
                "repair_chain_revalidate": bool((result.get("repair_chain_summary") or {}).get("revalidation_required")),
            },
        )
        self._record_agent_activity(
            "programmer_agent",
            "ok" if result.get("status") == "ok" else "error",
            "execute_programmer_task",
            result.get("error") or f"Changed files: {', '.join(result.get('changed_files', [])) or 'none'}",
            session.session_id,
            request_payload={"instruction": instruction, "target_files": target_files, "commit_changes": commit_changes},
            response_payload={"status": result.get("status"), "commit_hash": result.get("commit_hash"), "changed_files": result.get("changed_files", []), "repair_chain_summary": result.get("repair_chain_summary") or {}},
        )
        return session

    def expand_data_source(
        self,
        session_id: UUID,
        interface_documentation: str,
        api_key: str | None,
        provider_name: str | None,
        category: str | None,
        base_url: str | None,
        api_key_envs: list[str],
        docs_summary: str | None,
        docs_url: str | None = None,
        sample_endpoint: str | None = None,
        auth_style: str | None = None,
        response_format: str | None = None,
    ) -> WorkflowSession:
        session = self.get_session(session_id)
        if not (api_key or api_key_envs):
            raise ValueError("Data-source expansion requires an API key or an API key env binding.")
        if not interface_documentation.strip():
            raise ValueError("Data-source expansion requires interface documentation.")
        analysis = self._analyze_data_source_documentation(
            interface_documentation=interface_documentation,
            provider_name=provider_name,
            category=category,
            base_url=base_url,
            docs_url=docs_url,
            sample_endpoint=sample_endpoint,
            auth_style=auth_style,
            response_format=response_format,
            api_key_envs=api_key_envs,
        )
        request = DataSourceExpansionRequest(
            interface_documentation=interface_documentation,
            api_key=api_key,
            provider_name=provider_name or analysis.get("provider_name"),
            category=category or analysis.get("category"),
            base_url=base_url or analysis.get("base_url"),
            api_key_envs=api_key_envs,
            docs_summary=docs_summary,
            docs_url=docs_url or analysis.get("docs_url"),
            sample_endpoint=sample_endpoint or analysis.get("sample_endpoint"),
            auth_style=auth_style or analysis.get("auth_style"),
            response_format=response_format or analysis.get("response_format"),
            integration_spec=analysis,
        )
        result = self.data_source_expander.build_integration_package(request)
        result["run_id"] = f"datasource-{len(session.data_source_runs) + 1}"
        result["timestamp"] = self._now_iso()
        local_paths = self._persist_data_source_record(
            run=result,
            stage="expand",
            payload=self._sanitize_data_source_run_for_local_storage(result),
        )
        result["local_registry_paths"] = local_paths
        session.data_source_runs.append(result)
        self._archive_report(
            session,
            report_type="data_source_expansion",
            title=f"Data Source Expansion: {result['provider_name']}",
            body=result,
            related_refs=[*( [result.get("inference", {}).get("base_url")] if result.get("inference", {}).get("base_url") else [] ), *( [result.get("inference", {}).get("docs_url")] if result.get("inference", {}).get("docs_url") else [] )],
        )
        self._append_history_event(
            session,
            "data_source_expansion_generated",
            "数据源扩充方案已生成。",
            {
                "provider_name": result["provider_name"],
                "category": result["category"],
                "docs_url": result.get("inference", {}).get("docs_url"),
                "target_module": result["target_module"],
                "target_test": result["target_test"],
                "inferred_fields": result.get("inference", {}).get("inferred_fields", []),
                "analysis_generation_mode": ((result.get("analysis") or {}).get("generation_mode")),
                "analysis_status": ((result.get("analysis") or {}).get("analysis_status")),
                "fallback_reason": ((result.get("analysis") or {}).get("fallback_reason")),
                "local_registry_paths": local_paths,
            },
        )
        self._record_agent_activity(
            "data_source_expansion_agent",
            "ok" if result["validation"]["ready_for_programmer_agent"] else "warning",
            "expand_data_source",
            f"Prepared adapter package for {result['provider_name']} ({result['category']}).",
            session.session_id,
            request_payload={
                **asdict(request),
                "api_key": "[REDACTED]" if api_key else None,
            },
            response_payload={
                "target_module": result["target_module"],
                "target_test": result["target_test"],
                "validation": result["validation"],
                "analysis": result.get("analysis") or {},
                "local_registry_paths": local_paths,
            },
        )
        return session

    def _analyze_data_source_documentation(
        self,
        *,
        interface_documentation: str,
        provider_name: str | None,
        category: str | None,
        base_url: str | None,
        docs_url: str | None,
        sample_endpoint: str | None,
        auth_style: str | None,
        response_format: str | None,
        api_key_envs: list[str],
    ) -> dict:
        fallback_request = DataSourceExpansionRequest(
            interface_documentation=interface_documentation,
            provider_name=provider_name,
            category=category,
            base_url=base_url,
            api_key_envs=api_key_envs,
            docs_url=docs_url,
            sample_endpoint=sample_endpoint,
            auth_style=auth_style,
            response_format=response_format,
        )
        fallback_resolved = self.data_source_expander.analyze_request(fallback_request)
        fallback_spec = dict(fallback_resolved["structured_integration_spec"])
        fallback_spec["analysis_generation_mode"] = "rule_based"
        fallback_spec["analysis_status"] = "heuristic_completed"
        fallback_spec["fallback_reason"] = "live_llm_unavailable"

        prompt_payload = {
            "interface_documentation": interface_documentation,
            "user_overrides": {
                "provider_name": provider_name,
                "category": category,
                "base_url": base_url,
                "docs_url": docs_url,
                "sample_endpoint": sample_endpoint,
                "auth_style": auth_style,
                "response_format": response_format,
                "api_key_envs": api_key_envs,
            },
            "required_output_keys": [
                "provider_name",
                "category",
                "base_url",
                "docs_url",
                "auth_style",
                "auth_header_name",
                "auth_query_param",
                "response_format",
                "sample_endpoint",
                "quote_endpoint",
                "history_endpoint",
                "symbol_param",
                "interval_param",
                "lookback_param",
                "response_root_path",
                "default_headers",
                "default_query_params",
                "pagination_style",
                "error_field_path",
                "notes",
            ],
        }
        fallback_text = json.dumps(fallback_spec, ensure_ascii=False)
        system_prompt = (
            "Return strict JSON only, no markdown and no prose. "
            "You are analyzing a non-structured API documentation excerpt for a market data integration. "
            "Extract a deterministic integration specification that a Python code generator can consume. "
            "Allowed category values: market_data, fundamentals, dark_pool, options. "
            "Allowed auth_style values: header, query, bearer. "
            "Allowed response_format values: json, csv, xml. "
            "If a field is unknown, return an empty string for scalars, {} for maps, [] for notes. "
            "Keep endpoint paths relative, without scheme or host. "
            "default_headers and default_query_params must be JSON objects of string:string. "
            "notes must be a short list of implementation-relevant constraints. "
            "Do not invent vendor names or endpoints unless the documentation strongly implies them. "
            "Output only compact minified JSON."
        )
        try:
            llm_result = self.llm_runtime.invoke_text_task(
                "data_source_doc_analysis",
                json.dumps(prompt_payload, ensure_ascii=False),
                fallback_text=fallback_text,
                system_prompt=system_prompt,
            )
            parsed = self._parse_llm_json(str(llm_result.get("text", "") or ""))
            invocation = dict(llm_result["invocation"])
            profile = llm_result["profile"]
            if isinstance(parsed, dict) and self._is_valid_data_source_spec(parsed):
                sanitized = self._sanitize_data_source_spec(parsed, fallback_spec=fallback_spec)
                sanitized["analysis_generation_mode"] = profile.generation_mode
                sanitized["analysis_status"] = "live_llm_completed" if profile.generation_mode == "live_llm" else "fallback_completed"
                sanitized["fallback_reason"] = invocation.get("fallback_reason")
                sanitized["llm_invocation"] = invocation
                return sanitized
            fallback = dict(fallback_spec)
            fallback["analysis_generation_mode"] = "rule_based"
            fallback["analysis_status"] = "fallback_completed"
            fallback["fallback_reason"] = (
                f"invalid_llm_output:{invocation.get('fallback_reason') or 'invalid_json_shape'}"
            )
            fallback["llm_invocation"] = invocation
            return fallback
        except Exception as exc:
            fallback = dict(fallback_spec)
            fallback["analysis_generation_mode"] = "rule_based"
            fallback["analysis_status"] = "fallback_completed"
            fallback["fallback_reason"] = f"llm_analysis_error:{exc}"
            return fallback

    def _is_valid_data_source_spec(self, payload: dict) -> bool:
        required = [
            "provider_name",
            "category",
            "base_url",
            "auth_style",
            "response_format",
            "quote_endpoint",
            "history_endpoint",
            "symbol_param",
            "interval_param",
            "lookback_param",
        ]
        if not all(key in payload for key in required):
            return False
        category = str(payload.get("category") or "").strip()
        auth_style = str(payload.get("auth_style") or "").strip()
        response_format = str(payload.get("response_format") or "").strip()
        if category not in {"market_data", "fundamentals", "dark_pool", "options"}:
            return False
        if auth_style not in {"header", "query", "bearer"}:
            return False
        if response_format not in {"json", "csv", "xml"}:
            return False
        return True

    def _sanitize_data_source_spec(self, payload: dict, *, fallback_spec: dict) -> dict:
        sanitized = dict(fallback_spec)
        for key in [
            "provider_name",
            "category",
            "base_url",
            "docs_url",
            "auth_style",
            "auth_header_name",
            "auth_query_param",
            "response_format",
            "sample_endpoint",
            "quote_endpoint",
            "history_endpoint",
            "symbol_param",
            "interval_param",
            "lookback_param",
            "response_root_path",
            "pagination_style",
            "error_field_path",
        ]:
            value = payload.get(key)
            if value not in (None, ""):
                sanitized[key] = str(value).strip()
        for key in ["default_headers", "default_query_params"]:
            value = payload.get(key)
            if isinstance(value, dict):
                sanitized[key] = {
                    str(item_key).strip(): str(item_value).strip()
                    for item_key, item_value in value.items()
                    if str(item_key).strip()
                }
        notes = payload.get("notes")
        if isinstance(notes, list):
            sanitized["notes"] = [str(item).strip() for item in notes if str(item).strip()]
        return sanitized

    def _build_programmer_dry_run_result(
        self,
        *,
        instruction: str,
        context: str,
        target_files: list[str],
        summary: str,
        validation_note: str | None = None,
    ) -> dict:
        return {
            "status": "dry_run",
            "failure_type": None,
            "instruction": instruction,
            "context": context,
            "target_files": target_files,
            "stdout": "",
            "stderr": "",
            "returncode": 0,
            "diff": "",
            "changed_files": [],
            "scope_violation": None,
            "attempted_models": [],
            "attempted_api_key_envs": [],
            "commit_hash": None,
            "commit_error": None,
            "rollback_commit": None,
            "head_after_run": None,
            "error": None,
            "validation_ok": True,
            "validation_detail": validation_note or "Dry-run only. No workspace files were modified.",
            "dry_run_summary": summary,
            "attempts": [],
            "failure_summary": {
                "progress_status": "dry_run",
                "progress_note": summary,
            },
            "repair_plan": {
                "recommended_mode": "manual_review_then_commit",
                "steps": [
                    "Review generated module and test content.",
                    "Switch commit_changes to true when ready to write files.",
                    "Re-run compile and pytest after real apply.",
                ],
            },
            "progress_status": "dry_run",
            "progress_note": summary,
            "stop_reason": "dry_run_requested",
            "retry_exhausted": False,
            "no_progress_detected": False,
            "stable_success_required": False,
            "acceptance_summary": {
                "status": "dry_run",
                "detail": summary,
            },
            "rollback_summary": {
                "status": "not_needed",
                "detail": "Dry-run mode did not modify repository state.",
            },
            "promotion_summary": {
                "status": "pending_manual_apply",
                "detail": "Set commit_changes=true to let Programmer Agent write the generated files.",
            },
            "stability_summary": {
                "status": "dry_run",
                "detail": "Execution path verified without workspace mutation.",
            },
            "repair_chain_summary": {
                "chain_status": "dry_run",
                "primary_decision": "manual_review_then_commit",
                "next_mode": "commit_changes=true",
                "revalidation_required": True,
            },
        }

    def apply_data_source_expansion(
        self,
        session_id: UUID,
        run_id: str | None = None,
        commit_changes: bool = True,
    ) -> WorkflowSession:
        session = self.get_session(session_id)
        if not session.data_source_runs:
            raise ValueError("No data-source expansion run is available.")
        selected_run = session.data_source_runs[-1]
        if run_id:
            matched = next((item for item in session.data_source_runs if item.get("run_id") == run_id), None)
            if matched is None:
                raise ValueError(f"Unknown data-source run: {run_id}")
            selected_run = matched

        instruction = (
            f"Create or update the generated adapter module and test for provider "
            f"{selected_run['provider_name']} ({selected_run['category']}). "
            "Use the supplied code verbatim unless a minimal syntax or import correction is required. "
            "Do not modify unrelated files."
        )
        context = (
            f"Target module: {selected_run['target_module']}\n"
            f"Target test: {selected_run['target_test']}\n\n"
            "Write the following module code:\n"
            f"{selected_run['generated_module_code']}\n\n"
            "Write the following test code:\n"
            f"{selected_run['generated_test_code']}\n\n"
            "Generated config fragment:\n"
            f"{selected_run['config_fragment']}"
        )
        target_files = [selected_run["target_module"], selected_run["target_test"]]
        if commit_changes:
            result = self.programmer.execute(
                instruction=instruction,
                target_files=target_files,
                context=context,
                commit_changes=commit_changes,
            )
        else:
            result = self._build_programmer_dry_run_result(
                instruction=instruction,
                context=context,
                target_files=target_files,
                summary=f"Prepared data-source adapter apply plan for {selected_run['provider_name']} without modifying workspace files.",
                validation_note="Dry-run only. Generated module/test payload is ready for manual review or a later committed apply.",
            )
        result["timestamp"] = self._now_iso()
        result["applied_run_id"] = selected_run["run_id"]
        local_apply_paths = self._persist_data_source_record(
            run=selected_run,
            stage="apply",
            payload=self._sanitize_programmer_apply_for_local_storage(result),
        )
        result["local_registry_paths"] = local_apply_paths
        selected_run["programmer_apply"] = result
        session.programmer_runs.append(result)
        self._archive_report(
            session,
            report_type="data_source_programmer_apply",
            title=f"Data Source Apply: {selected_run['provider_name']}",
            body=result,
            related_refs=[selected_run["target_module"], selected_run["target_test"]],
        )
        apply_success = result.get("status") in {"ok", "dry_run"}
        self._append_history_event(
            session,
            "data_source_expansion_applied" if apply_success else "data_source_expansion_apply_failed",
            "数据源扩充结果已生成。"
            if result.get("status") == "dry_run"
            else (
                "数据源扩充结果已交给 Programmer Agent 写入工作区。"
                if result.get("status") == "ok"
                else "数据源扩充结果交给 Programmer Agent 时失败。"
            ),
            {
                "run_id": selected_run["run_id"],
                "status": result.get("status"),
                "commit_hash": result.get("commit_hash"),
                "changed_files": result.get("changed_files", []),
                "repair_chain_status": (result.get("repair_chain_summary") or {}).get("chain_status"),
                "repair_chain_decision": (result.get("repair_chain_summary") or {}).get("primary_decision"),
                "repair_chain_next_mode": (result.get("repair_chain_summary") or {}).get("next_mode"),
                "repair_chain_revalidate": bool((result.get("repair_chain_summary") or {}).get("revalidation_required")),
                "local_registry_paths": local_apply_paths,
            },
        )
        self._record_agent_activity(
            "programmer_agent",
            "ok" if apply_success else "error",
            "apply_data_source_expansion",
            result.get("error") or f"Applied generated adapter for {selected_run['provider_name']}.",
            session.session_id,
            request_payload={"run_id": selected_run["run_id"], "target_module": selected_run["target_module"], "target_test": selected_run["target_test"], "commit_changes": commit_changes},
            response_payload={"status": result.get("status"), "commit_hash": result.get("commit_hash"), "repair_chain_summary": result.get("repair_chain_summary") or {}},
        )
        return session

    def test_data_source_expansion(
        self,
        session_id: UUID,
        run_id: str | None = None,
        symbol: str = "AAPL",
        api_key: str | None = None,
    ) -> WorkflowSession:
        session = self.get_session(session_id)
        if not session.data_source_runs:
            raise ValueError("No data-source expansion run is available.")
        selected_run = session.data_source_runs[-1]
        if run_id:
            matched = next((item for item in session.data_source_runs if item.get("run_id") == run_id), None)
            if matched is None:
                raise ValueError(f"Unknown data-source run: {run_id}")
            selected_run = matched

        result = self._build_data_source_smoke_test(
            selected_run,
            symbol=symbol.strip().upper() or "AAPL",
            api_key=api_key,
        )
        local_test_paths = self._persist_data_source_record(run=selected_run, stage="test", payload=result)
        result["local_registry_paths"] = local_test_paths
        selected_run["smoke_test"] = result
        self._archive_report(
            session,
            report_type="data_source_smoke_test",
            title=f"Data Source Test: {selected_run['provider_name']}",
            body=result,
            related_refs=[selected_run.get("target_module"), selected_run.get("target_test")],
        )
        self._append_history_event(
            session,
            "data_source_expansion_tested",
            "数据源扩展 smoke test 已完成。",
            {
                "run_id": selected_run["run_id"],
                "status": result.get("status"),
                "symbol": result.get("symbol"),
                "live_fetch_status": (result.get("live_fetch") or {}).get("status"),
                "local_registry_paths": local_test_paths,
            },
        )
        self._record_agent_activity(
            "data_source_expansion_agent",
            "ok" if result.get("status") == "ok" else "warning",
            "test_data_source_expansion",
            f"Smoke-tested data-source adapter for {selected_run['provider_name']}.",
            session.session_id,
            request_payload={"run_id": selected_run["run_id"], "symbol": symbol, "api_key": "[REDACTED]" if api_key else None},
            response_payload=result,
        )
        return session

    def expand_trading_terminal(
        self,
        session_id: UUID,
        terminal_name: str,
        terminal_type: str,
        official_docs_url: str,
        docs_search_url: str | None,
        api_base_url: str,
        api_key_envs: list[str],
        auth_style: str,
        order_endpoint: str,
        cancel_endpoint: str,
        order_status_endpoint: str,
        positions_endpoint: str,
        balances_endpoint: str,
        docs_summary: str,
        user_notes: str | None = None,
        response_field_map: dict[str, str] | None = None,
    ) -> WorkflowSession:
        session = self.get_session(session_id)
        request = TradingTerminalIntegrationRequest(
            terminal_name=terminal_name,
            terminal_type=terminal_type,
            official_docs_url=official_docs_url,
            docs_search_url=docs_search_url,
            api_base_url=api_base_url,
            api_key_envs=api_key_envs,
            auth_style=auth_style,
            order_endpoint=order_endpoint,
            cancel_endpoint=cancel_endpoint,
            order_status_endpoint=order_status_endpoint,
            positions_endpoint=positions_endpoint,
            balances_endpoint=balances_endpoint,
            docs_summary=docs_summary,
            user_notes=user_notes,
            response_field_map=response_field_map,
        )
        result = self.terminal_integrator.build_terminal_package(request)
        result["run_id"] = f"terminal-{len(session.terminal_integration_runs) + 1}"
        result["timestamp"] = self._now_iso()
        result["terminal_runtime_summary"] = self._build_terminal_runtime_summary(result)
        result["terminal_reliability_summary"] = self._build_terminal_reliability_summary(result)
        session.terminal_integration_runs.append(result)
        self._archive_report(
            session,
            report_type="trading_terminal_integration",
            title=f"Trading Terminal Integration: {terminal_name}",
            body=result,
            related_refs=[official_docs_url, api_base_url],
        )
        self._append_history_event(
            session,
            "trading_terminal_integration_generated",
            "交易终端接入方案已生成。",
            {
                "terminal_name": terminal_name,
                "terminal_type": terminal_type,
                "target_module": result["target_module"],
                "target_test": result["target_test"],
                "docs_fetch_ok": result["docs_context"]["docs_fetch_ok"],
                "integration_readiness": result.get("integration_readiness_summary", {}).get("status"),
            },
        )
        self._record_agent_activity(
            "trading_terminal_integration_agent",
            "ok" if result["validation"]["ready_for_programmer_agent"] else "warning",
            "expand_trading_terminal",
            f"Prepared terminal adapter package for {terminal_name} ({terminal_type}).",
            session.session_id,
            request_payload=asdict(request),
            response_payload={"target_module": result["target_module"], "target_test": result["target_test"], "validation": result["validation"], "integration_readiness_summary": result.get("integration_readiness_summary") or {}},
        )
        return session

    def apply_trading_terminal_integration(
        self,
        session_id: UUID,
        run_id: str | None = None,
        commit_changes: bool = True,
    ) -> WorkflowSession:
        session = self.get_session(session_id)
        if not session.terminal_integration_runs:
            raise ValueError("No trading-terminal integration run is available.")
        selected_run = session.terminal_integration_runs[-1]
        if run_id:
            matched = next((item for item in session.terminal_integration_runs if item.get("run_id") == run_id), None)
            if matched is None:
                raise ValueError(f"Unknown trading-terminal run: {run_id}")
            selected_run = matched
        instruction = (
            f"Create or update the generated trading terminal adapter and test for "
            f"{selected_run['terminal_name']} ({selected_run['terminal_type']}). "
            "Use the supplied code verbatim unless a minimal syntax or import correction is required. "
            "Do not modify unrelated files."
        )
        context = (
            f"Target module: {selected_run['target_module']}\n"
            f"Target test: {selected_run['target_test']}\n"
            f"Official docs: {selected_run['official_docs_url']}\n"
            f"Docs search: {selected_run.get('docs_search_url') or 'n/a'}\n\n"
            "Write the following module code:\n"
            f"{selected_run['generated_module_code']}\n\n"
            "Write the following test code:\n"
            f"{selected_run['generated_test_code']}\n\n"
            "Generated config candidate:\n"
            f"{selected_run['config_candidate']}"
        )
        target_files = [selected_run["target_module"], selected_run["target_test"]]
        if commit_changes:
            result = self.programmer.execute_with_retries(
                instruction=instruction,
                target_files=target_files,
                context=context,
                commit_changes=commit_changes,
                validator=self._validate_programmer_changes,
            )
        else:
            result = self._build_programmer_dry_run_result(
                instruction=instruction,
                context=context,
                target_files=target_files,
                summary=f"Prepared terminal integration apply plan for {selected_run['terminal_name']} without modifying workspace files.",
                validation_note="Dry-run only. Generated terminal adapter payload is ready for manual review or a later committed apply.",
            )
        result["timestamp"] = self._now_iso()
        result["applied_run_id"] = selected_run["run_id"]
        selected_run["programmer_apply"] = result
        selected_run["terminal_runtime_summary"] = self._build_terminal_runtime_summary(selected_run)
        selected_run["terminal_reliability_summary"] = self._build_terminal_reliability_summary(selected_run)
        session.programmer_runs.append(result)
        self._archive_report(
            session,
            report_type="trading_terminal_programmer_apply",
            title=f"Trading Terminal Apply: {selected_run['terminal_name']}",
            body=result,
            related_refs=[selected_run["target_module"], selected_run["target_test"]],
        )
        apply_success = result.get("status") in {"ok", "dry_run"}
        self._append_history_event(
            session,
            "trading_terminal_integration_applied" if apply_success else "trading_terminal_integration_apply_failed",
            "交易终端接入结果已生成。"
            if result.get("status") == "dry_run"
            else (
                "交易终端接入结果已交给 Programmer Agent 写入工作区。"
                if result.get("status") == "ok"
                else "交易终端接入结果交给 Programmer Agent 时失败。"
            ),
            {
                "run_id": selected_run["run_id"],
                "status": result.get("status"),
                "commit_hash": result.get("commit_hash"),
                "changed_files": result.get("changed_files", []),
            },
        )
        self._record_agent_activity(
            "programmer_agent",
            "ok" if apply_success else "error",
            "apply_trading_terminal_integration",
            result.get("error") or f"Applied terminal adapter for {selected_run['terminal_name']}.",
            session.session_id,
            request_payload={"run_id": selected_run["run_id"], "terminal_name": selected_run["terminal_name"], "target_module": selected_run["target_module"], "target_test": selected_run["target_test"], "commit_changes": commit_changes},
            response_payload={"status": result.get("status"), "commit_hash": result.get("commit_hash"), "repair_chain_summary": result.get("repair_chain_summary") or {}},
        )
        return session

    def test_trading_terminal_integration(
        self,
        session_id: UUID,
        run_id: str | None = None,
    ) -> WorkflowSession:
        session = self.get_session(session_id)
        if not session.terminal_integration_runs:
            raise ValueError("No trading-terminal integration run is available.")
        selected_run = session.terminal_integration_runs[-1]
        if run_id:
            matched = next((item for item in session.terminal_integration_runs if item.get("run_id") == run_id), None)
            if matched is None:
                raise ValueError(f"Unknown trading-terminal run: {run_id}")
            selected_run = matched
        result = self.terminal_integrator.run_smoke_test(selected_run)
        result["timestamp"] = self._now_iso()
        result["run_id"] = selected_run["run_id"]
        selected_run["terminal_test"] = result
        selected_run["terminal_runtime_summary"] = self._build_terminal_runtime_summary(selected_run)
        selected_run["terminal_reliability_summary"] = self._build_terminal_reliability_summary(selected_run)
        checks = result.get("checks", [])
        passed_check_count = sum(1 for item in checks if item.get("status") == "pass")
        readiness = selected_run.get("integration_readiness_summary", {})
        self._archive_report(
            session,
            report_type="trading_terminal_test",
            title=f"Trading Terminal Test: {selected_run['terminal_name']}",
            body={
                **result,
                "terminal_runtime_summary": selected_run.get("terminal_runtime_summary") or {},
                "terminal_reliability_summary": selected_run.get("terminal_reliability_summary") or {},
            },
            related_refs=[selected_run["target_module"], selected_run["target_test"]],
        )
        self._append_history_event(
            session,
            "trading_terminal_test_completed",
            "交易终端接入 smoke test 已完成。",
            {
                "run_id": selected_run["run_id"],
                "terminal_name": selected_run.get("terminal_name"),
                "terminal_type": selected_run.get("terminal_type"),
                "readiness_status": readiness.get("status"),
                "passed_check_count": passed_check_count,
                "total_check_count": len(checks),
                "status": result.get("status"),
                "summary": result.get("summary"),
                "repair_route": result.get("repair_summary", {}).get("primary_route"),
                "repair_priority": result.get("repair_summary", {}).get("priority"),
                "reliability_status": (selected_run.get("terminal_reliability_summary") or {}).get("status"),
                "reliability_revalidate": bool((selected_run.get("terminal_reliability_summary") or {}).get("revalidation_required")),
                "reliability_next_action": (selected_run.get("terminal_reliability_summary") or {}).get("next_action"),
            },
        )
        self._record_agent_activity(
            "trading_terminal_integration_agent",
            "ok" if result.get("status") == "ok" else "warning",
            "test_trading_terminal_integration",
            result.get("summary") or f"Tested terminal adapter for {selected_run['terminal_name']}.",
            session.session_id,
            request_payload={"run_id": selected_run["run_id"], "terminal_name": selected_run["terminal_name"]},
            response_payload={"status": result.get("status"), "summary": result.get("summary"), "repair_summary": result.get("repair_summary") or {}, "terminal_reliability_summary": selected_run.get("terminal_reliability_summary") or {}},
        )
        return session

    def _build_terminal_reliability_summary(self, run: dict) -> dict:
        readiness = run.get("integration_readiness_summary") or {}
        runtime = run.get("terminal_runtime_summary") or {}
        test = run.get("terminal_test") or {}
        repair = test.get("repair_summary") or {}
        checks = test.get("checks") or []
        shape_checks = [item for item in checks if str(item.get("name") or "").endswith("_shape")]
        passed = sum(1 for item in checks if item.get("status") == "pass")
        shape_passed = sum(1 for item in shape_checks if item.get("status") == "pass")
        total = len(checks)
        contract_confidence = runtime.get("contract_confidence")
        if contract_confidence is None:
            contract_confidence = round(passed / max(1, total), 4)
        shape_confidence = runtime.get("shape_confidence")
        if shape_confidence is None and shape_checks:
            shape_confidence = round(shape_passed / max(1, len(shape_checks)), 4)

        readiness_status = readiness.get("status") or runtime.get("readiness_status") or "unknown"
        runtime_status = runtime.get("status") or "unknown"
        test_status = test.get("status") or runtime.get("test_status") or "not_tested"
        docs_fetch_ok = bool((run.get("docs_context") or {}).get("docs_fetch_ok"))
        field_map = ((run.get("config_candidate") or {}).get("provider_config") or {}).get("response_field_map") or {}
        field_map_ready = bool(field_map)

        if (
            readiness_status == "ready"
            and runtime_status == "healthy"
            and test_status == "ok"
            and docs_fetch_ok
            and field_map_ready
            and float(contract_confidence or 0.0) >= 0.95
            and (shape_confidence is None or float(shape_confidence) >= 1.0)
        ):
            status = "healthy"
            note = "Terminal package is reliable enough for sustained integration work and stronger endpoint verification."
            next_action = "Proceed to deeper endpoint verification while keeping periodic smoke-test revalidation."
            revalidation_required = False
        elif (
            readiness_status == "blocked"
            or runtime_status == "fragile"
            or test_status in {"warning", "error"}
            or not docs_fetch_ok
            or not field_map_ready
            or float(contract_confidence or 0.0) < 0.6
            or (shape_confidence is not None and float(shape_confidence) < 0.67)
        ):
            status = "fragile"
            note = "Terminal package is not reliable enough yet; fix readiness, contract failures, field mapping, or payload shape issues first."
            next_action = (repair.get("actions") or [runtime.get("next_action") or "Return to the terminal integration page and repair failed contracts before depending on this package."])[0]
            revalidation_required = True
        else:
            status = "warning"
            note = "Terminal package is partially reliable, but still needs another controlled validation pass before stronger dependence."
            next_action = runtime.get("next_action") or "Rerun readiness and smoke tests after reviewing endpoint coverage and field mapping."
            revalidation_required = True

        return {
            "status": status,
            "note": note,
            "readiness_status": readiness_status,
            "runtime_status": runtime_status,
            "test_status": test_status,
            "docs_fetch_ok": docs_fetch_ok,
            "field_map_ready": field_map_ready,
            "contract_confidence": contract_confidence,
            "shape_confidence": shape_confidence,
            "passed_check_count": passed,
            "total_check_count": total,
            "next_action": next_action,
            "primary_route": runtime.get("primary_route") or repair.get("primary_route") or "none",
            "revalidation_required": revalidation_required,
        }

    def _build_terminal_runtime_summary(self, run: dict) -> dict:
        readiness = run.get("integration_readiness_summary") or {}
        test = run.get("terminal_test") or {}
        repair = test.get("repair_summary") or {}
        checks = test.get("checks") or []
        passed = sum(1 for item in checks if item.get("status") == "pass")
        shape_checks = [item for item in checks if str(item.get("name") or "").endswith("_shape")]
        shape_passed = sum(1 for item in shape_checks if item.get("status") == "pass")
        readiness_status = readiness.get("status") or "unknown"
        test_status = test.get("status") or "not_tested"
        total_count = len(checks)
        contract_confidence = round(passed / max(1, total_count), 4)
        shape_confidence = round(shape_passed / max(1, len(shape_checks)), 4) if shape_checks else None
        if test_status == "ok" and readiness_status == "ready" and contract_confidence >= 0.95 and (shape_confidence is None or shape_confidence >= 1.0):
            return {
                "status": "healthy",
                "readiness_status": readiness_status,
                "test_status": test_status,
                "passed_check_count": passed,
                "total_check_count": total_count,
                "contract_confidence": contract_confidence,
                "shape_confidence": shape_confidence,
                "note": "Terminal package is ready for the next connectivity stage with strong smoke-test coverage.",
                "next_action": "Proceed to stronger endpoint verification or controlled local integration.",
                "primary_route": repair.get("primary_route") or "none",
            }
        if readiness_status == "blocked" or test_status in {"warning", "error"} or contract_confidence < 0.6 or (shape_confidence is not None and shape_confidence < 0.67):
            return {
                "status": "fragile",
                "readiness_status": readiness_status,
                "test_status": test_status,
                "passed_check_count": passed,
                "total_check_count": total_count,
                "contract_confidence": contract_confidence,
                "shape_confidence": shape_confidence,
                "note": "Terminal package is not ready yet. Fix readiness gaps, failed smoke-test contracts, or weak payload-shape coverage first.",
                "next_action": (repair.get("actions") or ["Return to the terminal integration page and fix the failed contract or endpoint."])[0],
                "primary_route": repair.get("primary_route") or "data_shape_repair",
            }
        return {
            "status": "warning",
            "readiness_status": readiness_status,
            "test_status": test_status,
            "passed_check_count": passed,
            "total_check_count": total_count,
            "contract_confidence": contract_confidence,
            "shape_confidence": shape_confidence,
            "note": "Terminal package has partial readiness but still needs another validation pass.",
            "next_action": "Run or rerun smoke tests after reviewing endpoint coverage and field mapping.",
            "primary_route": repair.get("primary_route") or "readiness_review",
        }

    def compose_market_template_campaign(
        self,
        day_count: int = 40,
        required_shapes: list[str] | None = None,
        required_regimes: list[str] | None = None,
        baseline_open: float = 100.0,
        seed: int = 11,
    ) -> list[dict]:
        return []

    def market_template_coverage(self) -> dict:
        return {
            "status": "unavailable",
            "required_shapes": ["w", "n", "v", "a", "box", "trend"],
            "required_regimes": ["bull", "bear", "oscillation", "fake_reversal", "gap"],
            "shape_counts": {},
            "regime_counts": {},
            "missing_shapes": ["w", "n", "v", "a", "box", "trend"],
            "missing_regimes": ["bull", "bear", "oscillation", "fake_reversal", "gap"],
            "matrix": [],
        }

    def monitor_signals(self, session_id: UUID) -> list[dict]:
        session = self.get_session(session_id)
        signals = [
            self.user_monitor.generate_signal(session.behavioral_report),
            self.strategy_monitor.generate_signal(session.strategy_package),
            self.market_asset_monitor.generate_signal(session.strategy_package, session.trade_universe),
        ]
        self._record_agent_activity("user_monitor", "ok", "monitor_signals", signals[0]["detail"], session.session_id)
        self._record_agent_activity("strategy_monitor", "ok", "monitor_signals", signals[1]["detail"], session.session_id)
        self._record_agent_activity("market_asset_monitor", "ok", "monitor_signals", signals[2]["detail"], session.session_id)
        return signals

    def system_health(self) -> dict:
        static_dir = Path(__file__).resolve().parents[1] / "webapp" / "static"
        nicegui_app = Path(__file__).resolve().parents[1] / "nicegui" / "app.py"
        frontend_pages = [
            "index.html",
            "pages/session.html",
            "pages/simulation.html",
            "pages/report.html",
            "pages/preferences.html",
            "pages/configuration.html",
            "pages/data-source-expansion.html",
            "pages/trading-terminal-integration.html",
            "pages/strategy.html",
            "pages/intelligence.html",
            "pages/operations.html",
        ]
        missing_pages = [name for name in frontend_pages if not (static_dir / name).exists()]
        modules = [
            self._module_status("config", "ok", f"Loaded from {self.settings.config_path}.", "Keep deployment overrides aligned with the config contract."),
            self._module_status("workflow_service", "ok", f"{self.__class__.__name__} is active.", "No action required."),
            self._module_status("scenario_generator", "ok", "Scenario generator is attached with deterministic replay behavior.", "No action required."),
            self._module_status("behavioral_profiler", "ok", "Behavioral profiler is attached.", "No action required."),
            self._module_status(
                "intelligence_agent",
                "ok" if self.settings.intelligence_enabled else "warning",
                "Intelligence agent is attached." if self.settings.intelligence_enabled else "Intelligence agent is present but disabled by config.",
                "Enable intelligence in config if external news retrieval should participate in workflow." if not self.settings.intelligence_enabled else "No action required.",
            ),
            self._module_status("strategy_evolver", "ok", "Strategy evolver is attached.", "No action required."),
            self._module_status(
                "programmer_agent",
                "ok" if self.settings.programmer_agent_enabled else "warning",
                "Programmer Agent is attached." if self.settings.programmer_agent_enabled else "Programmer Agent is present but disabled by config.",
                "Enable programmer_agent.enabled and install aider to allow controlled code modification." if not self.settings.programmer_agent_enabled else "No action required.",
            ),
            self._module_status("trading_terminal_integration_agent", "ok", "Trading Terminal Integration Agent is attached.", "No action required."),
            self._module_status("strategy_registry", "ok", f"Registered strategies: {', '.join(self.strategy_registry.list_types())}.", "Register new strategy implementations here before exposing them to workflow."),
            self._module_status("monitoring_agents", "ok", "User, strategy, and market monitors are enabled in workflow.", "No action required."),
            self._module_status("strategy_check_agents", "ok", "Integrity checker and stress/overfit checker are enforced before approval.", "No action required."),
            self._module_status(
                "web_module",
                "ok" if nicegui_app.exists() and not missing_pages else "error",
                "NiceGUI frontend is present and legacy redirect shells are intact."
                if nicegui_app.exists() and not missing_pages
                else (
                    f"Missing NiceGUI app: {nicegui_app}."
                    if not nicegui_app.exists()
                    else f"Missing redirect shells: {', '.join(missing_pages)}."
                ),
                "No action required."
                if nicegui_app.exists() and not missing_pages
                else (
                    "Restore src/sentinel_alpha/nicegui/app.py before shipping."
                    if not nicegui_app.exists()
                    else "Restore redirect shells under src/sentinel_alpha/webapp/static/pages before shipping."
                ),
            ),
            self._module_status(
                "storage_layer",
                "ok",
                f"Workflow sessions persist via {getattr(self, 'session_store_backend', 'memory')}.",
                "No action required." if getattr(self, 'session_store_backend', 'memory') != "memory" else "Enable persistence to avoid Session not found after restarts.",
            ),
        ]
        modules.extend(self.programmer.health_modules())
        modules.extend(self.llm_runtime.system_health_modules())
        overall = "ok"
        if any(item["status"] == "error" for item in modules):
            overall = "degraded"
        elif any(item["status"] == "warning" for item in modules):
            overall = "warning"
        return {
            "status": overall,
            "service_mode": self.settings.app_mode,
            "timestamp": self._now_iso(),
            "modules": modules,
            "libraries": self._library_diagnostics(),
            "agents": self._agent_diagnostics(),
            "performance": self._performance_snapshot(),
            "data_health": self._data_health_snapshot(),
            "runtime_health": self._runtime_health_summary(),
            "recent_agent_logs": self.agent_activity_log[-30:],
            "recent_errors": [item for item in self.agent_activity_log if item["status"] == "error"][-10:],
            "token_usage": self.llm_runtime.usage_snapshot(),
        }

    def llm_config(self) -> dict:
        return self.llm_runtime.describe()

    def history(self, session_id: UUID) -> list[dict]:
        return self.get_session(session_id).history_events

    def reports(self, session_id: UUID) -> list[dict]:
        return self.get_session(session_id).report_history

    def _run_strategy_checks(self, session: WorkflowSession) -> list[dict]:
        behavior = (session.profile_evolution or {}).get("effective_profile") or session.behavioral_report or {}
        strategy = session.strategy_package or {}
        check_target = strategy.get("selected_check_target") or {}
        candidate = check_target.get("candidate") or strategy.get("candidate") or {}
        compatibility = strategy.get("behavioral_compatibility", 0.0)
        return [
            self.strategy_integrity_checker.evaluate(strategy, candidate),
            self.strategy_stress_checker.evaluate(strategy, candidate, behavior, compatibility),
        ]

    def _resolve_check_target(
        self,
        winner: dict,
        baseline_candidate: dict,
        baseline_evaluation: dict,
        variants: list[dict],
    ) -> dict:
        winner_id = winner.get("variant_id")
        if winner_id == "baseline":
            return {
                "variant_id": "baseline",
                "candidate": baseline_candidate,
                "evaluation": baseline_evaluation,
                "source": "baseline_candidate",
            }
        selected_variant = next((item for item in variants if item.get("variant_id") == winner_id), None)
        if selected_variant is None:
            return {
                "variant_id": "baseline",
                "candidate": baseline_candidate,
                "evaluation": baseline_evaluation,
                "source": "baseline_candidate_fallback",
            }
        return {
            "variant_id": selected_variant["variant_id"],
            "candidate": selected_variant["candidate"],
            "evaluation": selected_variant["evaluation"],
            "source": "candidate_variant",
        }

    def _effective_behavior_report(self, session: WorkflowSession) -> BehavioralReport:
        profile = (session.profile_evolution or {}).get("effective_profile") or session.behavioral_report
        if profile:
            return BehavioralReport(
                panic_sell_score=float(profile.get("panic_sell_tendency", 0.0)),
                averaging_down_score=float(profile.get("bottom_fishing_tendency", 0.0)),
                noise_susceptibility=float(profile.get("noise_sensitivity", 0.0)),
                intervention_risk=float(profile.get("overtrading_tendency", 0.0)),
                max_comfort_drawdown_pct=abs(float(profile.get("loss_tolerance", -12.0))),
                discipline_score=float(profile.get("hold_strength", 0.5)),
                notes=list(profile.get("notes", [])) if isinstance(profile.get("notes", []), list) else [],
            )

    def _get_iteration_context(
        self,
        session: WorkflowSession,
        strategy_type: str,
        expanded: list[str],
    ) -> dict:
        profile = (session.profile_evolution or {}).get("effective_profile") or session.behavioral_report or {}
        cache_key = (
            str(session.session_id),
            strategy_type,
            tuple(expanded),
            self._target_holding_days(session.trading_preferences),
            repr(profile),
        )
        if self.settings.performance_enabled:
            cached = self._iteration_context_cache.get(cache_key)
            if cached is not None:
                self._performance_counters["iteration_context_hits"] += 1
                return cached
            self._performance_counters["iteration_context_misses"] += 1

        features = self.feature_pipeline.build(
            behavioral_report=session.behavioral_report,
            profile_evolution=session.profile_evolution,
            trading_preferences=session.trading_preferences,
            market_snapshots=self._training_market_snapshots(session),
            intelligence_runs=session.intelligence_runs,
            financials_runs=session.financials_runs,
            dark_pool_runs=session.dark_pool_runs,
            options_runs=session.options_runs,
        )

        latest_market = features["market"]
        base_trend = 0.58 if strategy_type == "trend_following_aligned" else 0.18 if strategy_type == "mean_reversion_aligned" else 0.42
        base_event_risk = 0.32

        market = MarketSnapshot(
            symbol=latest_market.get("symbol") or expanded[0],
            expected_return_pct=16.0,
            realized_volatility_pct=28.0,
            trend_score=base_trend,
            event_risk_score=base_event_risk,
            liquidity_score=0.92,
        )
        user = UserProfile(
            user_id=str(session.session_id),
            preferred_assets=expanded,
            capital_base=session.starting_capital,
            target_holding_days=self._target_holding_days(session.trading_preferences),
            self_reported_risk_tolerance=0.5,
            confidence_level=0.55,
        )
        behavior = self._effective_behavior_report(session)
        policy = self.evolver.derive_risk_policy(user, behavior)
        context = {
            "market": market,
            "user": user,
            "behavior": behavior,
            "policy": policy,
            "features": features,
        }
        if self.settings.performance_enabled:
            self._iteration_context_cache[cache_key] = context
            while len(self._iteration_context_cache) > self.settings.performance_dataset_plan_cache_size:
                first_key = next(iter(self._iteration_context_cache))
                self._iteration_context_cache.pop(first_key, None)
        return context

    def _performance_snapshot(self) -> dict:
        return {
            "enabled": self.settings.performance_enabled,
            "mode": "memory_incremental" if self.settings.performance_enabled else "disabled",
            "dataset_plan_cache": {
                "entries": len(self._dataset_plan_cache),
                "max_entries": self.settings.performance_dataset_plan_cache_size,
                "hits": self._performance_counters["dataset_plan_hits"],
                "misses": self._performance_counters["dataset_plan_misses"],
            },
            "iteration_context_cache": {
                "entries": len(self._iteration_context_cache),
                "max_entries": self.settings.performance_dataset_plan_cache_size,
                "hits": self._performance_counters["iteration_context_hits"],
                "misses": self._performance_counters["iteration_context_misses"],
            },
            "candidate_evaluation_cache": {
                "entries": len(self._candidate_eval_cache),
                "max_entries": self.settings.performance_dataset_plan_cache_size * 8,
                "hits": self._performance_counters["candidate_eval_hits"],
                "misses": self._performance_counters["candidate_eval_misses"],
            },
            "intelligence_cache": {
                "entries": len(self._intelligence_cache),
                "max_entries": self.settings.performance_market_data_cache_size,
                "hits": self._performance_counters["intelligence_hits"],
                "misses": self._performance_counters["intelligence_misses"],
            },
            "market_data_cache": self.market_data.cache_stats(),
            "llm_cache": self.llm_runtime.cache_stats(),
        }

    def _hours_since_iso(self, timestamp: str | None) -> float | None:
        if not timestamp:
            return None
        raw = str(timestamp).strip()
        if not raw:
            return None
        try:
            normalized = raw.replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalized)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt = dt.astimezone(timezone.utc)
            return round((datetime.now(timezone.utc) - dt).total_seconds() / 3600, 2)
        except Exception:
            return None

    def _data_health_snapshot(self) -> dict:
        def _max_timestamp(current: str | None, candidate: str | None) -> str | None:
            if not candidate:
                return current
            if current is None or candidate > current:
                return candidate
            return current

        latest_market = None
        latest_intelligence = None
        latest_financials = None
        latest_dark_pool = None
        latest_options = None
        sessions_with_data = 0
        latest_financials_provider = None
        latest_dark_pool_provider = None
        latest_options_provider = None
        latest_intelligence_query = None
        latest_market_symbol = None
        for session in self.sessions.values():
            has_data = False
            if session.market_snapshots:
                market_points = [item for item in session.market_snapshots if item.get("timestamp") or item.get("observed_at")]
                if market_points:
                    latest_market_item = max(market_points, key=lambda item: item.get("timestamp") or item.get("observed_at") or "")
                    latest_market = _max_timestamp(latest_market, latest_market_item.get("timestamp") or latest_market_item.get("observed_at"))
                    if latest_market_item.get("symbol"):
                        latest_market_symbol = latest_market_item.get("symbol")
                has_data = True
            if session.intelligence_runs:
                runs = [item for item in session.intelligence_runs if item.get("timestamp")]
                if runs:
                    latest_intelligence_item = max(runs, key=lambda item: item.get("timestamp") or "")
                    latest_intelligence = _max_timestamp(latest_intelligence, latest_intelligence_item.get("timestamp"))
                    latest_intelligence_query = latest_intelligence_item.get("query") or latest_intelligence_query
                has_data = True
            if session.financials_runs:
                runs = [item for item in session.financials_runs if item.get("timestamp")]
                if runs:
                    latest_financials_item = max(runs, key=lambda item: item.get("timestamp") or "")
                    latest_financials = _max_timestamp(latest_financials, latest_financials_item.get("timestamp"))
                    latest_financials_provider = latest_financials_item.get("provider") or latest_financials_provider
                has_data = True
            if session.dark_pool_runs:
                runs = [item for item in session.dark_pool_runs if item.get("timestamp")]
                if runs:
                    latest_dark_pool_item = max(runs, key=lambda item: item.get("timestamp") or "")
                    latest_dark_pool = _max_timestamp(latest_dark_pool, latest_dark_pool_item.get("timestamp"))
                    latest_dark_pool_provider = latest_dark_pool_item.get("provider") or latest_dark_pool_provider
                has_data = True
            if session.options_runs:
                runs = [item for item in session.options_runs if item.get("timestamp")]
                if runs:
                    latest_options_item = max(runs, key=lambda item: item.get("timestamp") or "")
                    latest_options = _max_timestamp(latest_options, latest_options_item.get("timestamp"))
                    latest_options_provider = latest_options_item.get("provider") or latest_options_provider
                has_data = True
            if has_data:
                sessions_with_data += 1
        recent_data_failures = [
            item
            for item in self.agent_activity_log
            if item["status"] == "error"
            and item["operation"] in {"search_intelligence", "fetch_financials_data", "fetch_dark_pool_data", "fetch_options_data"}
        ][-10:]
        failure_counts: dict[str, int] = {}
        for item in recent_data_failures:
            operation = item["operation"]
            failure_counts[operation] = failure_counts.get(operation, 0) + 1
        age_map = {
            "market": self._hours_since_iso(latest_market),
            "intelligence": self._hours_since_iso(latest_intelligence),
            "financials": self._hours_since_iso(latest_financials),
            "dark_pool": self._hours_since_iso(latest_dark_pool),
            "options": self._hours_since_iso(latest_options),
        }
        stale_sources = [name for name, hours in age_map.items() if hours is not None and hours > 24]
        critical_stale_sources = [name for name, hours in age_map.items() if hours is not None and hours > 72]
        known_hours = [hours for hours in age_map.values() if hours is not None]
        status = "healthy"
        note = "Recent data activity looks healthy."
        if (
            not latest_market
            and not latest_intelligence
            and not latest_financials
            and not latest_dark_pool
            and not latest_options
        ):
            status = "fragile"
            note = "No recent market, intelligence, financials, dark-pool, or options data has been recorded."
        elif critical_stale_sources:
            status = "fragile"
            note = f"Critical data sources are stale: {', '.join(critical_stale_sources)}."
        elif len(recent_data_failures) >= 3:
            status = "warning"
            note = "Recent data fetches show repeated failures. Check providers, keys, network, or local file paths."
        elif stale_sources:
            status = "warning"
            note = f"Some data sources are stale: {', '.join(stale_sources)}."
        elif recent_data_failures:
            status = "warning"
            note = "There are recent data fetch failures, but the data layer is still partially active."
        return {
            "status": status,
            "note": note,
            "sessions_with_data": sessions_with_data,
            "latest_market_timestamp": latest_market,
            "latest_market_symbol": latest_market_symbol,
            "latest_intelligence_timestamp": latest_intelligence,
            "latest_intelligence_query": latest_intelligence_query,
            "latest_financials_timestamp": latest_financials,
            "latest_financials_provider": latest_financials_provider,
            "latest_dark_pool_timestamp": latest_dark_pool,
            "latest_dark_pool_provider": latest_dark_pool_provider,
            "latest_options_timestamp": latest_options,
            "latest_options_provider": latest_options_provider,
            "recent_failure_count": len(recent_data_failures),
            "recent_failure_operations": [item["operation"] for item in recent_data_failures],
            "recent_failure_counts": failure_counts,
            "stale_sources": stale_sources,
            "critical_stale_sources": critical_stale_sources,
            "source_age_hours": age_map,
            "max_stale_hours": max(known_hours) if known_hours else None,
        }

    def _runtime_health_summary(self) -> dict:
        latest_strategy_session = None
        latest_strategy_log = None
        latest_strategy_ts = ""
        latest_terminal_run = None
        latest_terminal_ts = ""
        latest_programmer_run = None
        latest_programmer_ts = ""
        for session in self.sessions.values():
            for item in session.strategy_training_log:
                ts = item.get("timestamp") or ""
                if ts >= latest_strategy_ts:
                    latest_strategy_ts = ts
                    latest_strategy_log = item
                    latest_strategy_session = session
            for run in session.programmer_runs:
                ts = run.get("timestamp") or ""
                if ts >= latest_programmer_ts:
                    latest_programmer_ts = ts
                    latest_programmer_run = run
            for run in session.terminal_integration_runs:
                test = run.get("terminal_test") or {}
                ts = test.get("timestamp") or run.get("timestamp") or ""
                if ts >= latest_terminal_ts:
                    latest_terminal_ts = ts
                    latest_terminal_run = run

        research_status = "warning"
        research_note = "当前还没有足够的策略研究记录。"
        repair_status = "warning"
        repair_note = "当前还没有足够的修复记录。"
        terminal_status = "warning"
        terminal_note = "当前还没有终端测试记录。"
        llm_status = "warning"
        llm_note = "当前还没有 LLM 运行摘要。"
        research_age_hours = self._hours_since_iso(latest_strategy_ts)
        repair_age_hours = self._hours_since_iso(latest_programmer_ts or latest_strategy_ts)
        terminal_age_hours = self._hours_since_iso(latest_terminal_ts)

        if latest_strategy_log:
            research = latest_strategy_log.get("research_summary") or {}
            research_reliability = research.get("research_reliability_summary") or {}
            gate = (research.get("final_release_gate_summary") or {}).get("gate_status") or "unknown"
            robustness = (research.get("robustness_summary") or {}).get("grade") or "unknown"
            coverage_blocked = bool((research.get("final_release_gate_summary") or {}).get("coverage_gate_blocked"))
            if research_reliability.get("status") == "healthy":
                research_status = "healthy"
                research_note = str(research_reliability.get("note") or "最新策略研究可靠性较强。")
            elif research_reliability.get("status") == "fragile" or gate == "blocked" or robustness == "fragile" or coverage_blocked:
                research_status = "fragile"
                research_note = str(research_reliability.get("note") or "最新策略研究仍被发布门阻塞，或稳健性/回测覆盖不足。")
            else:
                research_note = str(research_reliability.get("note") or "最新策略研究已完成，但仍需继续观察 gate 与稳健性。")

            if research_age_hours is not None and research_age_hours > 72:
                research_status = "fragile"
                research_note = f"最近策略研究结果已过期（{research_age_hours}h），不适合继续长期依赖。"
            elif research_age_hours is not None and research_age_hours > 24 and research_status == "healthy":
                research_status = "warning"
                research_note = f"最近策略研究结果已有一定时效性压力（{research_age_hours}h）。"

            if latest_strategy_session:
                recent_logs = latest_strategy_session.strategy_training_log[-5:]
                route_names = [((item.get("repair_route_summary") or [{}])[0] or {}).get("lane", "无") for item in recent_logs]
                priorities = [((item.get("repair_route_summary") or [{}])[0] or {}).get("priority", "unknown") for item in recent_logs]
                if len(recent_logs) >= 3 and len(set(route_names)) == 1 and len(set(priorities)) <= 2:
                    repair_status = "healthy"
                    repair_note = "最近几轮主修复路线稳定，修复目标正在收敛。"
                elif len(set(route_names)) >= 3:
                    repair_status = "fragile"
                    repair_note = "最近几轮主修复路线变化较大，修复问题仍在发散。"
                else:
                    repair_note = "修复路线已有一定稳定性，但仍未完全收敛。"

            if latest_programmer_run:
                chain = latest_programmer_run.get("repair_chain_summary") or {}
                chain_status = chain.get("chain_status")
                if chain_status == "healthy":
                    repair_status = "healthy"
                elif chain_status == "fragile":
                    repair_status = "fragile"
                elif chain_status == "warning" and repair_status == "healthy":
                    repair_status = "warning"
                if chain.get("note"):
                    repair_note = str(chain.get("note"))

            if repair_age_hours is not None and repair_age_hours > 72:
                repair_status = "fragile"
                repair_note = f"最近修复链结果已过期（{repair_age_hours}h），需要重新验证当前修复基线。"
            elif repair_age_hours is not None and repair_age_hours > 24 and repair_status == "healthy":
                repair_status = "warning"
                repair_note = f"最近修复链结果已有一定时效性压力（{repair_age_hours}h）。"

        latest_terminal_runtime = {}
        latest_terminal_reliability = {}
        if latest_terminal_run:
            latest_terminal_runtime = latest_terminal_run.get("terminal_runtime_summary") or self._build_terminal_runtime_summary(latest_terminal_run)
            latest_terminal_reliability = latest_terminal_run.get("terminal_reliability_summary") or self._build_terminal_reliability_summary({**latest_terminal_run, "terminal_runtime_summary": latest_terminal_runtime})
            terminal_status = latest_terminal_reliability.get("status") or latest_terminal_runtime.get("status") or "warning"
            terminal_note = latest_terminal_reliability.get("note") or latest_terminal_runtime.get("note") or "终端接入已有测试记录，但仍建议继续检查返回结构和 endpoint 完整性。"
            if terminal_age_hours is not None and terminal_age_hours > 72:
                terminal_status = "fragile"
                terminal_note = f"最近终端测试结果已过期（{terminal_age_hours}h），应重新执行 readiness 和 smoke test。"
            elif terminal_age_hours is not None and terminal_age_hours > 24 and terminal_status == "healthy":
                terminal_status = "warning"
                terminal_note = f"最近终端测试结果已有一定时效性压力（{terminal_age_hours}h）。"

        data_health = self._data_health_snapshot()
        data_status = str(data_health.get("status") or "warning")
        data_note = str(data_health.get("note") or "当前还没有数据健康摘要。")

        llm_description = self.llm_runtime.describe()
        llm_usage = self.llm_runtime.usage_snapshot()
        llm_provider_runtime = self.llm_runtime.provider_runtime_summary()
        llm_aggregate = llm_usage.get("aggregate") or {}
        llm_tasks = llm_description.get("tasks", {})
        fallback_tasks = [name for name, item in llm_tasks.items() if item.get("generation_mode") == "template_fallback"]
        live_tasks = [name for name, item in llm_tasks.items() if item.get("generation_mode") == "live_llm"]
        api_request_count = int(llm_aggregate.get("api_request_count", 0))
        total_tokens = int(llm_aggregate.get("total_tokens", 0))
        fallback_ratio = float(llm_aggregate.get("fallback_ratio", 0.0))
        recent_fallback_ratio = float(llm_aggregate.get("recent_fallback_ratio", 0.0))
        cache_hit_ratio = float(llm_aggregate.get("cache_hit_ratio", 0.0))
        if not llm_description.get("enabled"):
            llm_status = "fragile"
            llm_note = "LLM runtime 当前被禁用，关键研究与总结任务将退回 fallback。"
        elif live_tasks and not fallback_tasks:
            llm_status = "healthy"
            llm_note = f"关键 LLM 任务当前都走 live provider。累计请求 {api_request_count} 次，总 token {total_tokens}。"
        elif live_tasks and fallback_tasks:
            llm_status = "warning"
            llm_note = f"当前 LLM 任务处于 live 与 fallback 混合状态，建议补齐缺失凭据。累计请求 {api_request_count} 次，总 token {total_tokens}。"
        else:
            llm_status = "fragile"
            llm_note = f"当前所有 LLM 任务都在 fallback 模式下运行。累计请求 {api_request_count} 次，总 token {total_tokens}。"

        if llm_status == "healthy" and recent_fallback_ratio > 0.25:
            llm_status = "warning"
            llm_note = f"最近 LLM 调用 fallback 占比偏高（{recent_fallback_ratio:.0%}），建议检查 provider 稳定性。累计请求 {api_request_count} 次，总 token {total_tokens}。"
        elif llm_status == "warning" and recent_fallback_ratio > 0.6:
            llm_status = "fragile"
            llm_note = f"最近 LLM 调用大多落到 fallback（{recent_fallback_ratio:.0%}），研究与总结质量存在明显风险。累计请求 {api_request_count} 次，总 token {total_tokens}。"

        research_actions: list[str] = []
        if gate == "blocked" if latest_strategy_log else False:
            research_actions.append("回到策略页，先处理当前 winner 的 gate blockers 和 next_iteration_focus。")
        if research_age_hours is not None and research_age_hours > 24:
            research_actions.append("重新运行至少一轮策略研究，刷新当前 research baseline。")
        if latest_strategy_log and ((latest_strategy_log.get("research_summary") or {}).get("final_release_gate_summary") or {}).get("coverage_gate_blocked"):
            research_actions.append("优先扩充本地历史样本或更换更完整的数据包，再重新评估候选。")
        if not research_actions:
            research_actions.append("维持当前研究基线，继续观察新的训练输入变化。")

        repair_actions: list[str] = []
        latest_repair_chain = (latest_programmer_run or {}).get("repair_chain_summary") or {}
        if latest_repair_chain.get("actions"):
            repair_actions.extend(list(latest_repair_chain.get("actions") or []))
        if repair_status == "fragile":
            repair_actions.append("回到策略页查看 Programmer Agent 的 rollback、promotion 和 stability 结论。")
        if repair_age_hours is not None and repair_age_hours > 24:
            repair_actions.append("重新验证最近一次代码修复基线，避免沿用过期 patch。")
        if not repair_actions:
            repair_actions.append("当前修复链可继续沿既有主路线推进。")
        repair_actions = list(dict.fromkeys(repair_actions))

        terminal_actions: list[str] = []
        if latest_terminal_reliability.get("next_action") or latest_terminal_runtime.get("next_action"):
            terminal_actions.append(str(latest_terminal_reliability.get("next_action") or latest_terminal_runtime.get("next_action")))
        if terminal_age_hours is not None and terminal_age_hours > 24:
            terminal_actions.append("重新执行 terminal readiness 和 smoke test，刷新终端契约置信度。")
        if not terminal_actions:
            terminal_actions.append("当前终端接入状态稳定，可继续进入更强联通验证。")

        data_actions: list[str] = []
        if data_health.get("critical_stale_sources"):
            data_actions.append(f"优先刷新过期最严重的数据源: {', '.join(data_health.get('critical_stale_sources') or [])}。")
        elif data_health.get("stale_sources"):
            data_actions.append(f"重新拉取这些 stale 数据源: {', '.join(data_health.get('stale_sources') or [])}。")
        if data_health.get("recent_failure_count", 0) > 0:
            data_actions.append("检查 provider、key、本地路径和网络状态，再重试数据抓取。")
        if not data_actions:
            data_actions.append("当前数据层新鲜度可接受，继续观察增量更新。")

        llm_actions: list[str] = []
        if recent_fallback_ratio > 0.25:
            llm_actions.append("检查当前 live provider 凭据和可用性，降低近期 fallback 压力。")
        if fallback_tasks:
            llm_actions.append(f"优先补齐这些任务的 live provider: {', '.join(fallback_tasks[:5])}。")
        if not llm_actions:
            llm_actions.append("当前 LLM 运行质量可接受，继续监控 fallback 与缓存效率。")

        research_revalidation_required = bool(
            latest_strategy_log
            and (
                gate == "blocked"
                or bool((latest_strategy_log.get("research_summary") or {}).get("final_release_gate_summary", {}).get("coverage_gate_blocked"))
                or research_status != "healthy"
                or (research_age_hours is not None and research_age_hours > 24)
            )
        )
        repair_revalidation_required = bool(
            latest_strategy_log
            and (
                repair_status != "healthy"
                or (repair_age_hours is not None and repair_age_hours > 24)
            )
        )
        terminal_revalidation_required = bool(
            latest_terminal_run
            and (
                terminal_status != "healthy"
                or (terminal_age_hours is not None and terminal_age_hours > 24)
            )
        )
        data_revalidation_required = bool(
            data_status != "healthy"
            or data_health.get("stale_sources")
            or data_health.get("critical_stale_sources")
            or data_health.get("recent_failure_count", 0) > 0
        )
        llm_revalidation_required = bool(
            llm_status != "healthy"
            or recent_fallback_ratio > 0.25
            or bool(fallback_tasks)
        )

        statuses = [research_status, repair_status, terminal_status, data_status, llm_status]
        overall_status = "healthy"
        overall_note = "研究、修复、终端、数据和模型层整体健康。"
        if "fragile" in statuses:
            overall_status = "fragile"
            overall_note = "至少有一条关键链路处于脆弱状态，当前不适合长时间无人值守使用。"
        elif "warning" in statuses:
            overall_status = "warning"
            overall_note = "整体可用，但仍有链路需要继续观察和修复。"

        overall_revalidation_required = any([
            research_revalidation_required,
            repair_revalidation_required,
            terminal_revalidation_required,
            data_revalidation_required,
            llm_revalidation_required,
        ])

        recommended_actions = list(dict.fromkeys([
            research_actions[0],
            repair_actions[0],
            terminal_actions[0],
            data_actions[0],
            llm_actions[0],
        ]))

        runtime_blockers: list[str] = []
        if research_status == "fragile":
            runtime_blockers.append("research")
        if repair_status == "fragile":
            runtime_blockers.append("repair")
        if terminal_status == "fragile":
            runtime_blockers.append("terminal")
        if data_status == "fragile":
            runtime_blockers.append("data")
        if llm_status == "fragile":
            runtime_blockers.append("llm")

        if overall_status == "healthy" and not overall_revalidation_required:
            recovery_status = "healthy"
            next_mode = "continue"
            recovery_note = "Current runtime posture is healthy enough to continue normal use without forced revalidation."
        elif runtime_blockers:
            recovery_status = "fragile"
            next_mode = "pause_and_recover"
            recovery_note = "At least one critical chain is too weak for sustained use; pause reliance on stale outputs and recover the blocked modules first."
        elif overall_revalidation_required:
            recovery_status = "warning"
            next_mode = "revalidate"
            recovery_note = "The platform is still usable, but one or more chains should be revalidated before continued reliance."
        else:
            recovery_status = "warning"
            next_mode = "stabilize"
            recovery_note = "The platform is usable, but should be stabilized further before long unattended operation."

        runtime_recovery_summary = {
            "status": recovery_status,
            "next_mode": next_mode,
            "revalidation_required": overall_revalidation_required,
            "blockers": runtime_blockers,
            "note": recovery_note,
            "actions": recommended_actions,
        }

        return {
            "status": overall_status,
            "note": overall_note,
            "recommended_actions": recommended_actions,
            "revalidation_required": overall_revalidation_required,
            "runtime_recovery_summary": runtime_recovery_summary,
            "research": {
                "status": research_status,
                "note": research_note,
                "timestamp": latest_strategy_ts or None,
                "age_hours": research_age_hours,
                "revalidation_required": research_revalidation_required,
                "recovery_actions": research_actions,
            },
            "repair": {
                "status": repair_status,
                "note": repair_note,
                "timestamp": latest_programmer_ts or latest_strategy_ts or None,
                "age_hours": repair_age_hours,
                "revalidation_required": repair_revalidation_required,
                "recovery_actions": repair_actions,
                "repair_chain_summary": (latest_programmer_run or {}).get("repair_chain_summary") or {},
            },
            "terminal": {
                "status": terminal_status,
                "note": terminal_note,
                "timestamp": latest_terminal_ts or None,
                "age_hours": terminal_age_hours,
                "next_action": latest_terminal_reliability.get("next_action") or latest_terminal_runtime.get("next_action"),
                "primary_route": latest_terminal_reliability.get("primary_route") or latest_terminal_runtime.get("primary_route"),
                "revalidation_required": terminal_revalidation_required or bool(latest_terminal_reliability.get("revalidation_required")),
                "recovery_actions": terminal_actions,
                "terminal_reliability_summary": latest_terminal_reliability,
            },
            "data": {
                "status": data_status,
                "note": data_note,
                "revalidation_required": data_revalidation_required,
                "recovery_actions": data_actions,
            },
            "llm": {
                "status": llm_status,
                "note": llm_note,
                "live_task_count": len(live_tasks),
                "fallback_task_count": len(fallback_tasks),
                "fallback_tasks": fallback_tasks[:8],
                "api_request_count": api_request_count,
                "total_tokens": total_tokens,
                "live_request_count": int(llm_aggregate.get("live_request_count", 0)),
                "fallback_request_count": int(llm_aggregate.get("fallback_request_count", 0)),
                "fallback_ratio": fallback_ratio,
                "recent_fallback_ratio": recent_fallback_ratio,
                "cache_hit_ratio": cache_hit_ratio,
                "recent_call_count": int(llm_aggregate.get("recent_call_count", 0)),
                "rotated_credential_count": int(llm_aggregate.get("rotated_credential_count", 0)),
                "active_api_key_envs": llm_aggregate.get("active_api_key_envs", []),
                "provider_runtime": llm_provider_runtime,
                "revalidation_required": llm_revalidation_required,
                "recovery_actions": llm_actions,
            },
        }

    def _get_intelligence_cache(self, key: tuple) -> dict | None:
        if not self.settings.performance_enabled:
            return None
        cached = self._intelligence_cache.get(key)
        if cached is not None:
            self._performance_counters["intelligence_hits"] += 1
            return dict(cached)
        self._performance_counters["intelligence_misses"] += 1
        return None

    def _set_intelligence_cache(self, key: tuple, value: dict) -> None:
        if not self.settings.performance_enabled:
            return
        self._intelligence_cache[key] = dict(value)
        while len(self._intelligence_cache) > self.settings.performance_market_data_cache_size:
            first_key = next(iter(self._intelligence_cache))
            self._intelligence_cache.pop(first_key, None)

    def _module_status(self, name: str, status: str, detail: str, recommendation: str) -> dict:
        return {"name": name, "status": status, "detail": detail, "recommendation": recommendation}

    def _extract_intelligence_factors(self, documents: list[dict], report: dict | None = None) -> dict:
        report = report or {}
        positive = sum(1 for item in documents if float(item.get("sentiment_hint", 0.0)) > 0.15)
        negative = sum(1 for item in documents if float(item.get("sentiment_hint", 0.0)) < -0.15)
        unique_sources = sorted({item.get("source", "unknown") for item in documents})
        source_diversity = round(min(1.0, len(unique_sources) / max(1, len(documents))), 4)
        sentiment_balance = round((positive - negative) / max(1, len(documents)), 4)
        contradiction_score = round(min(1.0, (1 if positive else 0) + (1 if negative else 0)) * 0.5, 4)
        credibility_score = round(
            min(
                1.0,
                (
                    0.35 * source_diversity
                    + 0.35 * min(1.0, len(documents) / 6)
                    + 0.3 * (1.0 - contradiction_score)
                ),
            ),
            4,
        )
        return {
            "document_count": len(documents),
            "source_count": len(unique_sources),
            "source_diversity_score": source_diversity,
            "sentiment_balance": sentiment_balance,
            "credibility_score": credibility_score,
            "contradiction_score": contradiction_score,
            "dominant_tone": report.get("dominant_tone", "mixed"),
        }

    def _extract_financial_factors(self, payload: dict) -> dict:
        normalized = payload.get("normalized", {})
        statements = normalized.get("statements", [])
        first = statements[0] if statements else {}
        revenue = first.get("revenue")
        net_income = first.get("net_income")
        overall_weight = float(normalized.get("overall_weight", 0.0) or 0.0)
        quality_score = round(min(1.0, overall_weight * 0.5 + (0.25 if revenue is not None else 0.0) + (0.25 if net_income is not None else 0.0)), 4)
        deterioration_score = round(max(0.0, 1.0 - quality_score), 4)
        return {
            "quality_score": quality_score,
            "deterioration_score": deterioration_score,
            "statement_count": len(statements),
            "overall_weight": overall_weight,
            "report_period": normalized.get("report_period") or payload.get("fiscal_period") or payload.get("fiscalDateEnding"),
        }

    def _extract_dark_pool_factors(self, payload: dict) -> dict:
        normalized = payload.get("normalized", {})
        records = normalized.get("records", [])
        total_shares = sum(float(item.get("shares", item.get("volume", 0)) or 0) for item in records[:10])
        overall_weight = float(normalized.get("overall_weight", 0.0) or 0.0)
        accumulation_score = round(min(1.0, overall_weight * 0.5 + min(0.5, total_shares / 1000000)), 4)
        return {
            "accumulation_score": accumulation_score,
            "record_count": len(records),
            "total_recent_shares": round(total_shares, 2),
            "overall_weight": overall_weight,
        }

    def _extract_options_factors(self, payload: dict) -> dict:
        normalized = payload.get("normalized", {})
        contracts = normalized.get("contracts", [])
        total_open_interest = sum(float(item.get("open_interest", 0) or 0) for item in contracts[:20])
        avg_iv = 0.0
        iv_values = [float(item.get("implied_volatility", item.get("iv", 0)) or 0) for item in contracts[:20] if item.get("implied_volatility", item.get("iv")) is not None]
        if iv_values:
            avg_iv = sum(iv_values) / len(iv_values)
        overall_weight = float(normalized.get("overall_weight", 0.0) or 0.0)
        options_pressure_score = round(min(1.0, overall_weight * 0.4 + min(0.3, total_open_interest / 100000) + min(0.3, avg_iv / 2)), 4)
        return {
            "options_pressure_score": options_pressure_score,
            "contract_count": len(contracts),
            "total_open_interest": round(total_open_interest, 2),
            "average_iv": round(avg_iv, 4),
            "overall_weight": overall_weight,
        }

    def _record_information_event(
        self,
        session: WorkflowSession,
        *,
        anchor: str,
        category: str,
        summary: str,
        factors: dict,
        provider: str | None,
        related_refs: list[str] | None,
    ) -> None:
        session.information_events.append(
            {
                "event_id": f"info-{len(session.information_events) + 1}",
                "timestamp": self._now_iso(),
                "anchor": anchor,
                "category": category,
                "summary": summary,
                "provider": provider,
                "factors": factors,
                "related_refs": related_refs or [],
            }
        )

    def _build_input_manifest(
        self,
        *,
        selected_universe: list[str],
        dataset_plan: dict,
        features: dict,
        objective_metric: str,
    ) -> dict:
        meta = features.get("meta") or {}
        lineage = features.get("source_lineage") or {}
        data_quality = features.get("data_quality") or {}
        return {
            "objective_metric": objective_metric,
            "selected_universe": selected_universe,
            "selected_universe_size": len(selected_universe),
            "dataset_protocol": dataset_plan.get("protocol"),
            "walk_forward_windows": len(dataset_plan.get("walk_forward_windows") or []),
            "data_bundle_id": meta.get("data_bundle_id"),
            "feature_snapshot_version": meta.get("snapshot_hash"),
            "available_sections": data_quality.get("available_sections") or [],
            "provider_coverage": data_quality.get("provider_coverage") or [],
            "data_quality": data_quality,
            "source_lineage": lineage,
        }

    def _register_data_bundle(self, session: WorkflowSession, manifest: dict) -> None:
        bundle_id = manifest.get("data_bundle_id")
        if not bundle_id:
            return
        existing = next((item for item in session.data_bundles if item.get("data_bundle_id") == bundle_id), None)
        if existing is not None:
            existing["last_used_at"] = self._now_iso()
            existing["usage_count"] = int(existing.get("usage_count", 1)) + 1
            return
        session.data_bundles.append(
            {
                "data_bundle_id": bundle_id,
                "feature_snapshot_version": manifest.get("feature_snapshot_version"),
                "dataset_protocol": manifest.get("dataset_protocol"),
                "selected_universe": manifest.get("selected_universe") or [],
                "selected_universe_size": manifest.get("selected_universe_size"),
                "available_sections": manifest.get("available_sections") or [],
                "provider_coverage": manifest.get("provider_coverage") or [],
                "quality_grade": manifest.get("data_quality", {}).get("quality_grade"),
                "training_readiness": manifest.get("data_quality", {}).get("training_readiness", {}).get("status"),
                "source_lineage": manifest.get("source_lineage") or {},
                "created_at": self._now_iso(),
                "last_used_at": self._now_iso(),
                "usage_count": 1,
            }
        )
        self._append_history_event(
            session,
            "data_bundle_registered",
            "训练输入数据包已登记。",
            {
                "data_bundle_id": bundle_id,
                "dataset_protocol": manifest.get("dataset_protocol"),
                "quality_grade": manifest.get("data_quality", {}).get("quality_grade"),
                "training_readiness": manifest.get("data_quality", {}).get("training_readiness", {}).get("status"),
            },
        )

    def _apply_feedback_evolution(self, session: WorkflowSession, feedback: str, strategy_type: str) -> None:
        if not feedback:
            return
        lowered = feedback.lower()
        delta_noise = 0.0
        delta_intervention = 0.0
        delta_confidence = 0.0
        delta_discipline = 0.0
        if any(token in lowered for token in ("reduce", "avoid", "worry", "worried", "risk", "downsize", "lower")):
            delta_noise += 0.03
            delta_intervention += 0.02
            delta_confidence -= 0.04
        if any(token in lowered for token in ("more aggressive", "increase", "add", "higher risk", "press")):
            delta_confidence += 0.05
            delta_discipline -= 0.02
        event = ProfileEvolutionEvent(
            timestamp=datetime.now(timezone.utc),
            source_type="strategy_feedback",
            source_ref=strategy_type,
            delta_noise_sensitivity=delta_noise,
            delta_intervention_risk=delta_intervention,
            delta_confidence=delta_confidence,
            delta_discipline=delta_discipline,
            note=feedback,
        )
        session.strategy_feedback_log.append(
            {
                "timestamp": self._now_iso(),
                "strategy_type": strategy_type,
                "feedback": feedback,
            }
        )
        self._append_history_event(
            session,
            "strategy_feedback_recorded",
            "用户提供了新的策略意见。",
            {
                "strategy_type": strategy_type,
                "feedback": feedback,
            },
        )
        self._merge_profile_evolution(session, event)

    def _apply_trade_evolution(self, session: WorkflowSession, trade: TradeExecutionRecord) -> None:
        delta_panic = 0.0
        delta_avg_down = 0.0
        delta_noise = 0.0
        delta_intervention = 0.0
        delta_discipline = 0.0
        delta_confidence = 0.0
        if trade.user_initiated:
            delta_intervention += 0.03
        if trade.realized_pnl_pct <= -8.0:
            delta_panic += 0.04
            delta_confidence -= 0.05
        elif trade.realized_pnl_pct >= 8.0:
            delta_confidence += 0.03
            delta_discipline += 0.01
        if trade.side.lower() == "buy" and trade.realized_pnl_pct < 0:
            delta_avg_down += 0.03
        event = ProfileEvolutionEvent(
            timestamp=trade.timestamp,
            source_type="trade_record",
            source_ref=trade.symbol,
            delta_panic_sell=delta_panic,
            delta_averaging_down=delta_avg_down,
            delta_noise_sensitivity=delta_noise,
            delta_intervention_risk=delta_intervention,
            delta_discipline=delta_discipline,
            delta_confidence=delta_confidence,
            note=trade.note,
        )
        self._merge_profile_evolution(session, event)

    def _merge_profile_evolution(self, session: WorkflowSession, event: ProfileEvolutionEvent) -> None:
        if session.profile_evolution is None:
            base = dict(session.behavioral_report or {})
            session.profile_evolution = {
                "base_profile": base,
                "effective_profile": dict(base),
                "confidence_level": 0.5,
                "events": [],
            }
        effective = session.profile_evolution["effective_profile"]
        mapping = {
            "panic_sell_tendency": event.delta_panic_sell,
            "bottom_fishing_tendency": event.delta_averaging_down,
            "noise_sensitivity": event.delta_noise_sensitivity,
            "overtrading_tendency": event.delta_intervention_risk,
            "hold_strength": event.delta_discipline,
        }
        for key, delta in mapping.items():
            effective[key] = round(max(0.0, min(1.0, float(effective.get(key, 0.5)) + delta)), 4)
        confidence = float(session.profile_evolution.get("confidence_level", 0.5)) + event.delta_confidence
        session.profile_evolution["confidence_level"] = round(max(0.0, min(1.0, confidence)), 4)
        session.profile_evolution["events"].append(
            {
                "timestamp": event.timestamp.isoformat(),
                "source_type": event.source_type,
                "source_ref": event.source_ref,
                "delta_panic_sell": round(event.delta_panic_sell, 4),
                "delta_averaging_down": round(event.delta_averaging_down, 4),
                "delta_noise_sensitivity": round(event.delta_noise_sensitivity, 4),
                "delta_intervention_risk": round(event.delta_intervention_risk, 4),
                "delta_discipline": round(event.delta_discipline, 4),
                "delta_confidence": round(event.delta_confidence, 4),
                "note": event.note,
            }
        )

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _append_history_event(self, session: WorkflowSession, event_type: str, summary: str, payload: dict | None = None) -> None:
        session.history_events.append(
            {
                "event_id": f"hist-{len(session.history_events) + 1}",
                "event_type": event_type,
                "summary": summary,
                "payload": payload or {},
                "timestamp": self._now_iso(),
                "phase": session.phase,
            }
        )
        self._persist_session(session)

    def _archive_report(
        self,
        session: WorkflowSession,
        report_type: str,
        title: str,
        body: dict,
        related_refs: list[str] | None = None,
    ) -> None:
        session.report_history.append(
            {
                "report_id": f"report-{len(session.report_history) + 1}",
                "report_type": report_type,
                "title": title,
                "created_at": self._now_iso(),
                "phase": session.phase,
                "related_refs": related_refs or [],
                "body": body,
            }
        )
        self._persist_session(session)


    def _debug_preview(self, payload):
        if payload is None:
            return None
        if isinstance(payload, dict):
            items = list(payload.items())
            preview = {str(key): self._debug_preview(value) for key, value in items[:10]}
            if len(items) > 10:
                preview["__more_keys__"] = len(items) - 10
            return preview
        if isinstance(payload, list):
            preview = [self._debug_preview(value) for value in payload[:5]]
            if len(payload) > 5:
                preview.append({"__more_items__": len(payload) - 5})
            return preview
        if isinstance(payload, tuple):
            return self._debug_preview(list(payload))
        if isinstance(payload, str):
            return payload if len(payload) <= 240 else f"{payload[:240]}..."
        if isinstance(payload, (int, float, bool)):
            return payload
        return str(payload)

    def _record_agent_activity(
        self,
        agent: str,
        status: str,
        operation: str,
        detail: str,
        session_id: UUID | None = None,
        request_payload=None,
        response_payload=None,
    ) -> None:
        self.agent_activity_log.append(
            {
                "timestamp": self._now_iso(),
                "agent": agent,
                "status": status,
                "operation": operation,
                "detail": detail,
                "session_id": str(session_id) if session_id else None,
                "request_payload": self._debug_preview(request_payload),
                "response_payload": self._debug_preview(response_payload),
            }
        )
        self.agent_activity_log = self.agent_activity_log[-200:]

    def _agent_diagnostics(self) -> list[dict]:
        known_agents = [
            "scenario_director",
            "noise_agent",
            "behavioral_profiler",
            "intelligence_agent",
            "strategy_evolver",
            "portfolio_manager",
            "intent_aligner",
            "risk_guardian",
            "user_monitor",
            "strategy_monitor",
            "market_asset_monitor",
            "strategy_integrity_checker",
            "strategy_stress_checker",
            "programmer_agent",
            "data_source_expansion_agent",
            "trading_terminal_integration_agent",
            "workflow_service",
        ]
        diagnostics: list[dict] = []
        for agent in known_agents:
            logs = [item for item in self.agent_activity_log if item["agent"] == agent]
            error_logs = [item for item in logs if item["status"] == "error"]
            last = logs[-1] if logs else None
            status = "idle"
            recommendation = "No action required."
            if error_logs:
                status = "error"
                recommendation = "Inspect the latest error log and the upstream payload for this agent."
            elif logs:
                status = "ok"
            diagnostics.append(
                {
                    "agent": agent,
                    "status": status,
                    "activity_count": len(logs),
                    "error_count": len(error_logs),
                    "last_seen": last["timestamp"] if last else None,
                    "last_operation": last["operation"] if last else None,
                    "last_detail": last["detail"] if last else "No activity recorded yet.",
                    "recommendation": recommendation if logs else "No activity yet. Run the related workflow stage to validate this agent.",
                }
            )
        return diagnostics

    def _library_diagnostics(self) -> list[dict]:
        libraries = [
            {
                "name": "fastapi",
                "import_name": "fastapi",
                "required": True,
                "detail": "API framework.",
            },
            {
                "name": "uvicorn",
                "import_name": "uvicorn",
                "required": True,
                "detail": "ASGI runtime.",
            },
            {
                "name": "psycopg",
                "import_name": "psycopg",
                "required": False,
                "detail": "PostgreSQL and TimescaleDB adapter.",
            },
            {
                "name": "redis",
                "import_name": "redis",
                "required": False,
                "detail": "Redis client for runtime bus and cache.",
            },
            {
                "name": "qdrant_client",
                "import_name": "qdrant_client",
                "required": False,
                "detail": "Vector store client.",
            },
            {
                "name": "langchain",
                "import_name": "langchain",
                "required": False,
                "detail": "Workflow orchestration and chain abstraction.",
            },
            {
                "name": "prometheus_fastapi_instrumentator",
                "import_name": "prometheus_fastapi_instrumentator",
                "required": self.settings.prometheus_enabled,
                "detail": "Prometheus metrics instrumentation.",
            },
            {
                "name": "sentry_sdk",
                "import_name": "sentry_sdk",
                "required": self.settings.sentry_enabled,
                "detail": "Error monitoring SDK.",
            },
            {
                "name": "langfuse",
                "import_name": "langfuse",
                "required": self.settings.langfuse_enabled,
                "detail": "LLM tracing and analytics SDK.",
            },
        ]
        diagnostics: list[dict] = []
        for item in libraries:
            present = importlib.util.find_spec(item["import_name"]) is not None
            required = bool(item["required"])
            if present:
                status = "ok"
                recommendation = "No action required."
            elif required:
                status = "error"
                recommendation = f"Install or enable {item['name']} before using the related feature."
            else:
                status = "warning"
                recommendation = f"{item['name']} is optional in the current mode."
            diagnostics.append(
                {
                    "name": item["name"],
                    "status": status,
                    "detail": f"{item['detail']} {'Installed.' if present else 'Not installed.'}",
                    "required": required,
                    "recommendation": recommendation,
                }
            )
        return diagnostics

    def _target_holding_days(self, preferences: dict | None) -> int:
        if not preferences:
            return 10
        timeframe = preferences.get("preferred_timeframe")
        if timeframe == "minute":
            return 2
        if timeframe == "weekly":
            return 30
        return 10

    def _recommend_trading_preferences(self, report: BehavioralReport) -> dict[str, str]:
        if report.intervention_risk > 0.75 or report.noise_susceptibility > 0.7:
            return {
                "trading_frequency": "low",
                "preferred_timeframe": "weekly" if report.panic_sell_score > 0.55 else "daily",
                "note": "你的测试结果显示你容易在高噪音和高波动环境中频繁干预，建议先用低频节奏和更慢周期过滤噪音。",
            }
        if report.discipline_score > 0.68 and report.noise_susceptibility < 0.45:
            return {
                "trading_frequency": "medium",
                "preferred_timeframe": "daily",
                "note": "你的持有纪律较稳定，且不容易被噪音带偏，日线为主的中频节奏更匹配当前画像。",
            }
        if report.discipline_score > 0.75 and report.panic_sell_score < 0.3 and report.intervention_risk < 0.45:
            return {
                "trading_frequency": "high",
                "preferred_timeframe": "minute",
                "note": "你的测试结果显示执行纪律和波动承受都较好，可以尝试更高频的分钟线节奏，但仍需控制成本和盯盘强度。",
            }
        return {
            "trading_frequency": "medium",
            "preferred_timeframe": "daily",
            "note": "当前画像更适合先从日线主导的中频节奏开始，再根据后续行为逐步调整。",
        }

    def _recommend_strategy_type(self, report: BehavioralReport, trading_recommendation: dict[str, str]) -> dict[str, str]:
        if report.discipline_score > 0.72 and report.noise_susceptibility < 0.45:
            return {
                "strategy_type": "trend_following_aligned",
                "note": "你的执行纪律较强且不容易被噪音带偏，更适合趋势跟随型策略。",
            }
        if report.averaging_down_score < 0.28 and report.panic_sell_score < 0.32 and trading_recommendation["preferred_timeframe"] == "minute":
            return {
                "strategy_type": "mean_reversion_aligned",
                "note": "你的恐慌和摊平倾向较低，且偏好更快节奏，可以尝试更严格约束下的均值回归型策略。",
            }
        return {
            "strategy_type": "rule_based_aligned",
            "note": "当前更适合先用规则约束更强的稳健型策略，避免让性格弱点直接放大。",
        }

    def _detect_preference_conflict(self, session: WorkflowSession) -> dict[str, str] | None:
        return self.intent_aligner.detect_preference_conflict(
            session.behavioral_report,
            session.trading_preferences,
        )

    def _run_integrity_check(self, strategy: dict, candidate: dict) -> dict:
        return self.strategy_integrity_checker.evaluate(strategy, candidate)

    def _run_stress_overfit_check(
        self,
        strategy: dict,
        candidate: dict,
        behavior: dict,
        compatibility: float,
    ) -> dict:
        return self.strategy_stress_checker.evaluate(strategy, candidate, behavior, compatibility)
