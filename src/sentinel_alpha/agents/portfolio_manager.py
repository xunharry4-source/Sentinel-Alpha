from __future__ import annotations


class PortfolioManagerAgent:
    """Owns deployment mode transitions for approved strategies."""

    def set_execution_mode(self, execution_mode: str) -> dict[str, str]:
        phase = "autonomous_active" if execution_mode == "autonomous" else "advice_only_active"
        return {"execution_mode": execution_mode, "phase": phase}
