from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
from uuid import UUID, uuid4

from sentinel_alpha.agents.behavioral_profiler import BehavioralProfilerAgent
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
from sentinel_alpha.agents.user_monitor_agent import UserMonitorAgent
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
    history_events: list[dict] = field(default_factory=list)
    report_history: list[dict] = field(default_factory=list)
    intelligence_runs: list[dict] = field(default_factory=list)
    programmer_runs: list[dict] = field(default_factory=list)


class WorkflowService:
    def __init__(self) -> None:
        self.sessions: dict[UUID, WorkflowSession] = {}
        self.settings = get_settings()
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
        self.evolver = StrategyEvolverAgent()
        self.strategy_registry = StrategyRegistry()
        self.llm_runtime = LLMRuntime(self.settings)
        self.agent_activity_log: list[dict] = []

    def create_session(self, user_name: str, starting_capital: float) -> WorkflowSession:
        session = WorkflowSession(session_id=uuid4(), user_name=user_name, starting_capital=starting_capital)
        self.sessions[session.session_id] = session
        self._record_agent_activity("workflow_service", "ok", "create_session", "Created workflow session.", session.session_id)
        self._append_history_event(
            session,
            "session_created",
            "会话已创建。",
            {"starting_capital": starting_capital, "user_name": user_name},
        )
        return session

    def get_session(self, session_id: UUID) -> WorkflowSession:
        return self.sessions[session_id]

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
        self._record_agent_activity("scenario_director", "ok", "generate_scenarios", f"Generated {len(session.scenarios)} scenarios.", session.session_id)
        self._append_history_event(
            session,
            "scenarios_generated",
            "模拟测试场景已生成。",
            {"scenario_count": len(session.scenarios)},
        )
        return session

    def append_behavior_event(self, session_id: UUID, event: BehaviorEvent) -> WorkflowSession:
        session = self.get_session(session_id)
        session.behavior_events.append(event)
        self._record_agent_activity("behavioral_profiler", "ok", "append_behavior_event", f"Recorded action={event.action} for {event.scenario_id}.", session.session_id)
        self._append_history_event(
            session,
            "behavior_event_recorded",
            "记录了一次模拟交易行为。",
            {
                "scenario_id": event.scenario_id,
                "action": event.action,
                "drawdown_pct": event.price_drawdown_pct,
            },
        )
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
        self._record_agent_activity("behavioral_profiler", "ok", "complete_simulation", "Generated behavioral report.", session.session_id)
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
        self._archive_report(
            session,
            report_type="behavioral_profiler",
            title="Behavioral Profiler Report",
            body=session.behavioral_report or {},
            related_refs=[symbol],
        )
        self._append_history_event(
            session,
            "simulation_completed",
            "模拟测试完成并生成心理侧写报告。",
            {"symbol": symbol},
        )
        return session

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
        self._record_agent_activity("intent_aligner", "ok", "set_trading_preferences", "Updated trading preferences and checked conflicts.", session.session_id)
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
        self._record_agent_activity("intelligence_agent", "ok", "set_trade_universe", f"Prepared universe size={len(expanded)}.", session.session_id)
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
    ) -> WorkflowSession:
        session = self.get_session(session_id)
        if session.trade_universe is None or session.behavioral_report is None:
            raise ValueError("Trade universe and behavioral report must exist before strategy iteration.")
        expanded = session.trade_universe["expanded"]
        targets = self._normalize_objective_targets(objective_metric, objective_targets or {})
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
                self._record_agent_activity("strategy_evolver", "ok", "derive_risk_policy", "Derived risk policy for iteration.", session.session_id)
                baseline_candidate = self.evolver.build_strategy_candidate(
                    user=user,
                    market=market,
                    report=behavior,
                    policy=policy,
                    selected_universe=expanded,
                    feedback=None,
                    strategy_type="rule_based_aligned",
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
                )
                candidate_payload = asdict(candidate)
                candidate_payload["version"] = self._strategy_version_label(1, iteration_no, 0, strategy_type)
                self._record_agent_activity("strategy_evolver", "ok", "build_strategy_candidate", f"Built candidate {candidate_payload['version']}.", session.session_id)
                previous_failure = self._previous_failure_summary(session)
                analysis = self._analyze_strategy_iteration(
                    session=session,
                    strategy_type=strategy_type,
                    objective_metric=objective_metric,
                    objective_targets=targets,
                    current_candidate=candidate_payload,
                    previous_failure=previous_failure,
                    feedback=feedback,
                )
                plans = self._build_upgrade_plans(strategy_type, analysis, behavior, targets)
                variants = []
                for variant_index, plan in enumerate(plans, start=1):
                    variant_candidate = self._build_variant_candidate(candidate, plan, variant_index)
                    artifact = self.llm_runtime.generate_strategy_code(
                        strategy_type=strategy_type,
                        selected_universe=expanded,
                        candidate_payload=asdict(variant_candidate),
                        feedback=f"{feedback or ''} | plan={plan['plan_name']}".strip(),
                    )
                    evaluation = self._evaluate_strategy_candidate(asdict(variant_candidate), objective_metric, targets, variant_index)
                    variants.append(
                        {
                            "variant_id": plan["variant_id"],
                            "plan": plan,
                            "candidate": asdict(variant_candidate),
                            "generated_code": artifact["code"],
                            "llm_profile": artifact["profile"],
                            "llm_generation_summary": artifact["summary"],
                            "evaluation": evaluation,
                        }
                    )
                baseline_evaluation = self._evaluate_strategy_candidate(asdict(baseline_candidate), objective_metric, targets, 0)
                winner = self._compare_variant_results(baseline_evaluation, variants)
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
                    "expected_return_range": [0.10, 0.22],
                    "max_potential_loss": -0.12,
                    "expected_drawdown": -0.08,
                    "position_limit": 0.18,
                    "behavioral_compatibility": compatibility,
                    "candidate": candidate_payload,
                    "baseline_candidate": baseline_payload,
                    "baseline_evaluation": baseline_evaluation,
                    "analysis": analysis,
                    "previous_failure_summary": previous_failure,
                    "upgrade_plans": plans,
                    "candidate_variants": variants,
                    "recommended_variant": winner,
                    "llm_profile": variants[0]["llm_profile"] if variants else {},
                    "generated_strategy_code": variants[0]["generated_code"] if variants else "",
                    "llm_generation_summary": variants[0]["llm_generation_summary"] if variants else "",
                    "agent_model_map": self.llm_runtime.agent_matrix(),
                    "task_model_map": self.llm_runtime.describe().get("tasks", {}),
                    "trading_preferences": session.trading_preferences,
                }
                session.strategy_checks = self._run_strategy_checks(session)
                failed_checks = [check for check in session.strategy_checks if check["status"] == "fail"]
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
                        "status": "rework_required" if failed_checks else "checked",
                        "feedback": feedback or "",
                        "analysis_summary": analysis["summary"],
                        "recommended_variant": winner["variant_id"],
                        "failed_checks": [check["check_type"] for check in failed_checks],
                    }
                )
                self._archive_report(
                    session,
                    report_type="strategy_iteration",
                    title=f"Strategy Iteration {session.strategy_package['version_label']}",
                    body={
                        "strategy_package": session.strategy_package,
                        "strategy_checks": session.strategy_checks,
                        "training_log_entry": session.strategy_training_log[-1],
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
                    },
                )
                if not failed_checks and iteration_mode != "free":
                    break
            except Exception as exc:
                last_error = str(exc)
                self._record_agent_activity("strategy_evolver", "error", "iterate_strategy", last_error, session.session_id)
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
    ) -> dict:
        avg_conviction = sum(float(item.get("conviction", 0.0)) for item in candidate.get("signals", [])) / max(1, len(candidate.get("signals", [])))
        max_position = float(candidate.get("parameters", {}).get("max_position_pct", 0.12) or 0.12)
        hard_stop = float(candidate.get("parameters", {}).get("hard_stop_loss_pct", 0.06) or 0.06)
        expected_return_pct = round(8 + avg_conviction * 18 + variant_index * 0.7, 2)
        win_rate_pct = round(48 + avg_conviction * 22 - variant_index * 0.4, 2)
        drawdown_pct = round(max(3.0, hard_stop * 100 * 1.6 + max_position * 12), 2)
        max_loss_pct = round(max(2.0, hard_stop * 100), 2)
        objective_value = {
            "return": expected_return_pct,
            "win_rate": win_rate_pct,
            "drawdown": -drawdown_pct,
            "max_loss": -max_loss_pct,
        }[objective_metric]
        score = self._objective_score(objective_metric, targets, expected_return_pct, win_rate_pct, drawdown_pct, max_loss_pct)
        return {
            "expected_return_pct": expected_return_pct,
            "win_rate_pct": win_rate_pct,
            "drawdown_pct": drawdown_pct,
            "max_loss_pct": max_loss_pct,
            "objective_metric": objective_metric,
            "objective_value": objective_value,
            "objective_score": score,
        }

    def _objective_score(
        self,
        objective_metric: str,
        targets: dict[str, float],
        expected_return_pct: float,
        win_rate_pct: float,
        drawdown_pct: float,
        max_loss_pct: float,
    ) -> float:
        score = 0.0
        score += expected_return_pct / max(1.0, targets["target_return_pct"]) * (0.5 if objective_metric == "return" else 0.2)
        score += win_rate_pct / max(1.0, targets["target_win_rate_pct"]) * (0.5 if objective_metric == "win_rate" else 0.2)
        score += max(0.0, 1 - drawdown_pct / max(1.0, targets["target_drawdown_pct"])) * (0.5 if objective_metric == "drawdown" else 0.3)
        score += max(0.0, 1 - max_loss_pct / max(1.0, targets["target_max_loss_pct"])) * (0.5 if objective_metric == "max_loss" else 0.3)
        return round(score, 4)

    def _compare_variant_results(self, baseline_evaluation: dict, variants: list[dict]) -> dict:
        best = {
            "variant_id": "baseline",
            "objective_score": baseline_evaluation["objective_score"],
            "evaluation": baseline_evaluation,
            "reason": "Baseline remains the strongest current reference.",
        }
        for variant in variants:
            if variant["evaluation"]["objective_score"] > best["objective_score"]:
                best = {
                    "variant_id": variant["variant_id"],
                    "objective_score": variant["evaluation"]["objective_score"],
                    "evaluation": variant["evaluation"],
                    "reason": f"{variant['plan']['plan_name']} beats baseline on the configured objective.",
                }
        return best

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
        documents = [asdict(item) for item in self.intelligence.search(query, max_documents)]
        report = self.llm_runtime.summarize_intelligence(query, documents)
        self._record_agent_activity("intelligence_agent", "ok", "search_intelligence", f"Collected {len(documents)} documents for query={query}.", session.session_id)
        session.intelligence_documents = documents
        session.intelligence_runs.append(
            {
                "run_id": f"intel-{len(session.intelligence_runs) + 1}",
                "query": query,
                "generated_at": self._now_iso(),
                "document_count": len(documents),
                "documents": documents,
                "report": report,
            }
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
        return session

    def append_information_events(self, session_id: UUID, events: list[dict]) -> WorkflowSession:
        session = self.get_session(session_id)
        normalized_events = self.noise_agent.normalize_events(events)
        session.information_events.extend(normalized_events)
        self._record_agent_activity("noise_agent", "ok", "append_information_events", f"Stored {len(normalized_events)} information events.", session.session_id)
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
        result = self.programmer.execute(
            instruction=instruction,
            target_files=target_files,
            context=context,
            commit_changes=commit_changes,
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
            },
        )
        self._record_agent_activity(
            "programmer_agent",
            "ok" if result.get("status") == "ok" else "error",
            "execute_programmer_task",
            result.get("error") or f"Changed files: {', '.join(result.get('changed_files', [])) or 'none'}",
            session.session_id,
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
            self._module_status(
                "programmer_agent",
                "ok" if self.settings.programmer_agent_enabled else "warning",
                "Programmer Agent is attached." if self.settings.programmer_agent_enabled else "Programmer Agent is present but disabled by config.",
                "Enable programmer_agent.enabled and install aider to allow controlled code modification." if not self.settings.programmer_agent_enabled else "No action required.",
            ),
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
        candidate = strategy.get("candidate") or {}
        compatibility = strategy.get("behavioral_compatibility", 0.0)
        return [
            self.strategy_integrity_checker.evaluate(strategy, candidate),
            self.strategy_stress_checker.evaluate(strategy, candidate, behavior, compatibility),
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

    def _record_agent_activity(
        self,
        agent: str,
        status: str,
        operation: str,
        detail: str,
        session_id: UUID | None = None,
    ) -> None:
        self.agent_activity_log.append(
            {
                "timestamp": self._now_iso(),
                "agent": agent,
                "status": status,
                "operation": operation,
                "detail": detail,
                "session_id": str(session_id) if session_id else None,
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
