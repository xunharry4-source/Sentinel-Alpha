from __future__ import annotations

from sentinel_alpha.agents.behavioral_profiler import BehavioralProfilerAgent
from sentinel_alpha.agents.strategy_evolver import StrategyEvolverAgent
from sentinel_alpha.domain.models import BehaviorEvent, MarketSnapshot, UserProfile


def test_strategy_evolver_agent_builds_candidate_and_brief() -> None:
    evolver = StrategyEvolverAgent()
    profiler = BehavioralProfilerAgent()
    report = profiler.profile(
        [
            BehaviorEvent(
                scenario_id="scenario-2",
                price_drawdown_pct=-8.0,
                action="hold",
                noise_level=0.4,
                sentiment_pressure=0.0,
                latency_seconds=120.0,
            ),
            BehaviorEvent(
                scenario_id="scenario-2",
                price_drawdown_pct=-4.0,
                action="buy",
                noise_level=0.3,
                sentiment_pressure=0.2,
                latency_seconds=160.0,
            ),
        ]
    )
    user = UserProfile(
        user_id="u-1",
        preferred_assets=["TSLA", "NVDA"],
        capital_base=30000,
        target_holding_days=10,
        self_reported_risk_tolerance=0.5,
        confidence_level=0.6,
    )
    market = MarketSnapshot(
        symbol="TSLA",
        expected_return_pct=14.0,
        realized_volatility_pct=30.0,
        trend_score=0.5,
        event_risk_score=0.2,
        liquidity_score=0.9,
    )

    policy = evolver.derive_risk_policy(user, report)
    brief = evolver.synthesize(user, market, report, policy)
    candidate = evolver.build_strategy_candidate(
        user=user,
        market=market,
        report=report,
        policy=policy,
        selected_universe=["TSLA", "NVDA", "QQQ"],
        feedback="Reduce concentration",
        strategy_type="trend_following_aligned",
    )

    assert policy.max_position_pct > 0
    assert brief.symbol == "TSLA"
    assert candidate.strategy_type == "trend_following_aligned"
    assert candidate.version
    assert candidate.parameters
