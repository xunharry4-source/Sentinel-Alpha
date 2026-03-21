from __future__ import annotations

from typing import Protocol

from sentinel_alpha.domain.models import BehaviorEvent, BehavioralReport, StrategyBrief, UserProfile


class BehavioralRunRepository(Protocol):
    def save_behavioral_run(
        self,
        user: UserProfile,
        events: list[BehaviorEvent],
        report: BehavioralReport,
        brief: StrategyBrief,
    ) -> None: ...


class MemoryStore(Protocol):
    def add_behavior_memory(
        self,
        user: UserProfile,
        report: BehavioralReport,
        brief: StrategyBrief,
    ) -> None: ...
