from __future__ import annotations

from sentinel_alpha.api.workflow_service import WorkflowService


def test_workflow_service_system_health_exposes_all_known_agents() -> None:
    payload = WorkflowService().system_health()
    agent_names = {item["agent"] for item in payload["agents"]}

    assert "scenario_director" in agent_names
    assert "noise_agent" in agent_names
    assert "behavioral_profiler" in agent_names
    assert "intelligence_agent" in agent_names
    assert "strategy_evolver" in agent_names
    assert "portfolio_manager" in agent_names
    assert "intent_aligner" in agent_names
    assert "risk_guardian" in agent_names
    assert "user_monitor" in agent_names
    assert "strategy_monitor" in agent_names
    assert "market_asset_monitor" in agent_names
    assert "strategy_integrity_checker" in agent_names
    assert "strategy_stress_checker" in agent_names
    assert "programmer_agent" in agent_names
