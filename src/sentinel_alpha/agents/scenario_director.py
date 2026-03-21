from __future__ import annotations

from sentinel_alpha.research.scenario_generator import ScenarioGenerator


class ScenarioDirectorAgent:
    """Coordinates the canonical behavioral stress scenario set."""

    def __init__(self, generator: ScenarioGenerator | None = None) -> None:
        self.generator = generator or ScenarioGenerator(seed=11)

    def generate_default_campaign(self) -> list:
        playbooks = [
            "uptrend",
            "gap",
            "oscillation",
            "drawdown",
            "fake_reversal",
            "downtrend",
        ]
        return [self.generator.generate(playbook, cohort="pressure") for playbook in playbooks]
