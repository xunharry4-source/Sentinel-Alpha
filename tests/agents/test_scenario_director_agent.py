from __future__ import annotations

from sentinel_alpha.agents.scenario_director import ScenarioDirectorAgent


def test_scenario_director_generates_default_campaign() -> None:
    campaign = ScenarioDirectorAgent().generate_default_campaign()

    assert len(campaign) == 6
    assert {item.playbook for item in campaign} == {
        "uptrend",
        "gap",
        "oscillation",
        "drawdown",
        "fake_reversal",
        "downtrend",
    }
