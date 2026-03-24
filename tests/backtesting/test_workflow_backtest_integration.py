from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from sentinel_alpha.api.workflow_service import WorkflowService
from sentinel_alpha.config import get_settings
from sentinel_alpha.infra.free_market_data import FreeMarketDataService


def test_workflow_uses_local_history_backtest_when_available(tmp_path: Path) -> None:
    history_path = tmp_path / "AAPL_1d.csv"
    rows = ["timestamp,open,high,low,close,volume"]
    price = 100.0
    current = date(2024, 1, 1)
    for day in range(1, 90):
        close = price + 1.0
        rows.append(f"{current.isoformat()},{price},{price + 2},{price - 1},{close},{1000 + day}")
        price = close
        current += timedelta(days=1)
    history_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    quote_path = tmp_path / "AAPL_quote.json"
    quote_path.write_text(json.dumps({"price": price, "timestamp": "2024-03-31T00:00:00Z"}), encoding="utf-8")

    settings = get_settings()
    provider_configs = dict(settings.market_data_provider_configs)
    provider_configs["local_file"] = {
        "enabled": True,
        "api_key_envs": [],
        "base_path": str(tmp_path),
        "quote_filename": "{symbol}_quote.json",
        "history_filename": "{symbol}_{interval}.csv",
    }
    patched = settings.__class__(**{**settings.__dict__, "market_data_provider_configs": provider_configs})

    service = WorkflowService()
    service.settings = patched
    service.market_data = FreeMarketDataService(patched)
    service.backtest_engine = service.backtest_engine.__class__()

    dataset_plan = {
        "train": {"start": "2024-01-02", "end": "2024-01-31"},
        "validation": {"start": "2024-02-01", "end": "2024-02-20"},
        "test": {"start": "2024-02-21", "end": "2024-03-20"},
        "walk_forward_windows": [
            {
                "window_id": "wf_1",
                "train_start": "2024-01-02",
                "train_end": "2024-01-31",
                "validation_start": "2024-03-01",
                "validation_end": "2024-03-10",
            }
        ],
    }
    candidate = {
        "signals": [{"symbol": "AAPL", "action": "buy", "conviction": 0.8}],
        "parameters": {"max_position_pct": 0.2, "hard_stop_loss_pct": 0.06},
    }

    evaluation = service._evaluate_strategy_candidate(
        candidate=candidate,
        objective_metric="return",
        targets={
            "target_return_pct": 18.0,
            "target_win_rate_pct": 58.0,
            "target_drawdown_pct": 12.0,
            "target_max_loss_pct": 6.0,
            "objective_metric": "return",
        },
        variant_index=0,
        dataset_plan=dataset_plan,
    )

    assert evaluation["evaluation_source"] == "local_history_backtest"
    assert "dataset_evaluation" in evaluation
    assert evaluation["coverage_summary"]["symbol_count"] == 1
    assert evaluation["coverage_summary"]["total_bar_count"] > 0
    assert evaluation["coverage_summary"]["walk_forward_window_count"] == 1
    assert "gross_exposure_pct" in evaluation["dataset_evaluation"]["test"]
    assert "avg_daily_turnover_proxy_pct" in evaluation["dataset_evaluation"]["test"]
