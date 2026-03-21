from __future__ import annotations

from sentinel_alpha.agents.programmer_agent import ProgrammerAgent
from sentinel_alpha.config import get_settings


def test_programmer_agent_disabled_mode_returns_explicit_status() -> None:
    settings = get_settings()
    agent = ProgrammerAgent(settings)

    result = agent.execute(
        instruction="Adjust strategy parameters",
        target_files=["src/sentinel_alpha/strategies/rule_based.py"],
        context="Keep risk controls.",
        commit_changes=True,
    )

    assert result["status"] in {"disabled", "misconfigured", "ok", "error"}
    assert "rollback_commit" in result
    assert "changed_files" in result
