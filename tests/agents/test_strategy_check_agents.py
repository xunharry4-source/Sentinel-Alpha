from __future__ import annotations

from sentinel_alpha.agents.strategy_integrity_checker import StrategyIntegrityCheckerAgent
from sentinel_alpha.agents.strategy_stress_checker import StrategyStressCheckerAgent


def test_strategy_integrity_checker_rejects_future_leakage() -> None:
    agent = StrategyIntegrityCheckerAgent()
    result = agent.evaluate(
        {"iteration_no": 2, "selected_universe": ["AAPL", "AMD"]},
        {
            "strategy_type": "rule_based_aligned",
            "parameters": {"oracle_bias": 1},
            "metadata": {},
            "signals": [{"conviction": 0.99, "rationale": ["Use future earnings result and next candle direction."]}],
        },
    )

    assert result["status"] == "fail"
    assert result["flags"]


def test_strategy_stress_checker_rejects_fragile_candidates() -> None:
    agent = StrategyStressCheckerAgent()
    result = agent.evaluate(
        {"selected_universe": ["AAPL"], "strategy_type": "mean_reversion_aligned"},
        {
            "strategy_type": "mean_reversion_aligned",
            "parameters": {
                "alpha": 1,
                "beta": 2,
                "gamma": 3,
                "delta": 4,
                "max_position_pct": 0.22,
            },
            "metadata": {},
        },
        {
            "noise_sensitivity": 0.82,
            "overtrading_tendency": 0.91,
            "bottom_fishing_tendency": 0.52,
        },
        compatibility=0.48,
    )

    assert result["status"] == "fail"
    assert "too_small_trade_universe" in result["flags"]
