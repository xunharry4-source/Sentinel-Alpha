from dataclasses import dataclass

from sentinel_alpha.agents.behavioral_profiler import BehavioralProfilerAgent
from sentinel_alpha.agents.strategy_evolver import StrategyEvolverAgent
from sentinel_alpha.domain.models import BehaviorEvent, MarketSnapshot, UserProfile
from sentinel_alpha.orchestration.pipeline import PersonalTradingExpertPipeline


@dataclass
class FakeRepository:
    calls: int = 0

    def save_behavioral_run(self, user, events, report, brief) -> None:
        self.calls += 1


@dataclass
class FakeMemoryStore:
    calls: int = 0

    def add_behavior_memory(self, user, report, brief) -> None:
        self.calls += 1


@dataclass
class FakeEventWriter:
    calls: int = 0

    def write_behavior_events(self, user_id, events) -> None:
        self.calls += 1


@dataclass
class FakeRuntimeBus:
    cache_calls: int = 0
    publish_calls: int = 0

    def cache_strategy_brief(self, brief) -> None:
        self.cache_calls += 1

    def publish_agent_event(self, channel, payload) -> None:
        self.publish_calls += 1


def test_behavior_report_and_policy_are_bounded() -> None:
    user = UserProfile(
        user_id="u1",
        preferred_assets=["NVDA"],
        capital_base=100000,
        target_holding_days=5,
        self_reported_risk_tolerance=0.3,
        confidence_level=0.4,
    )
    events = [
        BehaviorEvent("s1", -10.0, "sell", 0.8, -0.8, 30),
        BehaviorEvent("s2", -15.0, "buy", 0.9, -0.7, 60),
        BehaviorEvent("s3", 2.0, "buy", 0.6, 0.4, 100),
    ]
    market = MarketSnapshot("NVDA", 16.0, 35.0, 0.5, 0.4, 0.9)

    profiler = BehavioralProfilerAgent()
    report = profiler.profile(events)

    evolver = StrategyEvolverAgent()
    policy = evolver.derive_risk_policy(user, report)
    brief = evolver.synthesize(user, market, report, policy)

    assert 0.0 <= report.panic_sell_score <= 1.0
    assert 0.0 <= report.noise_susceptibility <= 1.0
    assert 0.05 <= policy.max_position_pct <= 0.35
    assert 0.03 <= policy.hard_stop_loss_pct <= 0.15
    assert brief.symbol == "NVDA"
    assert brief.recommended_position_pct >= 0.0


def test_pipeline_calls_repository_and_memory_store() -> None:
    user = UserProfile(
        user_id="u2",
        preferred_assets=["TSLA"],
        capital_base=200000,
        target_holding_days=8,
        self_reported_risk_tolerance=0.5,
        confidence_level=0.6,
    )
    events = [
        BehaviorEvent("s1", -12.0, "sell", 0.7, -0.6, 40),
        BehaviorEvent("s2", -14.0, "buy", 0.8, -0.5, 70),
    ]
    market = MarketSnapshot("TSLA", 20.0, 45.0, 0.4, 0.55, 0.95)
    repository = FakeRepository()
    memory_store = FakeMemoryStore()
    event_writer = FakeEventWriter()
    runtime_bus = FakeRuntimeBus()

    brief = PersonalTradingExpertPipeline(
        repository=repository,
        memory_store=memory_store,
        event_writer=event_writer,
        runtime_bus=runtime_bus,
    ).run(
        user,
        events,
        market,
    )

    assert brief.symbol == "TSLA"
    assert repository.calls == 1
    assert memory_store.calls == 1
    assert event_writer.calls == 1
    assert runtime_bus.cache_calls == 1
    assert runtime_bus.publish_calls == 1
