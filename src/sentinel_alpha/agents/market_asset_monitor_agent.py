from __future__ import annotations


class MarketAssetMonitorAgent:
    """Summarizes which assets are currently being watched by the workflow."""

    def generate_signal(self, strategy_package: dict | None, trade_universe: dict | None) -> dict:
        strategy = strategy_package or {}
        universe = strategy.get("selected_universe") or (trade_universe or {}).get("expanded", [])
        return {
            "monitor_type": "market",
            "severity": "info",
            "title": "Market and Asset Monitor",
            "detail": f"Watching universe: {', '.join(universe) or 'none'}.",
        }
