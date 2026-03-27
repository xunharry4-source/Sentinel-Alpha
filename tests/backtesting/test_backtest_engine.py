from __future__ import annotations

from sentinel_alpha.backtesting.engine import SimpleBacktestEngine


def test_simple_backtest_engine_generates_split_metrics() -> None:
    bars = [
        {"timestamp": "2024-01-01", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 1000},
        {"timestamp": "2024-01-02", "open": 101, "high": 103, "low": 100, "close": 102, "volume": 1100},
        {"timestamp": "2024-01-03", "open": 102, "high": 104, "low": 101, "close": 103, "volume": 1200},
        {"timestamp": "2024-01-04", "open": 103, "high": 104, "low": 99, "close": 100, "volume": 1300},
        {"timestamp": "2024-01-05", "open": 100, "high": 105, "low": 99, "close": 104, "volume": 1400},
        {"timestamp": "2024-01-06", "open": 104, "high": 106, "low": 103, "close": 105, "volume": 1500},
        {"timestamp": "2024-01-07", "open": 105, "high": 107, "low": 104, "close": 106, "volume": 1500},
        {"timestamp": "2024-01-08", "open": 106, "high": 108, "low": 105, "close": 107, "volume": 1500},
        {"timestamp": "2024-01-09", "open": 107, "high": 109, "low": 106, "close": 108, "volume": 1500},
        {"timestamp": "2024-01-10", "open": 108, "high": 110, "low": 107, "close": 109, "volume": 1500},
        {"timestamp": "2024-01-11", "open": 109, "high": 111, "low": 108, "close": 110, "volume": 1500},
        {"timestamp": "2024-01-12", "open": 110, "high": 112, "low": 109, "close": 111, "volume": 1500},
        {"timestamp": "2024-01-13", "open": 111, "high": 113, "low": 110, "close": 112, "volume": 1500},
        {"timestamp": "2024-01-14", "open": 112, "high": 114, "low": 111, "close": 113, "volume": 1500},
        {"timestamp": "2024-01-15", "open": 113, "high": 115, "low": 112, "close": 114, "volume": 1500},
        {"timestamp": "2024-01-16", "open": 114, "high": 116, "low": 113, "close": 115, "volume": 1500},
        {"timestamp": "2024-01-17", "open": 115, "high": 117, "low": 114, "close": 116, "volume": 1500},
        {"timestamp": "2024-01-18", "open": 116, "high": 118, "low": 115, "close": 117, "volume": 1500},
        {"timestamp": "2024-01-19", "open": 117, "high": 119, "low": 116, "close": 118, "volume": 1500},
        {"timestamp": "2024-01-20", "open": 118, "high": 120, "low": 117, "close": 119, "volume": 1500},
        {"timestamp": "2024-01-21", "open": 119, "high": 121, "low": 118, "close": 120, "volume": 1500},
    ]
    split_plan = {
        "train": {"start": "2024-01-01", "end": "2024-01-10"},
        "validation": {"start": "2024-01-11", "end": "2024-01-15"},
        "test": {"start": "2024-01-16", "end": "2024-01-21"},
        "walk_forward_windows": [
            {
                "window_id": "wf_1",
                "train_start": "2024-01-01",
                "train_end": "2024-01-10",
                "validation_start": "2024-01-16",
                "validation_end": "2024-01-18",
            }
        ],
    }
    engine = SimpleBacktestEngine()

    result = engine.evaluate(bars=bars, exposure=0.25, split_plan=split_plan)

    assert result is not None
    assert "train" in result
    assert "validation" in result
    assert "test" in result
    assert isinstance(result["walk_forward"], list)
    assert "gross_exposure_pct" in result["test"]
    assert "avg_daily_turnover_proxy_pct" in result["test"]
    assert result["coverage"]["symbol_count"] == 1
    assert result["coverage"]["total_bar_count"] == len(bars)
    assert result["coverage"]["walk_forward_window_count"] == 1


