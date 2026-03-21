from __future__ import annotations


class RiskGuardianAgent:
    """Blocks approval when hard strategy checks fail."""

    def approve(self, strategy_checks: list[dict]) -> tuple[bool, str]:
        failed = [check for check in strategy_checks if check.get("status") == "fail"]
        if failed:
            return False, "Strategy checks failed. Re-iterate the strategy before approval."
        return True, "Strategy approval passed."
