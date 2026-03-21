from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from sentinel_alpha.domain.models import BehavioralReport, MarketSnapshot, RiskPolicy, UserProfile


@dataclass(slots=True)
class StrategyContext:
    user: UserProfile
    behavior: BehavioralReport
    market: MarketSnapshot
    risk_policy: RiskPolicy
    selected_universe: list[str]
    feedback: str | None = None
    features: dict = field(default_factory=dict)


@dataclass(slots=True)
class StrategySignal:
    symbol: str
    action: str
    conviction: float
    rationale: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StrategyCandidate:
    strategy_id: str
    version: str
    strategy_type: str
    signals: list[StrategySignal]
    parameters: dict[str, float | int | str]
    metadata: dict[str, str | float | int]


class TradingStrategy(Protocol):
    strategy_type: str

    def build_candidate(self, context: StrategyContext) -> StrategyCandidate:
        """Create a strategy candidate from the shared strategy context."""
