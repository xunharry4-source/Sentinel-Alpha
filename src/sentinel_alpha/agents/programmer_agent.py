from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable

from sentinel_alpha.config import AppSettings


class ProgrammerAgent:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.repo_path = Path(settings.programmer_agent_repo_path).resolve()
        self.allowed_paths = [self.repo_path / item for item in settings.programmer_agent_allowed_paths]

    def health_modules(self) -> list[dict[str, str]]:
        command_path = shutil.which(self.settings.programmer_agent_command)
        status = "ok" if self.settings.programmer_agent_enabled and command_path else "warning"
        detail = (
            f"Programmer Agent is enabled and using {command_path}."
            if self.settings.programmer_agent_enabled and command_path
            else "Programmer Agent is disabled or aider command is unavailable."
        )
        recommendation = (
            "No action required."
            if self.settings.programmer_agent_enabled and command_path
            else "Install aider and enable programmer_agent.enabled to allow controlled local code modification."
        )
        return [
            {
                "name": "programmer_agent",
                "status": status,
                "detail": detail,
                "recommendation": recommendation,
            },
            {
                "name": "aider_cli",
                "status": "ok" if command_path else "error",
                "detail": f"aider command resolved to {command_path}." if command_path else "aider command not found in PATH.",
                "recommendation": "No action required." if command_path else "Install aider or set programmer_agent.command to the correct executable.",
            },
        ]

    def execute(
        self,
        instruction: str,
        target_files: list[str],
        context: str | None = None,
        commit_changes: bool | None = None,
    ) -> dict:
        if not self.settings.programmer_agent_enabled:
            return {
                "status": "disabled",
                "failure_type": "disabled",
                "instruction": instruction,
                "target_files": target_files,
                "error": "Programmer Agent is disabled by configuration.",
                "diff": "",
                "commit_hash": None,
                "rollback_commit": self._git_head(),
                "changed_files": [],
            }
        command_path = shutil.which(self.settings.programmer_agent_command)
        if not command_path:
            return {
                "status": "misconfigured",
                "failure_type": "misconfigured",
                "instruction": instruction,
                "target_files": target_files,
                "error": "aider command not found.",
                "diff": "",
                "commit_hash": None,
                "rollback_commit": self._git_head(),
                "changed_files": [],
            }
        normalized_targets = self._validate_targets(target_files)
        self._ensure_target_files(normalized_targets)
        before_head = self._git_head()
        prompt = instruction.strip()
        if context:
            prompt = f"{prompt}\n\nContext:\n{context.strip()}"
        command = [
            command_path,
            *self.settings.programmer_agent_args,
            "--message",
            prompt,
            *normalized_targets,
        ]
        result = subprocess.run(
            command,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            timeout=self.settings.programmer_agent_timeout_seconds,
        )
        changed_files = self._changed_files()
        diff = self._git_diff(normalized_targets)
        should_commit = self.settings.programmer_agent_auto_commit if commit_changes is None else bool(commit_changes)
        commit_hash = None
        commit_error = None
        if should_commit and changed_files:
            commit_hash, commit_error = self._commit_changes(normalized_targets, instruction)
        after_head = self._git_head()
        status = "ok" if result.returncode == 0 else "error"
        failure_type = None
        if result.returncode != 0:
            failure_type = "execution_failure"
        elif commit_error:
            failure_type = "commit_failure"
        return {
            "status": status,
            "failure_type": failure_type,
            "instruction": instruction,
            "context": context or "",
            "target_files": normalized_targets,
            "stdout": result.stdout[-6000:],
            "stderr": result.stderr[-6000:],
            "returncode": result.returncode,
            "diff": diff,
            "changed_files": changed_files,
            "commit_hash": commit_hash,
            "commit_error": commit_error,
            "rollback_commit": before_head,
            "head_after_run": after_head,
        }

    def execute_with_retries(
        self,
        instruction: str,
        target_files: list[str],
        context: str | None = None,
        commit_changes: bool | None = None,
        validator: Callable[[list[str]], tuple[bool, str]] | None = None,
    ) -> dict:
        attempts: list[dict] = []
        retry_context = context or ""
        for attempt in range(1, max(1, self.settings.programmer_agent_retry_attempts) + 1):
            result = self.execute(
                instruction=instruction,
                target_files=target_files,
                context=retry_context,
                commit_changes=commit_changes,
            )
            result["attempt"] = attempt
            validation_ok = result.get("status") == "ok"
            validation_detail = "No validator configured."
            if validation_ok and validator is not None:
                validation_ok, validation_detail = validator(result.get("target_files", []))
                if not validation_ok and result.get("failure_type") is None:
                    lowered = validation_detail.lower()
                    if "py_compile" in lowered or "syntaxerror" in lowered or "indentationerror" in lowered:
                        result["failure_type"] = "compile_failure"
                    elif "pytest" in lowered or "assert" in lowered or "failed" in lowered:
                        result["failure_type"] = "test_failure"
                    else:
                        result["failure_type"] = "validation_failure"
            result["validation_ok"] = validation_ok
            result["validation_detail"] = validation_detail
            attempts.append(result)
            if validation_ok:
                final = dict(result)
                final["attempts"] = attempts
                final["status"] = "ok"
                return final
            retry_context = self._build_retry_context(instruction, retry_context, result, validation_detail)

        final = dict(attempts[-1]) if attempts else {
            "status": "error",
            "failure_type": "unknown_failure",
            "instruction": instruction,
            "target_files": target_files,
            "error": "Programmer Agent did not run.",
        }
        final["attempts"] = attempts
        final["status"] = "error"
        return final

    def _validate_targets(self, target_files: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in target_files:
            candidate = (self.repo_path / item).resolve()
            if not any(self._is_within_allowed_scope(candidate, allowed.resolve()) for allowed in self.allowed_paths):
                raise ValueError(f"Target file is outside allowed programmer agent scope: {item}")
            if candidate.exists() and candidate.is_dir():
                raise ValueError(f"Target path must be a file, not a directory: {item}")
            normalized.append(str(candidate.relative_to(self.repo_path)))
        return normalized

    def _ensure_target_files(self, target_files: list[str]) -> None:
        for item in target_files:
            candidate = self.repo_path / item
            candidate.parent.mkdir(parents=True, exist_ok=True)
            if not candidate.exists():
                candidate.touch()

    def _is_within_allowed_scope(self, candidate: Path, allowed_root: Path) -> bool:
        try:
            candidate.relative_to(allowed_root)
            return True
        except ValueError:
            return False

    def _git_head(self) -> str | None:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() if result.returncode == 0 else None

    def _git_diff(self, target_files: list[str]) -> str:
        result = subprocess.run(
            ["git", "diff", "--", *target_files],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
        return result.stdout[-12000:]

    def _changed_files(self) -> list[str]:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return []
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return [line[3:] if len(line) > 3 else line for line in lines]

    def _commit_changes(self, target_files: list[str], instruction: str) -> tuple[str | None, str | None]:
        add_result = subprocess.run(
            ["git", "add", "--", *target_files],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
        if add_result.returncode != 0:
            return None, add_result.stderr.strip() or "git add failed"
        commit_message = f"Programmer Agent: {instruction[:72]}"
        commit_result = subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
        if commit_result.returncode != 0:
            return None, commit_result.stderr.strip() or commit_result.stdout.strip() or "git commit failed"
        return self._git_head(), None

    def _build_retry_context(
        self,
        instruction: str,
        current_context: str,
        result: dict,
        validation_detail: str,
    ) -> str:
        failure_type = str(result.get("failure_type") or "validation_failure")
        parts = [current_context.strip()] if current_context.strip() else []
        parts.append("Retry Requirements:")
        parts.append(f"- Original instruction: {instruction}")
        parts.append(f"- Failure type: {failure_type}")
        parts.append(f"- Last return code: {result.get('returncode')}")
        if result.get("stderr"):
            parts.append(f"- stderr: {str(result.get('stderr'))[-1200:]}")
        if result.get("stdout"):
            parts.append(f"- stdout: {str(result.get('stdout'))[-1200:]}")
        if validation_detail:
            parts.append(f"- validator: {validation_detail}")
        parts.append("- Preserve existing workflow, logging, monitoring, and approval contracts.")
        if failure_type == "compile_failure":
            parts.append("- Focus on syntax, imports, signatures, and Python correctness first.")
            parts.append("- Do not refactor unrelated logic until the code compiles.")
        elif failure_type == "test_failure":
            parts.append("- Focus on behavioral correctness and test expectations.")
            parts.append("- Do not change tests unless the implementation is clearly wrong and test assumptions are invalid.")
        elif failure_type == "commit_failure":
            parts.append("- Focus on git-safe file state, staged content, and commitability.")
        elif failure_type == "execution_failure":
            parts.append("- Focus on tool execution failure, malformed prompt outcome, or broken generated edits.")
        else:
            parts.append("- Fix the failure directly and keep the patch minimal.")
        return "\n".join(parts)
