from __future__ import annotations


class StrategyMonitorAgent:
    """Monitors drift between the active strategy and the user's profile."""

    def generate_signal(self, strategy_package: dict | None) -> dict:
        strategy = strategy_package or {}
        compatibility = float(strategy.get("behavioral_compatibility", 1.0) or 1.0)
        drifting = compatibility < 0.7
        return {
            "monitor_type": "strategy",
            "severity": "warning" if drifting else "info",
            "title": "Strategy Monitor",
            "detail": "Behavioral compatibility is drifting down." if drifting else "Strategy remains aligned with the current profile.",
        }