def test_simple_backtest_engine_supports_multi_asset_with_costs() -> None:
    bars = {
        "AAPL": [
            {"timestamp": "2024-01-01", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000},
            {"timestamp": "2024-01-02", "open": 100, "high": 103, "low": 99, "close": 102, "volume": 1000},
            {"timestamp": "2024-01-03", "open": 102, "high": 104, "low": 101, "close": 103, "volume": 1000},
            {"timestamp": "2024-01-04", "open": 103, "high": 105, "low": 102, "close": 104, "volume": 1000},
            {"timestamp": "2024-01-05", "open": 104, "high": 106, "low": 103, "close": 105, "volume": 1000},
            {"timestamp": "2024-01-06", "open": 105, "high": 107, "low": 104, "close": 106, "volume": 1000},
            {"timestamp": "2024-01-07", "open": 106, "high": 108, "low": 105, "close": 107, "volume": 1000},
            {"timestamp": "2024-01-08", "open": 107, "high": 109, "low": 106, "close": 108, "volume": 1000},
            {"timestamp": "2024-01-09", "open": 108, "high": 110, "low": 107, "close": 109, "volume": 1000},
            {"timestamp": "2024-01-10", "open": 109, "high": 111, "low": 108, "close": 110, "volume": 1000},
            {"timestamp": "2024-01-11", "open": 110, "high": 112, "low": 109, "close": 111, "volume": 1000},
            {"timestamp": "2024-01-12", "open": 111, "high": 113, "low": 110, "close": 112, "volume": 1000},
            {"timestamp": "2024-01-13", "open": 112, "high": 114, "low": 111, "close": 113, "volume": 1000},
            {"timestamp": "2024-01-14", "open": 113, "high": 115, "low": 112, "close": 114, "volume": 1000},
            {"timestamp": "2024-01-15", "open": 114, "high": 116, "low": 113, "close": 115, "volume": 1000},
            {"timestamp": "2024-01-16", "open": 115, "high": 117, "low": 114, "close": 116, "volume": 1000},
            {"timestamp": "2024-01-17", "open": 116, "high": 118, "low": 115, "close": 117, "volume": 1000},
            {"timestamp": "2024-01-18", "open": 117, "high": 119, "low": 116, "close": 118, "volume": 1000},
            {"timestamp": "2024-01-19", "open": 118, "high": 120, "low": 117, "close": 119, "volume": 1000},
            {"timestamp": "2024-01-20", "open": 119, "high": 121, "low": 118, "close": 120, "volume": 1000},
        ],
        "AMD": [
            {"timestamp": "2024-01-01", "open": 50, "high": 51, "low": 49, "close": 50, "volume": 1000},
            {"timestamp": "2024-01-02", "open": 50, "high": 52, "low": 49, "close": 51, "volume": 1000},
            {"timestamp": "2024-01-03", "open": 51, "high": 53, "low": 50, "close": 52, "volume": 1000},
            {"timestamp": "2024-01-04", "open": 52, "high": 54, "low": 51, "close": 53, "volume": 1000},
            {"timestamp": "2024-01-05", "open": 53, "high": 55, "low": 52, "close": 54, "volume": 1000},
            {"timestamp": "2024-01-06", "open": 54, "high": 56, "low": 53, "close": 55, "volume": 1000},
            {"timestamp": "2024-01-07", "open": 55, "high": 57, "low": 54, "close": 56, "volume": 1000},
            {"timestamp": "2024-01-08", "open": 56, "high": 58, "low": 55, "close": 57, "volume": 1000},
            {"timestamp": "2024-01-09", "open": 57, "high": 59, "low": 56, "close": 58, "volume": 1000},
            {"timestamp": "2024-01-10", "open": 58, "high": 60, "low": 57, "close": 59, "volume": 1000},
            {"timestamp": "2024-01-11", "open": 59, "high": 61, "low": 58, "close": 60, "volume": 1000},
            {"timestamp": "2024-01-12", "open": 60, "high": 62, "low": 59, "close": 61, "volume": 1000},
            {"timestamp": "2024-01-13", "open": 61, "high": 63, "low": 60, "close": 62, "volume": 1000},
            {"timestamp": "2024-01-14", "open": 62, "high": 64, "low": 61, "close": 63, "volume": 1000},
            {"timestamp": "2024-01-15", "open": 63, "high": 65, "low": 62, "close": 64, "volume": 1000},
            {"timestamp": "2024-01-16", "open": 64, "high": 66, "low": 63, "close": 65, "volume": 1000},
            {"timestamp": "2024-01-17", "open": 65, "high": 67, "low": 64, "close": 66, "volume": 1000},
            {"timestamp": "2024-01-18", "open": 66, "high": 68, "low": 65, "close": 67, "volume": 1000},
            {"timestamp": "2024-01-19", "open": 67, "high": 69, "low": 66, "close": 68, "volume": 1000},
            {"timestamp": "2024-01-20", "open": 68, "high": 70, "low": 67, "close": 69, "volume": 1000},
        ],
    }
    split_plan = {
        "train": {"start": "2024-01-01", "end": "2024-01-10"},
        "validation": {"start": "2024-01-11", "end": "2024-01-15"},
        "test": {"start": "2024-01-16", "end": "2024-01-20"},
        "walk_forward_windows": [],
    }
    engine = SimpleBacktestEngine()

    result = engine.evaluate(
        bars=bars,
        exposure={"AAPL": 0.15, "AMD": 0.1},
        split_plan=split_plan,
        fee_bps=5.0,
        slippage_bps=3.0,
    )

    assert result is not None
    assert result["test"]["expected_return_pct"] != 0
    assert result["test"]["active_symbol_count"] == 2
    assert result["test"]["avg_daily_turnover_proxy_pct"] >= 0
    assert result["coverage"]["symbol_count"] == 2
    assert result["coverage"]["split_bar_counts"]["test"]["symbol_count"] == 2


def test_simple_backtest_engine_builds_annual_breakdown() -> None:
    bars = []
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

    split_plan = {
        "train": {"start": "2023-01-03", "end": "2023-12-17"},
        "validation": {"start": "2024-01-03", "end": "2024-06-17"},
        "test": {"start": "2024-07-03", "end": "2024-12-17"},
        "walk_forward_windows": [],
    }

    engine = SimpleBacktestEngine()
    result = engine.evaluate(bars=bars, exposure=0.2, split_plan=split_plan)

    assert result is not None
    full_period = result["full_period"]
    annual = full_period["annual_breakdown"]
    assert len(annual) == 2
    assert annual[0]["year"] == 2023
    assert annual[1]["year"] == 2024
    assert "compounded_return_pct" in annual[0]
    assert "avg_loss_trade_pct" in annual[0]
    assert "avg_gain_trade_pct" in annual[1]
