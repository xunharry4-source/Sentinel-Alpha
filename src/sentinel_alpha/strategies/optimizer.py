from __future__ import annotations

from sentinel_alpha.strategies.base import StrategyCandidate, StrategyContext
from sentinel_alpha.strategies.registry import StrategyRegistry


class StrategyOptimizer:
    """Unified entry point for all strategy implementations."""

    def __init__(self, registry: StrategyRegistry | None = None) -> None:
        self.registry = registry or StrategyRegistry()

    def build_candidate(self, strategy_type: str, context: StrategyContext) -> StrategyCandidate:
        strategy = self.registry.get(strategy_type)
        return strategy.build_candidate(context)
