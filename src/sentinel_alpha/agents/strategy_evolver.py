from __future__ import annotations

from sentinel_alpha.domain.models import BehavioralReport, MarketSnapshot, RiskPolicy, StrategyBrief, UserProfile
from sentinel_alpha.domain.utility import aligned_utility
from sentinel_alpha.strategies.base import StrategyCandidate, StrategyContext
from sentinel_alpha.strategies.optimizer import StrategyOptimizer


class StrategyEvolverAgent:
    """Generates user-aligned risk policy and strategy summary."""

    def __init__(self, optimizer: StrategyOptimizer | None = None) -> None:
        self.optimizer = optimizer or StrategyOptimizer()

    def derive_risk_policy(self, user: UserProfile, report: BehavioralReport) -> RiskPolicy:
        risk_tolerance = max(0.05, min(1.0, user.self_reported_risk_tolerance))
        confidence = max(0.05, min(1.0, user.confidence_level))

        max_position_pct = max(
            0.05,
            min(
                0.35,
                0.08
                + risk_tolerance * 0.18
                + report.discipline_score * 0.08
                - report.noise_susceptibility * 0.06
                - report.averaging_down_score * 0.07,
            ),
        )
        hard_stop_loss_pct = max(
            0.03,
            min(
                0.15,
                report.max_comfort_drawdown_pct / 100.0 * 0.8
                - report.panic_sell_score * 0.03
                - report.noise_susceptibility * 0.02,
            ),
        )
        portfolio_drawdown_limit_pct = max(
            0.05,
            min(0.18, hard_stop_loss_pct * 1.8 + confidence * 0.02),
        )
        cooldown_hours = int(
            round(4 + report.averaging_down_score * 20 + report.intervention_risk * 12)
        )
        narrative_override_penalty = max(0.1, min(0.9, 0.2 + report.noise_susceptibility * 0.5))
        intervention_buffer_pct = max(0.02, min(0.12, 0.03 + report.intervention_risk * 0.07))

        return RiskPolicy(
            max_position_pct=max_position_pct,
            hard_stop_loss_pct=hard_stop_loss_pct,
            portfolio_drawdown_limit_pct=portfolio_drawdown_limit_pct,
            cooldown_hours=cooldown_hours,
            narrative_override_penalty=narrative_override_penalty,
            intervention_buffer_pct=intervention_buffer_pct,
        )

    def synthesize(
        self,
        user: UserProfile,
        market: MarketSnapshot,
        report: BehavioralReport,
        policy: RiskPolicy,
    ) -> StrategyBrief:
        lambda_value = max(
            0.2,
            min(
                2.0,
                0.4
                + (1.0 - user.self_reported_risk_tolerance) * 0.8
                + report.panic_sell_score * 0.5
                + report.noise_susceptibility * 0.3
                + (1.0 - user.confidence_level) * 0.4,
            ),
        )
        utility = aligned_utility(
            expected_return_pct=market.expected_return_pct,
            volatility_pct=market.realized_volatility_pct,
            risk_aversion_lambda=lambda_value,
            report=report,
            market=market,
        )
        recommended_position_pct = max(
            0.0,
            min(
                policy.max_position_pct,
                policy.max_position_pct
                * (1.0 - market.event_risk_score * policy.narrative_override_penalty)
                * (0.8 + max(0.0, market.trend_score) * 0.4),
            ),
        )

        action_bias = "hold"
        if utility > 0.02 and recommended_position_pct >= 0.08:
            action_bias = "accumulate"
        elif utility < 0.0 or market.event_risk_score > 0.75:
            action_bias = "defensive"

        rationale = [
            f"Utility score is {utility:.3f} after volatility and behavior alignment penalties.",
            f"Hard stop is capped at {policy.hard_stop_loss_pct:.1%} based on observed drawdown tolerance.",
            f"Position size is capped at {recommended_position_pct:.1%} due to intervention and noise sensitivity.",
        ]
        rationale.extend(report.notes)

        return StrategyBrief(
            symbol=market.symbol,
            action_bias=action_bias,
            expected_return_pct=market.expected_return_pct,
            worst_case_drawdown_pct=policy.portfolio_drawdown_limit_pct * 100.0,
            utility_score=utility,
            recommended_position_pct=recommended_position_pct * 100.0,
            rationale=rationale,
        )

    def build_strategy_candidate(
        self,
        user: UserProfile,
        market: MarketSnapshot,
        report: BehavioralReport,
        policy: RiskPolicy,
        selected_universe: list[str],
        feedback: str | None = None,
        strategy_type: str = "rule_based_aligned",
        features: dict | None = None,
    ) -> StrategyCandidate:
        context = StrategyContext(
            user=user,
            behavior=report,
            market=market,
            risk_policy=policy,
            selected_universe=selected_universe,
            feedback=feedback,
            features=features or {},
        )
        return self.optimizer.build_candidate(strategy_type, context)
