from __future__ import annotations

from sentinel_alpha.agents.behavioral_profiler import BehavioralProfilerAgent
from sentinel_alpha.domain.models import BehaviorEvent


def test_behavioral_profiler_agent_profiles_behavior_events() -> None:
    agent = BehavioralProfilerAgent()
    report = agent.profile(
        [
            BehaviorEvent(
                scenario_id="scenario-1",
                price_drawdown_pct=-10.0,
                action="sell",
                noise_level=0.9,
                sentiment_pressure=-0.8,
                latency_seconds=40.0,
            ),
            BehaviorEvent(
                scenario_id="scenario-1",
                price_drawdown_pct=-14.0,
                action="buy",
                noise_level=0.85,
                sentiment_pressure=0.9,
                latency_seconds=35.0,
            ),
        ]
    )

    assert 0.0 <= report.panic_sell_score <= 1.0
    assert 0.0 <= report.averaging_down_score <= 1.0
    assert 0.0 <= report.noise_susceptibility <= 1.0
    assert 0.0 <= report.intervention_risk <= 1.0
    assert report.max_comfort_drawdown_pct >= 3.0
