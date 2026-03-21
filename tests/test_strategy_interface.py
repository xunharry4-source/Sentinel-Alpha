from sentinel_alpha.agents.strategy_evolver import StrategyEvolverAgent
from sentinel_alpha.domain.models import BehavioralReport, MarketSnapshot, UserProfile


def test_generic_strategy_interface_builds_candidate() -> None:
    user = UserProfile(
        user_id="u-strategy",
        preferred_assets=["QQQ", "SMH"],
        capital_base=500000,
        target_holding_days=10,
        self_reported_risk_tolerance=0.5,
        confidence_level=0.6,
    )
    report = BehavioralReport(
        panic_sell_score=0.2,
        averaging_down_score=0.1,
        noise_susceptibility=0.3,
        intervention_risk=0.25,
        max_comfort_drawdown_pct=12.0,
        discipline_score=0.7,
        notes=[],
    )
    market = MarketSnapshot(
        symbol="QQQ",
        expected_return_pct=14.0,
        realized_volatility_pct=22.0,
        trend_score=0.6,
        event_risk_score=0.25,
        liquidity_score=0.95,
    )

    evolver = StrategyEvolverAgent()
    policy = evolver.derive_risk_policy(user, report)
    candidate = evolver.build_strategy_candidate(
        user=user,
        market=market,
        report=report,
        policy=policy,
        selected_universe=["QQQ", "SMH", "XLK", "SOXX", "NVDA"],
        feedback="Reduce event risk.",
    )

    assert candidate.strategy_type == "rule_based_aligned"
    assert candidate.version == "v1"
    assert candidate.signals[0].symbol == "QQQ"
    assert "max_position_pct" in candidate.parameters


def test_multiple_strategy_types_are_supported() -> None:
    user = UserProfile(
        user_id="u-strategy-2",
        preferred_assets=["QQQ", "SMH"],
        capital_base=500000,
        target_holding_days=10,
        self_reported_risk_tolerance=0.5,
        confidence_level=0.6,
    )
    report = BehavioralReport(
        panic_sell_score=0.2,
        averaging_down_score=0.2,
        noise_susceptibility=0.3,
        intervention_risk=0.25,
        max_comfort_drawdown_pct=12.0,
        discipline_score=0.7,
        notes=[],
    )
    evolver = StrategyEvolverAgent()
    policy = evolver.derive_risk_policy(user, report)

    trend_market = MarketSnapshot("QQQ", 14.0, 22.0, 0.7, 0.25, 0.95)
    trend_candidate = evolver.build_strategy_candidate(
        user=user,
        market=trend_market,
        report=report,
        policy=policy,
        selected_universe=["QQQ", "SMH", "XLK", "SOXX", "NVDA"],
        strategy_type="trend_following_aligned",
    )

    mean_market = MarketSnapshot("QQQ", 11.0, 20.0, 0.1, 0.2, 0.95)
    mean_candidate = evolver.build_strategy_candidate(
        user=user,
        market=mean_market,
        report=report,
        policy=policy,
        selected_universe=["QQQ", "SMH", "XLK", "SOXX", "NVDA"],
        strategy_type="mean_reversion_aligned",
    )

    assert trend_candidate.strategy_type == "trend_following_aligned"
    assert mean_candidate.strategy_type == "mean_reversion_aligned"
    assert trend_candidate.strategy_id != mean_candidate.strategy_id
