from __future__ import annotations

from sentinel_alpha.strategies.base import TradingStrategy
from sentinel_alpha.strategies.mean_reversion import MeanReversionAlignedStrategy
from sentinel_alpha.strategies.rule_based import RuleBasedAlignedStrategy
from sentinel_alpha.strategies.trend_following import TrendFollowingAlignedStrategy


class StrategyRegistry:
    def __init__(self) -> None:
        self._strategies: dict[str, TradingStrategy] = {
            RuleBasedAlignedStrategy.strategy_type: RuleBasedAlignedStrategy(),
            TrendFollowingAlignedStrategy.strategy_type: TrendFollowingAlignedStrategy(),
            MeanReversionAlignedStrategy.strategy_type: MeanReversionAlignedStrategy(),
        }

    def get(self, strategy_type: str) -> TradingStrategy:
        if strategy_type not in self._strategies:
            raise KeyError(f"Unknown strategy_type: {strategy_type}")
        return self._strategies[strategy_type]

    def list_types(self) -> list[str]:
        return sorted(self._strategies.keys())
