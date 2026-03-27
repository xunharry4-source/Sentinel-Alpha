from __future__ import annotations

from sentinel_alpha.backtesting.engine import SimpleBacktestEngine
from sentinel_alpha.backtesting.metrics import DefaultStrategyMetricsEngine


class DummySettings:
    def __init__(self, providers: list[str]) -> None:
        self.market_data_enabled_providers = providers


class DummyMarketData:
    def __init__(self, bars_by_symbol: dict[str, list[dict]]) -> None:
        self._bars_by_symbol = bars_by_symbol

    def fetch_history(self, symbol: str, interval: str = "1d", provider: str = "local_file") -> dict:
        return {"bars": self._bars_by_symbol[symbol]}


def make_candidate() -> dict:
    return {
        "signals": [{"symbol": "AAPL", "action": "buy", "conviction": 0.8}],
        "parameters": {"max_position_pct": 0.2, "hard_stop_loss_pct": 0.06},
    }


def make_dataset_plan() -> dict:
    return {
        "train": {"start": "2023-01-03", "end": "2023-12-17"},
        "validation": {"start": "2024-01-03", "end": "2024-06-17"},
        "test": {"start": "2024-07-03", "end": "2024-12-17"},
        "walk_forward_windows": [],
    }


def make_targets() -> dict[str, float]:
    return {
        "target_return_pct": 18.0,
        "target_win_rate_pct": 58.0,
        "target_drawdown_pct": 12.0,
        "target_max_loss_pct": 6.0,
    }


def make_year_spanning_bars() -> list[dict]:
    bars: list[dict] = []
    price = 100.0
    for year in (2023, 2024):
        for month in range(1, 13):
            for day in (3, 10, 17):
                close = price * (1.01 if (month + day) % 4 else 0.985)
                bars.append(
                    {
                        "timestamp": f"{year}-{month:02d}-{day:02d}",
                        "open": round(price, 2),
                        "high": round(max(price, close) * 1.01, 2),
                        "low": round(min(price, close) * 0.99, 2),
                        "close": round(close, 2),
                        "volume": 1000 + month * 10 + day,
                    }
                )
                price = close
    return bars


def test_metrics_engine_contract_for_surrogate_payload() -> None:
    engine = DefaultStrategyMetricsEngine()
    result = engine.evaluate_candidate(
        candidate=make_candidate(),
        objective_metric="return",
        targets=make_targets(),
        variant_index=1,
        dataset_plan=make_dataset_plan(),
        backtest_engine=SimpleBacktestEngine(),
        market_data=DummyMarketData({}),
        settings=DummySettings([]),
    )

    assert sorted(result.keys()) == [
        "annual_performance",
        "coverage_summary",
        "dataset_evaluation",
        "drawdown_pct",
        "evaluation_source",
        "expected_return_pct",
        "max_loss_pct",
        "objective_metric",
        "objective_score",
        "objective_value",
        "stability_score",
        "test_objective_score",
        "validation_objective_score",
        "walk_forward_score",
        "win_rate_pct",
    ]
    assert sorted(result["dataset_evaluation"].keys()) == ["full_period", "stability", "test", "train", "validation", "walk_forward"]
    assert sorted(result["dataset_evaluation"]["full_period"].keys()) == [
        "annual_breakdown",
        "avg_gain_trade_pct",
        "avg_loss_trade_pct",
        "compounded_return_pct",
        "drawdown_pct",
        "expected_return_pct",
        "losing_trade_count",
        "max_loss_pct",
        "period",
        "win_rate_pct",
        "winning_trade_count",
    ]
    assert result["evaluation_source"] == "heuristic_surrogate"


def test_metrics_engine_golden_payload_for_local_history() -> None:
    bars = make_year_spanning_bars()
    engine = DefaultStrategyMetricsEngine()
    result = engine.evaluate_candidate(
        candidate=make_candidate(),
        objective_metric="return",
        targets=make_targets(),
        variant_index=0,
        dataset_plan=make_dataset_plan(),
        backtest_engine=SimpleBacktestEngine(),
        market_data=DummyMarketData({"AAPL": bars}),
        settings=DummySettings(["local_file"]),
    )

    assert result["evaluation_source"] == "local_history_backtest"
    assert result["expected_return_pct"] == -0.24
    assert result["win_rate_pct"] == 76.47
    assert result["drawdown_pct"] == 0.56
    assert result["max_loss_pct"] == 0.32
    assert result["objective_score"] == 0.827

    full_period = result["dataset_evaluation"]["full_period"]
    assert full_period["expected_return_pct"] == -1.12
    assert full_period["compounded_return_pct"] == -1.12
    assert full_period["avg_loss_trade_pct"] == 0.32
    assert full_period["avg_gain_trade_pct"] == 0.08
    assert full_period["winning_trade_count"] == 54
    assert full_period["losing_trade_count"] == 17

    annual = result["annual_performance"]
    assert len(annual) == 2
    assert annual[0]["year"] == 2023
    assert annual[0]["return_pct"] == -0.4
    assert annual[0]["compounded_return_pct"] == -0.4
    assert annual[1]["year"] == 2024
    assert annual[1]["compounded_return_pct"] == -0.8
