from __future__ import annotations

from sentinel_alpha.strategies.base import StrategyCandidate, StrategyContext, StrategySignal, TradingStrategy


class TrendFollowingAlignedStrategy(TradingStrategy):
    strategy_type = "trend_following_aligned"

    def build_candidate(self, context: StrategyContext) -> StrategyCandidate:
        action = "hold"
        conviction = 0.4
        if context.market.trend_score >= 0.55 and context.market.event_risk_score <= 0.5:
            action = "accumulate"
            conviction = min(0.9, 0.55 + context.market.trend_score * 0.35)
        elif context.market.trend_score < 0.0:
            action = "defensive"
            conviction = 0.72

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
                        "Follow persistent trend only when event risk remains bounded.",
                        f"trend_score={context.market.trend_score:.2f}",
                        f"event_risk_score={context.market.event_risk_score:.2f}",
                    ],
                )
            ],
            parameters={
                "trend_entry_threshold": 0.55,
                "event_risk_cap": 0.50,
                "max_position_pct": round(context.risk_policy.max_position_pct, 4),
            },
            metadata={
                "style": "trend_following",
                "selected_universe_size": len(context.selected_universe),
            },
        )
