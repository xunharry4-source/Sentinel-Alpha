from __future__ import annotations

from sentinel_alpha.agents.behavioral_profiler import BehavioralProfilerAgent
from sentinel_alpha.agents.strategy_evolver import StrategyEvolverAgent
from sentinel_alpha.domain.models import BehaviorEvent, MarketSnapshot, StrategyBrief, UserProfile
from sentinel_alpha.domain.ports import BehavioralRunRepository, MemoryStore


class PersonalTradingExpertPipeline:
    """Minimal end-to-end orchestration for the first research interface."""

    def __init__(
        self,
        repository: BehavioralRunRepository | None = None,
        memory_store: MemoryStore | None = None,
        event_writer: object | None = None,
        runtime_bus: object | None = None,
    ) -> None:
        self.profiler = BehavioralProfilerAgent()
        self.evolver = StrategyEvolverAgent()
        self.repository = repository
        self.memory_store = memory_store
        self.event_writer = event_writer
        self.runtime_bus = runtime_bus

    def run(
        self,
        user: UserProfile,
        behavior_events: list[BehaviorEvent],
        market: MarketSnapshot,
    ) -> StrategyBrief:
        report = self.profiler.profile(behavior_events)
        policy = self.evolver.derive_risk_policy(user, report)
        brief = self.evolver.synthesize(user, market, report, policy)

        if self.repository is not None:
            self.repository.save_behavioral_run(user, behavior_events, report, brief)
        if self.event_writer is not None:
            self.event_writer.write_behavior_events(user.user_id, behavior_events)
        if self.memory_store is not None:
            self.memory_store.add_behavior_memory(user, report, brief)
        if self.runtime_bus is not None:
            self.runtime_bus.cache_strategy_brief(brief)
            self.runtime_bus.publish_agent_event(
                "agent.strategy.generated",
                {
                    "user_id": user.user_id,
                    "symbol": brief.symbol,
                    "action_bias": brief.action_bias,
                },
            )

        return brief
