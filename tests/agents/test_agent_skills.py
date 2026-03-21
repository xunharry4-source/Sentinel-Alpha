from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_agent_skill_files_exist() -> None:
    expected = [
        "skills/scenario-director-agent/SKILL.md",
        "skills/noise-agent/SKILL.md",
        "skills/behavioral-profiler-agent/SKILL.md",
        "skills/intelligence-agent/SKILL.md",
        "skills/strategy-evolver-agent/SKILL.md",
        "skills/portfolio-manager-agent/SKILL.md",
        "skills/intent-aligner-agent/SKILL.md",
        "skills/risk-guardian-agent/SKILL.md",
        "skills/user-monitor-agent/SKILL.md",
        "skills/strategy-monitor-agent/SKILL.md",
        "skills/market-asset-monitor-agent/SKILL.md",
        "skills/strategy-integrity-checker-agent/SKILL.md",
        "skills/strategy-stress-checker-agent/SKILL.md",
        "skills/programmer-agent/SKILL.md",
        "skills/data-source-expansion-agent/SKILL.md",
        "skills/trading-terminal-integration-agent/SKILL.md",
    ]

    missing = [path for path in expected if not (REPO_ROOT / path).exists()]
    assert not missing, f"Missing agent skill files: {missing}"
