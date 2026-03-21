from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel_alpha.research.scenario_generator import ScenarioGenerator


def main() -> None:
    generator = ScenarioGenerator(seed=11)
    scenarios = [
        generator.generate("uptrend", cohort="pressure"),
        generator.generate("gap", cohort="pressure"),
        generator.generate("oscillation", cohort="pressure"),
        generator.generate("drawdown", cohort="pressure"),
        generator.generate("fake_reversal", cohort="pressure"),
        generator.generate("downtrend", cohort="pressure"),
    ]
    print(json.dumps([asdict(scenario) for scenario in scenarios], indent=2, default=str))


if __name__ == "__main__":
    main()
