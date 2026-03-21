from __future__ import annotations

from sentinel_alpha.strategies.base import StrategyCandidate, StrategyContext, StrategySignal, TradingStrategy


class RuleBasedAlignedStrategy(TradingStrategy):
    strategy_type = "rule_based_aligned"

    def build_candidate(self, context: StrategyContext) -> StrategyCandidate:
        action = "hold"
        conviction = 0.45
        if context.market.trend_score > 0.4 and context.behavior.panic_sell_score < 0.45:
            action = "accumulate"
            conviction = 0.68
        elif context.market.event_risk_score > 0.7 or context.behavior.noise_susceptibility > 0.65:
            action = "defensive"
            conviction = 0.74

        rationale = [
            f"trend_score={context.market.trend_score:.2f}",
            f"event_risk_score={context.market.event_risk_score:.2f}",
            f"panic_sell_score={context.behavior.panic_sell_score:.2f}",
            f"noise_sensitivity={context.behavior.noise_susceptibility:.2f}",
        ]
        if context.feedback:
            rationale.append(f"user_feedback={context.feedback}")

        return StrategyCandidate(
            strategy_id=f"{context.market.symbol}-{self.strategy_type}",
            version="v1",
            strategy_type=self.strategy_type,
            signals=[
                StrategySignal(
                    symbol=context.market.symbol,
                    action=action,
                    conviction=conviction,
                    rationale=rationale,
                )
            ],
            parameters={
                "max_position_pct": round(context.risk_policy.max_position_pct, 4),
                "hard_stop_loss_pct": round(context.risk_policy.hard_stop_loss_pct, 4),
                "portfolio_drawdown_limit_pct": round(context.risk_policy.portfolio_drawdown_limit_pct, 4),
            },
            metadata={
                "selected_universe_size": len(context.selected_universe),
                "feedback_present": "yes" if context.feedback else "no",
            },
        )
