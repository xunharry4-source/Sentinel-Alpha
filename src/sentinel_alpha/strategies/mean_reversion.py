from __future__ import annotations

from sentinel_alpha.strategies.base import StrategyCandidate, StrategyContext, StrategySignal, TradingStrategy


class MeanReversionAlignedStrategy(TradingStrategy):
    strategy_type = "mean_reversion_aligned"

    def build_candidate(self, context: StrategyContext) -> StrategyCandidate:
        action = "hold"
        conviction = 0.38
        if context.market.trend_score < 0.2 and context.market.event_risk_score < 0.45 and context.behavior.averaging_down_score < 0.45:
            action = "accumulate"
            conviction = 0.61
        elif context.behavior.averaging_down_score >= 0.45:
            action = "defensive"
            conviction = 0.76

        return StrategyCandidate(
            strategy_id=f"{context.market.symbol}-{self.strategy_type}",
            version="v1",
            strategy_type=self.strategy_type,
            signals=[
                StrategySignal(
                    symbol=context.market.symbol,
                    action=action,
                    conviction=conviction,
                    rationale=[
                        "Mean reversion is only allowed when downside averaging tendency is controlled.",
                        f"trend_score={context.market.trend_score:.2f}",
                        f"averaging_down_score={context.behavior.averaging_down_score:.2f}",
                    ],
                )
            ],
            parameters={
                "reversion_entry_trend_cap": 0.20,
                "averaging_down_guard": 0.45,
                "hard_stop_loss_pct": round(context.risk_policy.hard_stop_loss_pct, 4),
            },
            metadata={
                "style": "mean_reversion",
                "selected_universe_size": len(context.selected_universe),
            },
        )
