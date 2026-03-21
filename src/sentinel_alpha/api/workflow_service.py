from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from sentinel_alpha.agents.behavioral_profiler import BehavioralProfilerAgent
from sentinel_alpha.agents.intelligence_agent import IntelligenceAgent
from sentinel_alpha.agents.strategy_evolver import StrategyEvolverAgent
from dataclasses import asdict

from sentinel_alpha.config import get_settings
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


class WorkflowService:
    def __init__(self) -> None:
        self.sessions: dict[UUID, WorkflowSession] = {}
        self.settings = get_settings()
        self.generator = ScenarioGenerator(seed=11)
        self.profiler = BehavioralProfilerAgent()
        self.intelligence = IntelligenceAgent()
        self.evolver = StrategyEvolverAgent()
        self.strategy_registry = StrategyRegistry()
        self.llm_runtime = LLMRuntime(self.settings)

    def create_session(self, user_name: str, starting_capital: float) -> WorkflowSession:
        session = WorkflowSession(session_id=uuid4(), user_name=user_name, starting_capital=starting_capital)
        self.sessions[session.session_id] = session
        return session

    def get_session(self, session_id: UUID) -> WorkflowSession:
        return self.sessions[session_id]

    def generate_scenarios(self, session_id: UUID) -> WorkflowSession:
        session = self.get_session(session_id)
        packages = [
            self.generator.generate("uptrend", cohort="pressure"),
            self.generator.generate("gap", cohort="pressure"),
            self.generator.generate("oscillation", cohort="pressure"),
            self.generator.generate("drawdown", cohort="pressure"),
            self.generator.generate("fake_reversal", cohort="pressure"),
            self.generator.generate("downtrend", cohort="pressure"),
        ]
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
        return session

    def append_behavior_event(self, session_id: UUID, event: BehaviorEvent) -> WorkflowSession:
        session = self.get_session(session_id)
        session.behavior_events.append(event)
        return session

    def complete_simulation(self, session_id: UUID, symbol: str) -> WorkflowSession:
        session = self.get_session(session_id)
        user = UserProfile(
            user_id=str(session.session_id),
            preferred_assets=[symbol],
            capital_base=session.starting_capital,
            target_holding_days=10,
            self_reported_risk_tolerance=0.5,
            confidence_level=0.5,
        )
        report = self.profiler.profile(session.behavior_events)
        market = MarketSnapshot(symbol=symbol, expected_return_pct=16.0, realized_volatility_pct=35.0, trend_score=0.45, event_risk_score=0.35, liquidity_score=0.9)
        policy = self.evolver.derive_risk_policy(user, report)
        brief = self.evolver.synthesize(user, market, report, policy)
        trading_recommendation = self._recommend_trading_preferences(report)
        strategy_recommendation = self._recommend_strategy_type(report, trading_recommendation)
        session.behavioral_report = {
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
        }
        session.profile_evolution = {
            "base_profile": dict(session.behavioral_report),
            "effective_profile": dict(session.behavioral_report),
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
        return session

    def set_trading_preferences(
        self,
        session_id: UUID,
        trading_frequency: str,
        preferred_timeframe: str,
        rationale: str | None,
    ) -> WorkflowSession:
        session = self.get_session(session_id)
        descriptions = {
            "low": "低频交易意味着更少操作次数，更强调等待和耐心，不适合频繁追逐盘中波动。",
            "medium": "中频交易强调节奏和过滤，允许阶段性出手，但仍需避免噪音驱动。",
            "high": "高频交易意味着更高盯盘要求和更高执行密度，用户需要接受更频繁的信号与波动。",
        }
        timeframe_notes = {
            "minute": "分钟线机会更多，但噪音和成本也更高，适合高频或盘中型用户。",
            "daily": "日线更适合大多数个人交易者，能过滤大量盘中噪音。",
            "weekly": "周线更强调趋势和耐心，适合低频和波段型用户。",
        }
        session.trading_preferences = {
            "trading_frequency": trading_frequency,
            "preferred_timeframe": preferred_timeframe,
            "frequency_description": descriptions[trading_frequency],
            "timeframe_description": timeframe_notes[preferred_timeframe],
            "rationale": rationale or "",
        }
        conflict = self._detect_preference_conflict(session)
        if conflict:
            session.trading_preferences["conflict_warning"] = conflict["warning"]
            session.trading_preferences["conflict_level"] = conflict["level"]
        session.phase = "preferences_ready"
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
        return session

    def iterate_strategy(
        self,
        session_id: UUID,
        feedback: str | None,
        strategy_type: str = "rule_based_aligned",
        auto_iterations: int = 1,
        iteration_mode: str = "guided",
    ) -> WorkflowSession:
        session = self.get_session(session_id)
        if session.trade_universe is None or session.behavioral_report is None:
            raise ValueError("Trade universe and behavioral report must exist before strategy iteration.")
        expanded = session.trade_universe["expanded"]
        if feedback:
            self._apply_feedback_evolution(session, feedback, strategy_type)
        last_error: str | None = None
        for loop_index in range(max(1, auto_iterations)):
            iteration_no = 1 if session.strategy_package is None else session.strategy_package["iteration_no"] + 1
            try:
                compatibility = max(0.35, min(0.95, 0.78 - 0.04 * max(0, iteration_no - 1)))
                market = MarketSnapshot(
                    symbol=expanded[0],
                    expected_return_pct=16.0,
                    realized_volatility_pct=28.0,
                    trend_score=0.58 if strategy_type == "trend_following_aligned" else 0.18 if strategy_type == "mean_reversion_aligned" else 0.42,
                    event_risk_score=0.32,
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
                candidate = self.evolver.build_strategy_candidate(
                    user=user,
                    market=market,
                    report=behavior,
                    policy=policy,
                    selected_universe=expanded,
                    feedback=feedback,
                    strategy_type=strategy_type,
                )
                llm_strategy_artifact = self.llm_runtime.generate_strategy_code(
                    strategy_type=strategy_type,
                    selected_universe=expanded,
                    candidate_payload=asdict(candidate),
                    feedback=feedback,
                )
                session.strategy_package = {
                    "iteration_no": iteration_no,
                    "strategy_type": strategy_type,
                    "selected_universe": expanded,
                    "feedback": feedback,
                    "iteration_mode": iteration_mode,
                    "auto_iterations_requested": auto_iterations,
                    "expected_return_range": [0.10, 0.22],
                    "max_potential_loss": -0.12,
                    "expected_drawdown": -0.08,
                    "position_limit": 0.18,
                    "behavioral_compatibility": compatibility,
                    "candidate": asdict(candidate),
                    "llm_profile": llm_strategy_artifact["profile"],
                    "generated_strategy_code": llm_strategy_artifact["code"],
                    "llm_generation_summary": llm_strategy_artifact["summary"],
                    "agent_model_map": self.llm_runtime.agent_matrix(),
                    "task_model_map": self.llm_runtime.describe().get("tasks", {}),
                    "trading_preferences": session.trading_preferences,
                }
                session.strategy_checks = self._run_strategy_checks(session)
                failed_checks = [check for check in session.strategy_checks if check["status"] == "fail"]
                session.strategy_training_log.append(
                    {
                        "timestamp": self._now_iso(),
                        "iteration_no": iteration_no,
                        "loop_index": loop_index + 1,
                        "strategy_type": strategy_type,
                        "iteration_mode": iteration_mode,
                        "status": "rework_required" if failed_checks else "checked",
                        "feedback": feedback or "",
                        "llm_summary": llm_strategy_artifact["summary"],
                        "failed_checks": [check["check_type"] for check in failed_checks],
                    }
                )
                if not failed_checks and iteration_mode != "free":
                    break
            except Exception as exc:
                last_error = str(exc)
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
                raise ValueError(f"Strategy iteration failed: {last_error}") from exc
        if last_error:
            raise ValueError(last_error)
        session.phase = (
            "strategy_rework_required"
            if any(check["status"] == "fail" for check in session.strategy_checks)
            else "strategy_checked"
        )
        return session

    def approve_strategy(self, session_id: UUID) -> WorkflowSession:
        session = self.get_session(session_id)
        if not session.strategy_checks or any(check["status"] == "fail" for check in session.strategy_checks):
            session.phase = "strategy_rework_required"
            raise ValueError("Strategy checks failed. Re-iterate the strategy before approval.")
        session.phase = "strategy_approved"
        return session

    def set_deployment(self, session_id: UUID, execution_mode: str) -> WorkflowSession:
        session = self.get_session(session_id)
        session.execution_mode = execution_mode
        session.phase = "autonomous_active" if execution_mode == "autonomous" else "advice_only_active"
        return session

    def append_market_snapshot(self, session_id: UUID, snapshot: MarketDataPoint) -> WorkflowSession:
        session = self.get_session(session_id)
        session.market_snapshots.append(asdict(snapshot))
        return session

    def append_trade_record(self, session_id: UUID, trade: TradeExecutionRecord) -> WorkflowSession:
        session = self.get_session(session_id)
        session.trade_records.append(asdict(trade))
        self._apply_trade_evolution(session, trade)
        return session

    def search_intelligence(self, session_id: UUID, query: str, max_documents: int | None = None) -> WorkflowSession:
        session = self.get_session(session_id)
        session.intelligence_documents = [asdict(item) for item in self.intelligence.search(query, max_documents)]
        return session

    def append_information_events(self, session_id: UUID, events: list[dict]) -> WorkflowSession:
        session = self.get_session(session_id)
        session.information_events.extend(events)
        return session

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
        behavior = session.behavioral_report or {}
        strategy = session.strategy_package or {}
        return [
            {
                "monitor_type": "user",
                "severity": "warning" if behavior.get("noise_sensitivity", 0) > 0.6 else "info",
                "title": "User Monitor",
                "detail": "Noise sensitivity remains elevated." if behavior.get("noise_sensitivity", 0) > 0.6 else "User behavior is within the profiled baseline.",
            },
            {
                "monitor_type": "strategy",
                "severity": "warning" if strategy.get("behavioral_compatibility", 1) < 0.7 else "info",
                "title": "Strategy Monitor",
                "detail": "Behavioral compatibility is drifting down." if strategy.get("behavioral_compatibility", 1) < 0.7 else "Strategy remains aligned with the current profile.",
            },
            {
                "monitor_type": "market",
                "severity": "info",
                "title": "Market and Asset Monitor",
                "detail": f"Watching universe: {', '.join(strategy.get('selected_universe', session.trade_universe.get('expanded', []) if session.trade_universe else [])) or 'none'}.",
            },
        ]

    def system_health(self) -> dict:
        static_dir = Path(__file__).resolve().parents[1] / "webapp" / "static"
        frontend_pages = [
            "index.html",
            "pages/session.html",
            "pages/simulation.html",
            "pages/report.html",
            "pages/preferences.html",
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
            self._module_status("strategy_registry", "ok", f"Registered strategies: {', '.join(self.strategy_registry.list_types())}.", "Register new strategy implementations here before exposing them to workflow."),
            self._module_status("monitoring_agents", "ok", "User, strategy, and market monitors are enabled in workflow.", "No action required."),
            self._module_status("strategy_check_agents", "ok", "Integrity checker and stress/overfit checker are enforced before approval.", "No action required."),
            self._module_status(
                "web_module",
                "ok" if not missing_pages else "error",
                "Canonical web pages are present." if not missing_pages else f"Missing pages: {', '.join(missing_pages)}.",
                "No action required." if not missing_pages else "Restore missing pages under src/sentinel_alpha/webapp/static/pages before shipping.",
            ),
            self._module_status(
                "storage_layer",
                "ok",
                "In-memory workflow service is active. External persistence is optional in the current mode.",
                "Switch to persistent_app only when you need PostgreSQL, TimescaleDB, Redis, and Qdrant persistence.",
            ),
        ]
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
        }

    def llm_config(self) -> dict:
        return self.llm_runtime.describe()

    def _run_strategy_checks(self, session: WorkflowSession) -> list[dict]:
        behavior = (session.profile_evolution or {}).get("effective_profile") or session.behavioral_report or {}
        strategy = session.strategy_package or {}
        candidate = strategy.get("candidate") or {}
        compatibility = strategy.get("behavioral_compatibility", 0.0)
        return [
            self._run_integrity_check(strategy, candidate),
            self._run_stress_overfit_check(strategy, candidate, behavior, compatibility),
        ]

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

    def _module_status(self, name: str, status: str, detail: str, recommendation: str) -> dict:
        return {"name": name, "status": status, "detail": detail, "recommendation": recommendation}
        return self.profiler.profile(session.behavior_events)

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
        if not session.behavioral_report or not session.trading_preferences:
            return None
        recommended_frequency = session.behavioral_report.get("recommended_trading_frequency")
        recommended_timeframe = session.behavioral_report.get("recommended_timeframe")
        selected_frequency = session.trading_preferences.get("trading_frequency")
        selected_timeframe = session.trading_preferences.get("preferred_timeframe")
        if selected_frequency == recommended_frequency and selected_timeframe == recommended_timeframe:
            return None

        severe = (
            recommended_frequency == "low" and selected_frequency == "high"
        ) or (
            recommended_timeframe == "weekly" and selected_timeframe == "minute"
        )
        warning = (
            f"你的测试结果更推荐 {recommended_frequency} 频次和 {recommended_timeframe} 周期，"
            f"但你当前选择了 {selected_frequency} 频次和 {selected_timeframe} 周期。"
            " 这意味着你未来更可能在噪音、盯盘强度或执行纪律上出现偏离。"
        )
        return {"level": "high" if severe else "warning", "warning": warning}

    def _run_integrity_check(self, strategy: dict, candidate: dict) -> dict:
        flags: list[str] = []
        required_fix_actions: list[str] = []
        metrics: dict[str, float | int | str] = {}

        parameters = candidate.get("parameters") or {}
        metadata = candidate.get("metadata") or {}
        signals = candidate.get("signals") or []
        rationale_tokens = " ".join(
            " ".join(signal.get("rationale") or [])
            for signal in signals
            if isinstance(signal, dict)
        ).lower()
        suspicious_terms = [
            "future",
            "tomorrow",
            "next candle",
            "post-close result",
            "guaranteed",
            "known earnings result",
            "after the event",
        ]
        detected_terms = [term for term in suspicious_terms if term in rationale_tokens]
        if detected_terms:
            flags.append(f"future_leakage_terms={','.join(detected_terms)}")
            required_fix_actions.append("Remove any rationale or feature that references unavailable future information.")

        parameter_keys = {str(key).lower() for key in parameters}
        metadata_keys = {str(key).lower() for key in metadata}
        suspicious_keys = [
            key
            for key in parameter_keys | metadata_keys
            if any(token in key for token in ("future", "leak", "cheat", "oracle", "perfect", "winrate"))
        ]
        if suspicious_keys:
            flags.append(f"suspicious_keys={','.join(sorted(suspicious_keys))}")
            required_fix_actions.append("Rename or remove parameters that imply future leakage or engineered win logic.")

        max_conviction = max(
            (float(signal.get("conviction", 0.0)) for signal in signals if isinstance(signal, dict)),
            default=0.0,
        )
        metrics["max_signal_conviction"] = round(max_conviction, 4)
        if max_conviction >= 0.97:
            flags.append("win_coding_conviction_spike")
            required_fix_actions.append("Reduce impossible conviction levels and justify confidence with observable features only.")

        iteration_no = int(strategy.get("iteration_no", 1))
        metrics["iteration_no"] = iteration_no
        metrics["strategy_type"] = str(candidate.get("strategy_type", strategy.get("strategy_type", "unknown")))
        if iteration_no > 5:
            flags.append("excessive_manual_iteration_count")
            required_fix_actions.append("Review the optimization loop for silent curve fitting across too many manual revisions.")

        universe_size = int((metadata.get("selected_universe_size") or len(strategy.get("selected_universe") or [])) or 0)
        metrics["selected_universe_size"] = universe_size
        if universe_size <= 1:
            flags.append("single_asset_candidate")
            required_fix_actions.append("Expand the universe or attach a benchmark basket before approving the strategy.")

        score = 1.0
        score -= 0.45 if detected_terms else 0.0
        score -= 0.25 if suspicious_keys else 0.0
        score -= 0.25 if max_conviction >= 0.97 else 0.0
        score -= 0.10 if iteration_no > 5 else 0.0
        score -= 0.10 if universe_size <= 1 else 0.0
        score = max(0.0, round(score, 2))

        status = "pass"
        if detected_terms or suspicious_keys or max_conviction >= 0.97:
            status = "fail"
        elif flags:
            status = "warning"

        summary = "No obvious future leakage or engineered win logic was found."
        detail = "Integrity checks passed on rationale, parameter naming, conviction profile, and iteration path."
        if status == "warning":
            summary = "Integrity review found weak spots that need manual attention before release."
            detail = "The candidate is not outright invalid, but its optimization path or concentration setup increases audit risk."
        if status == "fail":
            summary = "Integrity review rejected this strategy version."
            detail = "The candidate exposes future-information leakage, cheating-like markers, or impossible confidence assumptions."

        return {
            "check_type": "integrity",
            "status": status,
            "title": "Strategy Integrity Checker",
            "score": score,
            "summary": summary,
            "detail": detail,
            "flags": flags,
            "required_fix_actions": required_fix_actions,
            "metrics": metrics,
        }

    def _run_stress_overfit_check(
        self,
        strategy: dict,
        candidate: dict,
        behavior: dict,
        compatibility: float,
    ) -> dict:
        flags: list[str] = []
        required_fix_actions: list[str] = []
        metrics: dict[str, float | int | str] = {
            "behavioral_compatibility": round(compatibility, 4),
        }

        parameters = candidate.get("parameters") or {}
        metadata = candidate.get("metadata") or {}
        strategy_type = candidate.get("strategy_type") or strategy.get("strategy_type", "unknown")
        universe_size = int((metadata.get("selected_universe_size") or len(strategy.get("selected_universe") or [])) or 0)
        parameter_count = len(parameters)
        max_position_pct = float(
            parameters.get("max_position_pct", strategy.get("position_limit", 0.0)) or 0.0
        )
        noise_sensitivity = float(behavior.get("noise_sensitivity", 0.0) or 0.0)
        overtrading_tendency = float(behavior.get("overtrading_tendency", 0.0) or 0.0)
        bottom_fishing_tendency = float(behavior.get("bottom_fishing_tendency", 0.0) or 0.0)

        metrics["selected_universe_size"] = universe_size
        metrics["parameter_count"] = parameter_count
        metrics["max_position_pct"] = round(max_position_pct, 4)
        metrics["noise_sensitivity"] = round(noise_sensitivity, 4)
        metrics["overtrading_tendency"] = round(overtrading_tendency, 4)
        metrics["bottom_fishing_tendency"] = round(bottom_fishing_tendency, 4)
        metrics["strategy_type"] = strategy_type

        if universe_size < 5:
            flags.append("too_small_trade_universe")
            required_fix_actions.append("Expand the trade universe to at least 5 instruments or explicitly justify the narrow scope.")
        if compatibility < 0.55:
            flags.append("low_behavioral_compatibility")
            required_fix_actions.append("Re-iterate with stricter behavior alignment so the user is less likely to override execution.")
        if parameter_count > max(3, universe_size):
            flags.append("parameter_density_too_high")
            required_fix_actions.append("Reduce free parameters or broaden the train universe before the next iteration.")
        if noise_sensitivity > 0.75 and max_position_pct > 0.18:
            flags.append("position_limit_too_high_for_user_profile")
            required_fix_actions.append("Lower position limits for this user profile before re-running stress validation.")
        if overtrading_tendency > 0.85:
            flags.append("manual_intervention_risk_high")
            required_fix_actions.append("Increase confirmation thresholds or cooldown periods to reduce intervention churn.")
        if strategy_type == "mean_reversion_aligned" and bottom_fishing_tendency > 0.45:
            flags.append("mean_reversion_conflicts_with_bottom_fishing_profile")
            required_fix_actions.append("Switch strategy family or add multi-timeframe confirmation against premature bottom fishing.")
        if strategy_type == "trend_following_aligned" and compatibility < 0.65:
            flags.append("trend_following_not_stable_under_current_profile")
            required_fix_actions.append("Tighten the trend filter or select a less behavior-sensitive strategy family.")

        score = 1.0
        score -= 0.30 if universe_size < 5 else 0.0
        score -= 0.35 if compatibility < 0.55 else 0.10 if compatibility < 0.70 else 0.0
        score -= 0.15 if parameter_count > max(3, universe_size) else 0.0
        score -= 0.15 if noise_sensitivity > 0.75 and max_position_pct > 0.18 else 0.0
        score -= 0.10 if overtrading_tendency > 0.85 else 0.0
        score -= 0.20 if strategy_type == "mean_reversion_aligned" and bottom_fishing_tendency > 0.45 else 0.0
        score -= 0.10 if strategy_type == "trend_following_aligned" and compatibility < 0.65 else 0.0
        score = max(0.0, round(score, 2))

        status = "pass"
        if any(
            flag in flags
            for flag in (
                "too_small_trade_universe",
                "low_behavioral_compatibility",
                "parameter_density_too_high",
                "mean_reversion_conflicts_with_bottom_fishing_profile",
            )
        ):
            status = "fail"
        elif flags:
            status = "warning"

        summary = "Stress and overfit review is within tolerance."
        detail = "The candidate remains reasonably stable across behavior alignment, universe breadth, and parameter density checks."
        if status == "warning":
            summary = "Stress review found fragility that should be addressed before approval."
            detail = "The candidate is usable for research, but user behavior or concentration risk could break it in live trading."
        if status == "fail":
            summary = "Stress and overfit review rejected this strategy version."
            detail = "The candidate is too fragile under current user behavior, universe breadth, or parameter concentration assumptions."

        return {
            "check_type": "stress_overfit",
            "status": status,
            "title": "Strategy Stress and Overfit Checker",
            "score": score,
            "summary": summary,
            "detail": detail,
            "flags": flags,
            "required_fix_actions": required_fix_actions,
            "metrics": metrics,
        }
