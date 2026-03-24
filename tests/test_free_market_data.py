from __future__ import annotations

import json
from pathlib import Path

from sentinel_alpha.config import get_settings
from sentinel_alpha.infra.free_market_data import FreeMarketDataService


def test_local_file_market_data_provider_reads_quote_and_history(tmp_path: Path) -> None:
    quote_path = tmp_path / "AAPL_quote.json"
    history_path = tmp_path / "AAPL_1d.csv"
    quote_path.write_text(
        json.dumps(
            {
                "price": 188.5,
                "open": 186.0,
                "high": 189.2,
                "low": 185.7,
                "previous_close": 184.8,
                "timestamp": "2026-03-21T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    history_path.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2026-03-20,180,185,179,184,1000\n"
        "2026-03-21,184,189,183,188,1200\n",
        encoding="utf-8",
    )

    settings = get_settings()
    provider_configs = dict(settings.market_data_provider_configs)
    provider_configs["local_file"] = {
        "enabled": True,
        "api_key_envs": [],
        "base_path": str(tmp_path),
        "quote_filename": "{symbol}_quote.json",
        "history_filename": "{symbol}_{interval}.csv",
    }
    test_settings = settings.__class__(**{**settings.__dict__, "market_data_provider_configs": provider_configs})
    service = FreeMarketDataService(test_settings)

    quote = service.fetch_quote("AAPL", provider="local_file")
    history = service.fetch_history("AAPL", interval="1d", provider="local_file")

    assert quote["provider"] == "local_file"
    assert quote["symbol"] == "AAPL"
    assert float(quote["price"]) == 188.5
    assert history["provider"] == "local_file"
    assert len(history["bars"]) == 2
    assert history["bars"][-1]["close"] == "188"
