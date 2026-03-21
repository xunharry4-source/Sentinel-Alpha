from __future__ import annotations


class UserMonitorAgent:
    """Tracks user behavior drift versus the behavioral profile."""

    def generate_signal(self, behavioral_report: dict | None) -> dict:
        behavior = behavioral_report or {}
        elevated = float(behavior.get("noise_sensitivity", 0.0) or 0.0) > 0.6
        return {
            "monitor_type": "user",
            "severity": "warning" if elevated else "info",
            "title": "User Monitor",
            "detail": "Noise sensitivity remains elevated." if elevated else "User behavior is within the profiled baseline.",
        }
