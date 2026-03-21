from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import subprocess
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
                self._record_agent_activity("strategy_evolver", "ok", "derive_risk_policy", "Derived risk policy for iteration.", session.session_id)
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
                self._record_agent_activity("strategy_evolver", "ok", "build_strategy_candidate", f"Built candidate {candidate_payload['version']}.", session.session_id)
                previous_failure = self._previous_failure_summary(session)
                dataset_plan = self._build_strategy_dataset_plan(iteration_no)
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

    def _build_strategy_dataset_plan(self, iteration_no: int) -> dict:
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

        real_backtest = self._evaluate_candidate_with_local_history(candidate, objective_metric, targets, dataset_plan)
        if real_backtest is not None:
            if self.settings.performance_enabled:
                self._candidate_eval_cache[cache_key] = dict(real_backtest)
                while len(self._candidate_eval_cache) > self.settings.performance_dataset_plan_cache_size * 8:
                    first_key = next(iter(self._candidate_eval_cache))
                    self._candidate_eval_cache.pop(first_key, None)
            return real_backtest

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
        split_metrics = self._build_split_metrics(
            expected_return_pct,
            win_rate_pct,
            drawdown_pct,
            max_loss_pct,
            variant_index,
            dataset_plan,
            objective_metric,
            targets,
        )
        score = split_metrics["test"]["objective_score"]
        stability_score = split_metrics["stability"]["score"]
        evaluation = {
            "expected_return_pct": expected_return_pct,
            "win_rate_pct": win_rate_pct,
            "drawdown_pct": drawdown_pct,
            "max_loss_pct": max_loss_pct,
            "objective_metric": objective_metric,
            "objective_value": objective_value,
            "objective_score": score,
            "dataset_evaluation": split_metrics,
            "validation_objective_score": split_metrics["validation"]["objective_score"],
            "test_objective_score": split_metrics["test"]["objective_score"],
            "walk_forward_score": split_metrics["stability"]["walk_forward_score"],
            "stability_score": stability_score,
            "evaluation_source": "heuristic_surrogate",
            "coverage_summary": {
                "symbol_count": len(list(dict.fromkeys(signal.get("symbol") for signal in candidate.get("signals", []) if signal.get("symbol")))),
                "symbols": sorted(list(dict.fromkeys(signal.get("symbol") for signal in candidate.get("signals", []) if signal.get("symbol")))),
                "total_bar_count": None,
                "symbol_bar_counts": {},
                "date_range": {
                    "start": dataset_plan.get("train", {}).get("start"),
                    "end": dataset_plan.get("test", {}).get("end"),
                },
                "walk_forward_window_count": len(dataset_plan.get("walk_forward_windows", [])),
                "split_bar_counts": {
                    "train": {"symbol_count": None, "bar_count": None},
                    "validation": {"symbol_count": None, "bar_count": None},
                    "test": {"symbol_count": None, "bar_count": None},
                },
            },
        }
        if self.settings.performance_enabled:
            self._candidate_eval_cache[cache_key] = dict(evaluation)
            while len(self._candidate_eval_cache) > self.settings.performance_dataset_plan_cache_size * 8:
                first_key = next(iter(self._candidate_eval_cache))
                self._candidate_eval_cache.pop(first_key, None)
        return evaluation

    def _build_split_metrics(
        self,
        expected_return_pct: float,
        win_rate_pct: float,
        drawdown_pct: float,
        max_loss_pct: float,
        variant_index: int,
        dataset_plan: dict,
        objective_metric: str,
        targets: dict[str, float],
    ) -> dict:
        split_adjustments = {
            "train": {"return": 1.08, "win_rate": 1.03, "drawdown": 0.94, "max_loss": 0.95},
            "validation": {"return": 0.98, "win_rate": 0.99, "drawdown": 1.03, "max_loss": 1.04},
            "test": {"return": 0.94, "win_rate": 0.97, "drawdown": 1.08, "max_loss": 1.09},
        }
        result: dict[str, dict] = {}
        for split_name, multipliers in split_adjustments.items():
            split_return = round(expected_return_pct * multipliers["return"], 2)
            split_win_rate = round(win_rate_pct * multipliers["win_rate"], 2)
            split_drawdown = round(drawdown_pct * multipliers["drawdown"], 2)
            split_max_loss = round(max_loss_pct * multipliers["max_loss"], 2)
            gross_exposure_pct = round(100.0 * min(1.0, 0.22 + 0.03 * max(0, variant_index)), 2)
            net_exposure_pct = round(gross_exposure_pct * 0.85, 2)
            result[split_name] = {
                "period": dataset_plan[split_name],
                "expected_return_pct": split_return,
                "win_rate_pct": split_win_rate,
                "drawdown_pct": split_drawdown,
                "max_loss_pct": split_max_loss,
                "observation_count": 0,
                "active_symbol_count": 0,
                "gross_exposure_pct": gross_exposure_pct,
                "net_exposure_pct": net_exposure_pct,
                "avg_daily_turnover_proxy_pct": round(2.0 + variant_index * 0.4, 2),
                "avg_volume": 0.0,
                "objective_score": self._objective_score(
                    objective_metric,
                    targets,
                    split_return,
                    split_win_rate,
                    split_drawdown,
                    split_max_loss,
                ),
            }

        walk_forward_results = []
        for index, window in enumerate(dataset_plan.get("walk_forward_windows", []), start=1):
            wf_return = round(expected_return_pct * (0.95 - index * 0.01) + variant_index * 0.15, 2)
            wf_win_rate = round(win_rate_pct * (0.985 - index * 0.005), 2)
            wf_drawdown = round(drawdown_pct * (1.03 + index * 0.01), 2)
            wf_max_loss = round(max_loss_pct * (1.04 + index * 0.01), 2)
            walk_forward_results.append(
                {
                    "window_id": window["window_id"],
                    "train_start": window["train_start"],
                    "train_end": window["train_end"],
                    "validation_start": window["validation_start"],
                    "validation_end": window["validation_end"],
                    "objective_score": self._objective_score(
                        objective_metric,
                        targets,
                        wf_return,
                        wf_win_rate,
                        wf_drawdown,
                        wf_max_loss,
                    ),
                    "expected_return_pct": wf_return,
                    "win_rate_pct": wf_win_rate,
                    "drawdown_pct": wf_drawdown,
                    "max_loss_pct": wf_max_loss,
                    "observation_count": 0,
                    "active_symbol_count": 0,
                    "gross_exposure_pct": round(100.0 * min(1.0, 0.22 + 0.03 * max(0, variant_index)), 2),
                    "net_exposure_pct": round(100.0 * min(1.0, 0.22 + 0.03 * max(0, variant_index)) * 0.85, 2),
                    "avg_daily_turnover_proxy_pct": round(2.0 + variant_index * 0.4, 2),
                    "avg_volume": 0.0,
                }
            )

        walk_forward_score = round(
            sum(item["objective_score"] for item in walk_forward_results) / max(1, len(walk_forward_results)),
            4,
        )
        stability_gap = abs(result["train"]["objective_score"] - result["test"]["objective_score"])
        stability_score = round(max(0.0, 1 - stability_gap) * 0.6 + walk_forward_score * 0.4, 4)
        result["walk_forward"] = walk_forward_results
        result["stability"] = {
            "score": stability_score,
            "walk_forward_score": walk_forward_score,
            "train_test_gap": round(stability_gap, 4),
        }
        return result

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

    def _evaluate_candidate_with_local_history(
        self,
        candidate: dict,
        objective_metric: str,
        targets: dict[str, float],
        dataset_plan: dict,
    ) -> dict | None:
        if "local_file" not in self.settings.market_data_enabled_providers:
            return None
        bars_by_symbol: dict[str, list[dict]] = {}
        exposure_by_symbol: dict[str, float] = {}
        max_position = float(candidate.get("parameters", {}).get("max_position_pct", 0.12) or 0.12)
        for signal in candidate.get("signals", []):
            symbol = signal.get("symbol")
            if not symbol:
                continue
            try:
                history = self.market_data.fetch_history(symbol=symbol, interval="1d", provider="local_file")
            except Exception:
                continue
            bars = history.get("bars", [])
            if not bars:
                continue
            bars_by_symbol[symbol] = bars
            action = str(signal.get("action", "hold")).lower()
            direction = 1.0 if action == "buy" else -1.0 if action == "sell" else 0.0
            exposure_by_symbol[symbol] = direction * float(signal.get("conviction", 0.0) or 0.0) * max_position
        if not bars_by_symbol:
            return None
        split_metrics = self.backtest_engine.evaluate(
            bars=bars_by_symbol,
            exposure=exposure_by_symbol,
            split_plan=dataset_plan,
        )
        if split_metrics is None:
            return None
        for split_name in ("train", "validation", "test"):
            metrics = split_metrics.get(split_name)
            if metrics is None:
                return None
            metrics["objective_score"] = self._objective_score(
                objective_metric,
                targets,
                metrics["expected_return_pct"],
                metrics["win_rate_pct"],
                metrics["drawdown_pct"],
                metrics["max_loss_pct"],
            )
        walk_forward_results = []
        for window in split_metrics.get("walk_forward", []):
            walk_forward_results.append(
                {
                    **window,
                    "objective_score": self._objective_score(
                        objective_metric,
                        targets,
                        window["expected_return_pct"],
                        window["win_rate_pct"],
                        window["drawdown_pct"],
                        window["max_loss_pct"],
                    ),
                }
            )
        walk_forward_score = round(
            sum(item["objective_score"] for item in walk_forward_results) / max(1, len(walk_forward_results)),
            4,
        )
        stability_gap = abs(split_metrics["train"]["objective_score"] - split_metrics["test"]["objective_score"])
        stability_score = round(max(0.0, 1 - stability_gap) * 0.6 + walk_forward_score * 0.4, 4)
        dataset_evaluation = {
            "train": split_metrics["train"],
            "validation": split_metrics["validation"],
            "test": split_metrics["test"],
            "walk_forward": walk_forward_results,
            "stability": {
                "score": stability_score,
                "walk_forward_score": walk_forward_score,
                "train_test_gap": round(stability_gap, 4),
            },
        }
        return {
            "expected_return_pct": split_metrics["test"]["expected_return_pct"],
            "win_rate_pct": split_metrics["test"]["win_rate_pct"],
            "drawdown_pct": split_metrics["test"]["drawdown_pct"],
            "max_loss_pct": split_metrics["test"]["max_loss_pct"],
            "objective_metric": objective_metric,
            "objective_value": {
                "return": split_metrics["test"]["expected_return_pct"],
                "win_rate": split_metrics["test"]["win_rate_pct"],
                "drawdown": -split_metrics["test"]["drawdown_pct"],
                "max_loss": -split_metrics["test"]["max_loss_pct"],
            }[objective_metric],
            "objective_score": split_metrics["test"]["objective_score"],
            "dataset_evaluation": dataset_evaluation,
            "validation_objective_score": split_metrics["validation"]["objective_score"],
            "test_objective_score": split_metrics["test"]["objective_score"],
            "walk_forward_score": walk_forward_score,
            "stability_score": stability_score,
            "evaluation_source": "local_history_backtest",
            "coverage_summary": split_metrics.get("coverage") or {},
        }

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
        winner_gap = abs(float(winner_entry.get("train_test_gap") or 0.0))
        winner_stability = float(winner_entry.get("stability_score") or 0.0)
        if (
            winner_stability >= 0.8
            and winner_gap <= 0.12
            and backtest_binding_summary.get("grade") == "strong"
            and coverage_summary.get("coverage_grade") == "healthy"
        ):
            robustness_grade = "strong"
            robustness_note = "The winner remains stable across out-of-sample evaluation and the train-test gap is controlled."
        elif (
            winner_stability >= 0.6
            and winner_gap <= 0.2
            and backtest_binding_summary.get("grade") in {"strong", "partial"}
            and coverage_summary.get("coverage_grade") != "degraded"
        ):
            robustness_grade = "acceptable"
            robustness_note = "The winner is usable, but stability or train-test dispersion still needs monitoring."
        else:
            robustness_grade = "fragile"
            robustness_note = "The winner is currently ahead, but robustness is weak and should be treated as research-only."
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
        release_ready = not failed_checks
        final_release_gate_summary = {
            "release_ready": release_ready,
            "failed_check_count": len(failed_checks),
            "passed_check_count": len(passed_checks),
            "gate_status": "passed" if release_ready else "blocked",
            "reason": (
                "The selected winner passed integrity and stress/overfit validation."
                if release_ready
                else "The selected winner is blocked by integrity and/or stress-overfit checks and must be reworked."
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
        merged = dict(research_summary)
        merged["final_release_gate_summary"] = final_release_gate_summary
        merged["check_failure_summary"] = check_failure_summary
        merged["next_iteration_focus"] = list(dict.fromkeys(next_iteration_focus))
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
            self._record_agent_activity("intelligence_agent", "ok", "search_intelligence", f"Cache hit for query={query}.", session.session_id)
            return session
        documents = [asdict(item) for item in self.intelligence.search(query, max_documents)]
        report = self.llm_runtime.summarize_intelligence(query, documents)
        report["factors"] = self._extract_intelligence_factors(documents, report)
        self._record_agent_activity("intelligence_agent", "ok", "search_intelligence", f"Collected {len(documents)} documents for query={query}.", session.session_id)
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
        return session

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
            )
            return session
        payload = self.market_data.fetch_financials(symbol=symbol, provider=provider)
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
            )
            return session
        payload = self.market_data.fetch_dark_pool(symbol=symbol, provider=provider)
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
            )
            return session
        payload = self.market_data.fetch_options(symbol=symbol, provider=provider, expiration=expiration)
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

    def expand_data_source(
        self,
        session_id: UUID,
        provider_name: str,
        category: str,
        base_url: str,
        api_key_env: str | None,
        docs_summary: str | None,
        docs_url: str | None = None,
        sample_endpoint: str | None = None,
        auth_style: str = "header",
        response_format: str = "json",
    ) -> WorkflowSession:
        session = self.get_session(session_id)
        request = DataSourceExpansionRequest(
            provider_name=provider_name,
            category=category,
            base_url=base_url,
            api_key_env=api_key_env,
            docs_summary=docs_summary,
            docs_url=docs_url,
            sample_endpoint=sample_endpoint,
            auth_style=auth_style,
            response_format=response_format,
        )
        result = self.data_source_expander.build_integration_package(request)
        result["run_id"] = f"datasource-{len(session.data_source_runs) + 1}"
        result["timestamp"] = self._now_iso()
        session.data_source_runs.append(result)
        self._archive_report(
            session,
            report_type="data_source_expansion",
            title=f"Data Source Expansion: {provider_name}",
            body=result,
            related_refs=[base_url, *( [docs_url] if docs_url else [] )],
        )
        self._append_history_event(
            session,
            "data_source_expansion_generated",
            "数据源扩充方案已生成。",
            {
                "provider_name": provider_name,
                "category": category,
                "docs_url": docs_url,
                "target_module": result["target_module"],
                "target_test": result["target_test"],
            },
        )
        self._record_agent_activity(
            "data_source_expansion_agent",
            "ok" if result["validation"]["ready_for_programmer_agent"] else "warning",
            "expand_data_source",
            f"Prepared adapter package for {provider_name} ({category}).",
            session.session_id,
        )
        return session

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
        result = self.programmer.execute(
            instruction=instruction,
            target_files=[selected_run["target_module"], selected_run["target_test"]],
            context=context,
            commit_changes=commit_changes,
        )
        result["timestamp"] = self._now_iso()
        result["applied_run_id"] = selected_run["run_id"]
        selected_run["programmer_apply"] = result
        session.programmer_runs.append(result)
        self._archive_report(
            session,
            report_type="data_source_programmer_apply",
            title=f"Data Source Apply: {selected_run['provider_name']}",
            body=result,
            related_refs=[selected_run["target_module"], selected_run["target_test"]],
        )
        self._append_history_event(
            session,
            "data_source_expansion_applied" if result.get("status") == "ok" else "data_source_expansion_apply_failed",
            "数据源扩充结果已交给 Programmer Agent 写入工作区。"
            if result.get("status") == "ok"
            else "数据源扩充结果交给 Programmer Agent 时失败。",
            {
                "run_id": selected_run["run_id"],
                "status": result.get("status"),
                "commit_hash": result.get("commit_hash"),
                "changed_files": result.get("changed_files", []),
            },
        )
        self._record_agent_activity(
            "programmer_agent",
            "ok" if result.get("status") == "ok" else "error",
            "apply_data_source_expansion",
            result.get("error") or f"Applied generated adapter for {selected_run['provider_name']}.",
            session.session_id,
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
        api_key_env: str | None,
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
            api_key_env=api_key_env,
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
        result = self.programmer.execute_with_retries(
            instruction=instruction,
            target_files=[selected_run["target_module"], selected_run["target_test"]],
            context=context,
            commit_changes=commit_changes,
            validator=self._validate_programmer_changes,
        )
        result["timestamp"] = self._now_iso()
        result["applied_run_id"] = selected_run["run_id"]
        selected_run["programmer_apply"] = result
        selected_run["terminal_runtime_summary"] = self._build_terminal_runtime_summary(selected_run)
        session.programmer_runs.append(result)
        self._archive_report(
            session,
            report_type="trading_terminal_programmer_apply",
            title=f"Trading Terminal Apply: {selected_run['terminal_name']}",
            body=result,
            related_refs=[selected_run["target_module"], selected_run["target_test"]],
        )
        self._append_history_event(
            session,
            "trading_terminal_integration_applied" if result.get("status") == "ok" else "trading_terminal_integration_apply_failed",
            "交易终端接入结果已交给 Programmer Agent 写入工作区。"
            if result.get("status") == "ok"
            else "交易终端接入结果交给 Programmer Agent 时失败。",
            {
                "run_id": selected_run["run_id"],
                "status": result.get("status"),
                "commit_hash": result.get("commit_hash"),
                "changed_files": result.get("changed_files", []),
            },
        )
        self._record_agent_activity(
            "programmer_agent",
            "ok" if result.get("status") == "ok" else "error",
            "apply_trading_terminal_integration",
            result.get("error") or f"Applied terminal adapter for {selected_run['terminal_name']}.",
            session.session_id,
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
        checks = result.get("checks", [])
        passed_check_count = sum(1 for item in checks if item.get("status") == "pass")
        readiness = selected_run.get("integration_readiness_summary", {})
        self._archive_report(
            session,
            report_type="trading_terminal_test",
            title=f"Trading Terminal Test: {selected_run['terminal_name']}",
            body=result,
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
            },
        )
        self._record_agent_activity(
            "trading_terminal_integration_agent",
            "ok" if result.get("status") == "ok" else "warning",
            "test_trading_terminal_integration",
            result.get("summary") or f"Tested terminal adapter for {selected_run['terminal_name']}.",
            session.session_id,
        )
        return session

    def _build_terminal_runtime_summary(self, run: dict) -> dict:
        readiness = run.get("integration_readiness_summary") or {}
        test = run.get("terminal_test") or {}
        repair = test.get("repair_summary") or {}
        checks = test.get("checks") or []
        passed = sum(1 for item in checks if item.get("status") == "pass")
        readiness_status = readiness.get("status") or "unknown"
        test_status = test.get("status") or "not_tested"
        if test_status == "ok" and readiness_status == "ready":
            return {
                "status": "healthy",
                "readiness_status": readiness_status,
                "test_status": test_status,
                "passed_check_count": passed,
                "total_check_count": len(checks),
                "note": "Terminal package is ready for the next connectivity stage.",
                "next_action": "Proceed to stronger endpoint verification or controlled local integration.",
                "primary_route": repair.get("primary_route") or "none",
            }
        if readiness_status == "blocked" or test_status in {"warning", "error"}:
            return {
                "status": "fragile",
                "readiness_status": readiness_status,
                "test_status": test_status,
                "passed_check_count": passed,
                "total_check_count": len(checks),
                "note": "Terminal package is not ready yet. Fix readiness gaps or failed smoke-test contracts first.",
                "next_action": (repair.get("actions") or ["Return to the terminal integration page and fix the failed contract or endpoint."])[0],
                "primary_route": repair.get("primary_route") or "data_shape_repair",
            }
        return {
            "status": "warning",
            "readiness_status": readiness_status,
            "test_status": test_status,
            "passed_check_count": passed,
            "total_check_count": len(checks),
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
            market_snapshots=session.market_snapshots,
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

    def _data_health_snapshot(self) -> dict:
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
                    latest_market = max([latest_market, latest_market_item.get("timestamp") or latest_market_item.get("observed_at")])
                    if latest_market_item.get("symbol"):
                        latest_market_symbol = latest_market_item.get("symbol")
                has_data = True
            if session.intelligence_runs:
                runs = [item for item in session.intelligence_runs if item.get("timestamp")]
                if runs:
                    latest_intelligence_item = max(runs, key=lambda item: item.get("timestamp") or "")
                    latest_intelligence = max([latest_intelligence, latest_intelligence_item.get("timestamp")])
                    latest_intelligence_query = latest_intelligence_item.get("query") or latest_intelligence_query
                has_data = True
            if session.financials_runs:
                runs = [item for item in session.financials_runs if item.get("timestamp")]
                if runs:
                    latest_financials_item = max(runs, key=lambda item: item.get("timestamp") or "")
                    latest_financials = max([latest_financials, latest_financials_item.get("timestamp")])
                    latest_financials_provider = latest_financials_item.get("provider") or latest_financials_provider
                has_data = True
            if session.dark_pool_runs:
                runs = [item for item in session.dark_pool_runs if item.get("timestamp")]
                if runs:
                    latest_dark_pool_item = max(runs, key=lambda item: item.get("timestamp") or "")
                    latest_dark_pool = max([latest_dark_pool, latest_dark_pool_item.get("timestamp")])
                    latest_dark_pool_provider = latest_dark_pool_item.get("provider") or latest_dark_pool_provider
                has_data = True
            if session.options_runs:
                runs = [item for item in session.options_runs if item.get("timestamp")]
                if runs:
                    latest_options_item = max(runs, key=lambda item: item.get("timestamp") or "")
                    latest_options = max([latest_options, latest_options_item.get("timestamp")])
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
        elif len(recent_data_failures) >= 3:
            status = "warning"
            note = "Recent data fetches show repeated failures. Check providers, keys, network, or local file paths."
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
        }

    def _runtime_health_summary(self) -> dict:
        latest_strategy_session = None
        latest_strategy_log = None
        latest_strategy_ts = ""
        latest_terminal_run = None
        latest_terminal_ts = ""
        for session in self.sessions.values():
            for item in session.strategy_training_log:
                ts = item.get("timestamp") or ""
                if ts >= latest_strategy_ts:
                    latest_strategy_ts = ts
                    latest_strategy_log = item
                    latest_strategy_session = session
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

        if latest_strategy_log:
            research = latest_strategy_log.get("research_summary") or {}
            gate = (research.get("final_release_gate_summary") or {}).get("gate_status") or "unknown"
            robustness = (research.get("robustness_summary") or {}).get("grade") or "unknown"
            if gate == "passed" and robustness == "strong":
                research_status = "healthy"
                research_note = "最新策略研究通过发布门，且稳健性较强。"
            elif gate == "blocked" or robustness == "fragile":
                research_status = "fragile"
                research_note = "最新策略研究仍被发布门阻塞，或稳健性不足。"
            else:
                research_note = "最新策略研究已完成，但仍需继续观察 gate 与稳健性。"

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

        latest_terminal_runtime = {}
        if latest_terminal_run:
            latest_terminal_runtime = latest_terminal_run.get("terminal_runtime_summary") or self._build_terminal_runtime_summary(latest_terminal_run)
            terminal_status = latest_terminal_runtime.get("status") or "warning"
            terminal_note = latest_terminal_runtime.get("note") or "终端接入已有测试记录，但仍建议继续检查返回结构和 endpoint 完整性。"

        data_health = self._data_health_snapshot()
        data_status = "healthy"
        data_note = "最近数据层没有明显失败。"
        if data_health.get("recent_failure_count", 0) > 0:
            data_status = "warning"
            data_note = "最近存在数据查询失败，建议检查 provider、网络或本地路径。"
        if (
            not data_health.get("latest_market_timestamp")
            and not data_health.get("latest_intelligence_timestamp")
            and not data_health.get("latest_financials_timestamp")
            and not data_health.get("latest_dark_pool_timestamp")
            and not data_health.get("latest_options_timestamp")
        ):
            data_status = "fragile"
            data_note = "当前还没有任何有效数据更新记录。"

        llm_description = self.llm_runtime.describe()
        llm_tasks = llm_description.get("tasks", {})
        fallback_tasks = [name for name, item in llm_tasks.items() if item.get("generation_mode") == "template_fallback"]
        live_tasks = [name for name, item in llm_tasks.items() if item.get("generation_mode") == "live_llm"]
        if not llm_description.get("enabled"):
            llm_status = "fragile"
            llm_note = "LLM runtime 当前被禁用，关键研究与总结任务将退回 fallback。"
        elif live_tasks and not fallback_tasks:
            llm_status = "healthy"
            llm_note = "关键 LLM 任务当前都走 live provider。"
        elif live_tasks and fallback_tasks:
            llm_status = "warning"
            llm_note = "当前 LLM 任务处于 live 与 fallback 混合状态，建议补齐缺失凭据。"
        else:
            llm_status = "fragile"
            llm_note = "当前所有 LLM 任务都在 fallback 模式下运行。"

        statuses = [research_status, repair_status, terminal_status, data_status, llm_status]
        overall_status = "healthy"
        overall_note = "研究、修复、终端、数据和模型层整体健康。"
        if "fragile" in statuses:
            overall_status = "fragile"
            overall_note = "至少有一条关键链路处于脆弱状态，当前不适合长时间无人值守使用。"
        elif "warning" in statuses:
            overall_status = "warning"
            overall_note = "整体可用，但仍有链路需要继续观察和修复。"

        return {
            "status": overall_status,
            "note": overall_note,
            "research": {"status": research_status, "note": research_note, "timestamp": latest_strategy_ts or None},
            "repair": {"status": repair_status, "note": repair_note, "timestamp": latest_strategy_ts or None},
            "terminal": {
                "status": terminal_status,
                "note": terminal_note,
                "timestamp": latest_terminal_ts or None,
                "next_action": latest_terminal_runtime.get("next_action"),
                "primary_route": latest_terminal_runtime.get("primary_route"),
            },
            "data": {"status": data_status, "note": data_note},
            "llm": {
                "status": llm_status,
                "note": llm_note,
                "live_task_count": len(live_tasks),
                "fallback_task_count": len(fallback_tasks),
                "fallback_tasks": fallback_tasks[:8],
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
