from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

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


def test_programmer_agent_validates_allowed_and_disallowed_targets(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    allowed = repo / "src" / "sentinel_alpha" / "infra" / "generated_sources"
    blocked = repo / "outside"
    allowed.mkdir(parents=True)
    blocked.mkdir(parents=True)
    allowed_file = allowed / "example_source.py"
    blocked_file = blocked / "not_allowed.py"
    allowed_file.write_text("VALUE = 1\n", encoding="utf-8")
    blocked_file.write_text("VALUE = 2\n", encoding="utf-8")

    settings = get_settings()
    patched = settings.__class__(
        **{
            **settings.__dict__,
            "programmer_agent_repo_path": str(repo),
            "programmer_agent_allowed_paths": ["src/sentinel_alpha/infra/generated_sources", "tests"],
        }
    )
    agent = ProgrammerAgent(patched)

    normalized = agent._validate_targets(["src/sentinel_alpha/infra/generated_sources/example_source.py"])
    assert normalized == ["src/sentinel_alpha/infra/generated_sources/example_source.py"]

    missing_normalized = agent._validate_targets(["src/sentinel_alpha/infra/generated_sources/missing.py"])
    assert missing_normalized == ["src/sentinel_alpha/infra/generated_sources/missing.py"]

    with pytest.raises(ValueError, match="outside allowed programmer agent scope"):
        agent._validate_targets(["outside/not_allowed.py"])


def test_programmer_agent_retries_until_validator_passes(monkeypatch) -> None:
    settings = get_settings()
    patched = settings.__class__(**{**settings.__dict__, "programmer_agent_retry_attempts": 3})
    agent = ProgrammerAgent(patched)
    attempts = {"count": 0}

    def fake_execute(*, instruction, target_files, context=None, commit_changes=None):
        attempts["count"] += 1
        return {
            "status": "ok",
            "instruction": instruction,
            "target_files": target_files,
            "stdout": "",
            "stderr": "syntax error" if attempts["count"] == 1 else "",
            "returncode": 0,
            "diff": "",
            "changed_files": target_files,
            "commit_hash": None,
            "commit_error": None,
            "rollback_commit": "abc",
            "head_after_run": "def",
        }

    monkeypatch.setattr(agent, "execute", fake_execute)

    result = agent.execute_with_retries(
        instruction="fix code",
        target_files=["tests/example.py"],
        validator=lambda files: (attempts["count"] >= 2, "still failing" if attempts["count"] < 2 else "ok"),
    )

    assert result["status"] == "ok"
    assert attempts["count"] == 2
    assert len(result["attempts"]) == 2
    assert result["attempts"][0]["failure_type"] == "validation_failure"
    assert result["failure_summary"]["attempt_count"] == 2
    assert result["failure_summary"]["dominant_failure_type"] in {"validation_failure", "success"}
    assert result["repair_plan"]["priority"] in {"P0", "P1", "P2"}
    assert result["stop_reason"] == "success"
    assert result["retry_exhausted"] is False
    assert result["progress_status"] == "improving"
    assert result["acceptance_summary"]["acceptance_status"] == "accepted"
    assert result["acceptance_summary"]["should_promote"] is True
    assert result["rollback_summary"]["rollback_status"] == "hold_current_baseline"
    assert result["rollback_summary"]["rollback_ready"] is True
    assert result["promotion_summary"]["promotion_status"] == "promote_candidate"
    assert result["promotion_summary"]["should_promote"] is True
    assert result["stability_summary"]["stability_status"] == "stable"


def test_programmer_agent_classifies_compile_failure(monkeypatch) -> None:
    settings = get_settings()
    patched = settings.__class__(**{**settings.__dict__, "programmer_agent_retry_attempts": 1})
    agent = ProgrammerAgent(patched)

    def fake_execute(*, instruction, target_files, context=None, commit_changes=None):
        return {
            "status": "ok",
            "instruction": instruction,
            "target_files": target_files,
            "stdout": "",
            "stderr": "",
            "returncode": 0,
            "diff": "",
            "changed_files": target_files,
            "commit_hash": None,
            "commit_error": None,
            "rollback_commit": "abc",
            "head_after_run": "def",
            "failure_type": None,
        }

    monkeypatch.setattr(agent, "execute", fake_execute)

    result = agent.execute_with_retries(
        instruction="fix code",
        target_files=["tests/example.py"],
        validator=lambda files: (False, "py_compile failed: SyntaxError"),
    )

    assert result["status"] == "error"
    assert result["attempts"][0]["failure_type"] == "compile_failure"
    assert result["failure_summary"]["dominant_failure_type"] == "compile_failure"
    assert result["repair_plan"]["dominant_failure_type"] == "compile_failure"
    assert result["repair_plan"]["priority"] == "P0"
    assert result["stop_reason"] == "retry_exhausted"
    assert result["retry_exhausted"] is True
    assert result["progress_status"] in {"unknown", "stalled"}
    assert result["acceptance_summary"]["acceptance_status"] == "rejected"
    assert result["acceptance_summary"]["rollback_recommended"] is True
    assert result["rollback_summary"]["rollback_status"] == "rollback_preferred"
    assert result["promotion_summary"]["promotion_status"] == "reject_candidate"
    assert result["promotion_summary"]["promotion_gate"] == "rollback_first"
    assert result["stability_summary"]["stability_status"] in {"caution", "fragile"}


def test_programmer_agent_retry_context_includes_repair_plan(monkeypatch) -> None:
    settings = get_settings()
    patched = settings.__class__(**{**settings.__dict__, "programmer_agent_retry_attempts": 2})
    agent = ProgrammerAgent(patched)
    seen_contexts: list[str | None] = []
    attempts = {"count": 0}

    def fake_execute(*, instruction, target_files, context=None, commit_changes=None):
        attempts["count"] += 1
        seen_contexts.append(context)
        return {
            "status": "ok",
            "instruction": instruction,
            "target_files": target_files,
            "stdout": "",
            "stderr": "",
            "returncode": 0,
            "diff": "",
            "changed_files": target_files,
            "commit_hash": None,
            "commit_error": None,
            "rollback_commit": "abc",
            "head_after_run": "def",
            "failure_type": None,
        }

    monkeypatch.setattr(agent, "execute", fake_execute)

    result = agent.execute_with_retries(
        instruction="fix code",
        target_files=["tests/example.py"],
        validator=lambda files: (attempts["count"] >= 2, "py_compile failed: SyntaxError" if attempts["count"] < 2 else "ok"),
    )

    assert result["status"] == "ok"
    assert len(seen_contexts) == 2
    assert "Repair priority: P0" in (seen_contexts[1] or "")
    assert "Repair action:" in (seen_contexts[1] or "")


def test_programmer_agent_stops_when_no_progress_detected(monkeypatch) -> None:
    settings = get_settings()
    patched = settings.__class__(**{**settings.__dict__, "programmer_agent_retry_attempts": 3})
    agent = ProgrammerAgent(patched)

    def fake_execute(*, instruction, target_files, context=None, commit_changes=None):
        return {
            "status": "ok",
            "instruction": instruction,
            "target_files": target_files,
            "stdout": "",
            "stderr": "",
            "returncode": 0,
            "diff": "",
            "changed_files": target_files,
            "commit_hash": None,
            "commit_error": None,
            "rollback_commit": "abc",
            "head_after_run": "def",
            "failure_type": None,
        }

    monkeypatch.setattr(agent, "execute", fake_execute)

    result = agent.execute_with_retries(
        instruction="fix code",
        target_files=["tests/example.py"],
        validator=lambda files: (False, "pytest failed: same failure"),
    )

    assert result["status"] == "error"
    assert result["stop_reason"] == "no_progress_detected"
    assert result["no_progress_detected"] is True
    assert result["retry_exhausted"] is False
    assert len(result["attempts"]) == 2
    assert result["progress_status"] == "stalled"
    assert result["acceptance_summary"]["acceptance_status"] == "rejected"
    assert result["acceptance_summary"]["acceptance_gate"] == "rollback_or_rethink"
    assert result["rollback_summary"]["rollback_status"] == "rollback_preferred"
    assert result["promotion_summary"]["promotion_status"] == "reject_candidate"
    assert result["stability_summary"]["stability_status"] == "fragile"


def test_programmer_agent_marks_regressing_when_failure_severity_worsens(monkeypatch) -> None:
    settings = get_settings()
    patched = settings.__class__(**{**settings.__dict__, "programmer_agent_retry_attempts": 2})
    agent = ProgrammerAgent(patched)
    attempts = {"count": 0}

    def fake_execute(*, instruction, target_files, context=None, commit_changes=None):
        attempts["count"] += 1
        return {
            "status": "ok",
            "instruction": instruction,
            "target_files": target_files,
            "stdout": "",
            "stderr": "",
            "returncode": 0,
            "diff": "",
            "changed_files": target_files,
            "commit_hash": None,
            "commit_error": None,
            "rollback_commit": "abc",
            "head_after_run": "def",
            "failure_type": None,
        }

    monkeypatch.setattr(agent, "execute", fake_execute)

    def validator(_files):
        return (False, "validator mismatch" if attempts["count"] == 1 else "py_compile failed: SyntaxError")

    result = agent.execute_with_retries(
        instruction="fix code",
        target_files=["tests/example.py"],
        validator=validator,
    )

    assert result["status"] == "error"
    assert result["progress_status"] == "regressing"


def test_programmer_validator_maps_pytest_targets(monkeypatch) -> None:
    from sentinel_alpha.api.workflow_service import WorkflowService

    service = WorkflowService()
    calls = []

    def fake_run(cmd, cwd=None, capture_output=None, text=None):
        calls.append(cmd)
        class Result:
            returncode = 0
            stdout = ""
            stderr = ""
        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)

    ok, detail = service._validate_programmer_changes(["src/sentinel_alpha/agents/programmer_agent.py"])

    assert ok is True
    assert any(cmd[:3] == ["python", "-m", "py_compile"] for cmd in calls)
    assert any(cmd[:3] == ["python", "-m", "pytest"] for cmd in calls)
    assert "pytest passed" in detail


def test_programmer_contract_check_rejects_empty_python_target(tmp_path: Path) -> None:
    from sentinel_alpha.api.workflow_service import WorkflowService

    repo = tmp_path / "repo"
    target = repo / "src" / "sentinel_alpha" / "infra" / "generated_sources" / "empty_module.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("", encoding="utf-8")

    service = WorkflowService()
    service.settings = service.settings.__class__(**{**service.settings.__dict__, "programmer_agent_repo_path": str(repo)})

    ok, detail = service._validate_programmer_python_contracts(["src/sentinel_alpha/infra/generated_sources/empty_module.py"])

    assert ok is False
    assert "empty python target" in detail
