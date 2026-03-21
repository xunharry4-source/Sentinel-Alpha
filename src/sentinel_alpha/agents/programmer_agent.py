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
        max_attempts = max(1, self.settings.programmer_agent_retry_attempts)
        for attempt in range(1, max_attempts + 1):
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
                final["failure_summary"] = self._build_failure_summary(attempts)
                final["repair_plan"] = self._build_repair_plan(attempts, final["failure_summary"])
                final["progress_status"] = final["failure_summary"].get("progress_status")
                final["progress_note"] = final["failure_summary"].get("progress_note")
                final["stop_reason"] = "success"
                final["retry_exhausted"] = False
                final["no_progress_detected"] = False
                final["stable_success_required"] = True
                final["acceptance_summary"] = self._build_acceptance_summary(final)
                final["rollback_summary"] = self._build_rollback_summary(final)
                final["promotion_summary"] = self._build_promotion_summary(final)
                final["stability_summary"] = self._build_stability_summary(final)
                return final
            if self._detect_no_progress(attempts):
                final = dict(result)
                final["attempts"] = attempts
                final["status"] = "error"
                final["failure_summary"] = self._build_failure_summary(attempts)
                final["repair_plan"] = self._build_repair_plan(attempts, final["failure_summary"])
                final["progress_status"] = final["failure_summary"].get("progress_status")
                final["progress_note"] = final["failure_summary"].get("progress_note")
                final["stop_reason"] = "no_progress_detected"
                final["retry_exhausted"] = False
                final["no_progress_detected"] = True
                final["stable_success_required"] = True
                final["acceptance_summary"] = self._build_acceptance_summary(final)
                final["rollback_summary"] = self._build_rollback_summary(final)
                final["promotion_summary"] = self._build_promotion_summary(final)
                final["stability_summary"] = self._build_stability_summary(final)
                return final
            current_summary = self._build_failure_summary(attempts)
            current_plan = self._build_repair_plan(attempts, current_summary)
            retry_context = self._build_retry_context(instruction, retry_context, result, validation_detail, current_plan)

        final = dict(attempts[-1]) if attempts else {
            "status": "error",
            "failure_type": "unknown_failure",
            "instruction": instruction,
            "target_files": target_files,
            "error": "Programmer Agent did not run.",
        }
        final["attempts"] = attempts
        final["status"] = "error"
        final["failure_summary"] = self._build_failure_summary(attempts)
        final["repair_plan"] = self._build_repair_plan(attempts, final["failure_summary"])
        final["progress_status"] = final["failure_summary"].get("progress_status")
        final["progress_note"] = final["failure_summary"].get("progress_note")
        final["stop_reason"] = "retry_exhausted"
        final["retry_exhausted"] = True
        final["no_progress_detected"] = self._detect_no_progress(attempts)
        final["stable_success_required"] = True
        final["acceptance_summary"] = self._build_acceptance_summary(final)
        final["rollback_summary"] = self._build_rollback_summary(final)
        final["promotion_summary"] = self._build_promotion_summary(final)
        final["stability_summary"] = self._build_stability_summary(final)
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
        repair_plan: dict | None = None,
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
        if repair_plan:
            parts.append(f"- Repair priority: {repair_plan.get('priority', 'P1')}")
            parts.append(f"- Dominant failure type: {repair_plan.get('dominant_failure_type', failure_type)}")
            for action in repair_plan.get("actions", []):
                parts.append(f"- Repair action: {action}")
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

    def _build_failure_summary(self, attempts: list[dict]) -> dict:
        counts: dict[str, int] = {}
        ordered_types: list[str] = []
        for item in attempts:
            failure_type = str(item.get("failure_type") or ("success" if item.get("status") == "ok" else "unknown"))
            counts[failure_type] = counts.get(failure_type, 0) + 1
            ordered_types.append(failure_type)
        latest = attempts[-1] if attempts else {}
        dominant_failure_type = max(counts.items(), key=lambda pair: pair[1])[0] if counts else "unknown"
        progress = self._assess_progress(attempts)
        return {
            "attempt_count": len(attempts),
            "ordered_failure_types": ordered_types,
            "failure_type_counts": counts,
            "dominant_failure_type": dominant_failure_type,
            "latest_failure_type": latest.get("failure_type") or ("success" if latest.get("status") == "ok" else "unknown"),
            "latest_validation_detail": latest.get("validation_detail") or latest.get("error") or latest.get("stderr") or "",
            "stable_success": bool(attempts and attempts[-1].get("status") == "ok"),
            "no_progress_detected": self._detect_no_progress(attempts),
            "progress_status": progress["status"],
            "progress_note": progress["note"],
        }

    def _build_repair_plan(self, attempts: list[dict], failure_summary: dict) -> dict:
        dominant = str(failure_summary.get("dominant_failure_type") or "unknown")
        latest_detail = str(failure_summary.get("latest_validation_detail") or "").strip()
        priorities: list[str] = []
        actions: list[str] = []
        if dominant == "compile_failure":
            priorities.append("P0")
            actions.extend(
                [
                    "修正语法、导入、签名与返回结构，先确保代码可编译。",
                    "避免继续扩大修改面，优先最小补丁通过 py_compile。",
                ]
            )
        elif dominant == "test_failure":
            priorities.append("P0")
            actions.extend(
                [
                    "优先修复行为与测试预期不一致的问题。",
                    "先看断言失败点，缩小改动范围，不要先动无关逻辑。",
                ]
            )
        elif dominant == "validation_failure":
            priorities.append("P1")
            actions.extend(
                [
                    "优先修复 validator 暴露出的契约或结构问题。",
                    "检查输出字段、目标文件、版本命名和返回格式是否符合平台契约。",
                ]
            )
        elif dominant == "commit_failure":
            priorities.append("P1")
            actions.extend(
                [
                    "检查 git 状态、提交消息、暂存内容和目标文件是否可提交。",
                    "优先保证变更集最小且可提交，再继续下一轮修改。",
                ]
            )
        elif dominant == "execution_failure":
            priorities.append("P1")
            actions.extend(
                [
                    "检查执行工具返回错误、生成结果是否畸形、上下文是否导致错误修改。",
                    "必要时缩短指令并减少目标文件数量。",
                ]
            )
        elif dominant == "success":
            priorities.append("P2")
            actions.append("当前最近一次已成功，可将该结果作为稳定修复基线。")
        else:
            priorities.append("P1")
            actions.append("当前失败类型不明确，先检查最近一次 stderr 和 validator 输出。")
        if latest_detail:
            actions.append(f"最近失败细节: {latest_detail[:240]}")
        return {
            "dominant_failure_type": dominant,
            "priority": priorities[0] if priorities else "P1",
            "actions": actions,
        }

    def _detect_no_progress(self, attempts: list[dict]) -> bool:
        if len(attempts) < 2:
            return False
        recent = attempts[-2:]
        failure_types = [
            str(item.get("failure_type") or ("success" if item.get("status") == "ok" else "unknown"))
            for item in recent
        ]
        details = [str(item.get("validation_detail") or item.get("error") or "").strip() for item in recent]
        if "success" in failure_types:
            return False
        return len(set(failure_types)) == 1 and len(set(details)) == 1

    def _assess_progress(self, attempts: list[dict]) -> dict:
        if not attempts:
            return {"status": "unknown", "note": "No attempts were recorded."}
        if len(attempts) == 1:
            latest_type = str(attempts[-1].get("failure_type") or ("success" if attempts[-1].get("status") == "ok" else "unknown"))
            if latest_type == "success":
                return {"status": "improving", "note": "The first attempt already succeeded."}
            return {"status": "unknown", "note": "Only one attempt is available, so progress cannot be judged yet."}
        previous = attempts[-2]
        latest = attempts[-1]
        previous_type = str(previous.get("failure_type") or ("success" if previous.get("status") == "ok" else "unknown"))
        latest_type = str(latest.get("failure_type") or ("success" if latest.get("status") == "ok" else "unknown"))
        previous_detail = str(previous.get("validation_detail") or previous.get("error") or "").strip()
        latest_detail = str(latest.get("validation_detail") or latest.get("error") or "").strip()
        severity = {
            "success": 0,
            "validation_failure": 1,
            "commit_failure": 1,
            "execution_failure": 2,
            "test_failure": 2,
            "compile_failure": 3,
            "unknown": 2,
        }
        if latest_type == "success":
            return {"status": "improving", "note": "The latest attempt passed validation."}
        if self._detect_no_progress(attempts):
            return {"status": "stalled", "note": "Recent attempts are failing in the same way with no visible change."}
        latest_severity = severity.get(latest_type, 2)
        previous_severity = severity.get(previous_type, 2)
        if latest_severity < previous_severity:
            return {"status": "improving", "note": "The latest failure is weaker than the previous one."}
        if latest_severity > previous_severity:
            return {"status": "regressing", "note": "The latest failure is more severe than the previous one."}
        if latest_type == previous_type and latest_detail != previous_detail:
            return {"status": "improving", "note": "The failure type is unchanged, but the validator detail moved, suggesting partial progress."}
        return {"status": "stalled", "note": "Progress is limited and the latest failure is not clearly better than the previous one."}

    def _build_acceptance_summary(self, result: dict) -> dict:
        attempts = result.get("attempts") or []
        failure_summary = result.get("failure_summary") or self._build_failure_summary(attempts)
        progress_status = str(result.get("progress_status") or failure_summary.get("progress_status") or "unknown")
        stop_reason = str(result.get("stop_reason") or "unknown")
        latest_attempt = attempts[-1] if attempts else result
        rollback_target = result.get("rollback_commit") or latest_attempt.get("rollback_commit")
        commit_hash = result.get("commit_hash") or latest_attempt.get("commit_hash")
        validation_ok = bool(result.get("status") == "ok" and latest_attempt.get("validation_ok", True))
        changed_files = latest_attempt.get("changed_files") or result.get("changed_files") or []
        if validation_ok and stop_reason == "success":
            return {
                "acceptance_status": "accepted",
                "acceptance_gate": "promote",
                "note": "Latest patch passed the active validation gate and can be used as the current repair baseline.",
                "rollback_recommended": False,
                "rollback_target": rollback_target,
                "requires_human_review": False,
                "should_promote": True,
                "changed_file_count": len(changed_files),
                "commit_hash": commit_hash,
            }
        if stop_reason == "no_progress_detected":
            return {
                "acceptance_status": "rejected",
                "acceptance_gate": "rollback_or_rethink",
                "note": "Recent attempts are stalled. Prefer rollback or a materially different repair route before continuing.",
                "rollback_recommended": bool(rollback_target),
                "rollback_target": rollback_target,
                "requires_human_review": True,
                "should_promote": False,
                "changed_file_count": len(changed_files),
                "commit_hash": commit_hash,
            }
        if stop_reason == "retry_exhausted":
            return {
                "acceptance_status": "rejected",
                "acceptance_gate": "do_not_promote",
                "note": "Retry budget was exhausted before a stable validated fix was found.",
                "rollback_recommended": bool(rollback_target and changed_files),
                "rollback_target": rollback_target,
                "requires_human_review": True,
                "should_promote": False,
                "changed_file_count": len(changed_files),
                "commit_hash": commit_hash,
            }
        return {
            "acceptance_status": "review",
            "acceptance_gate": "manual_review",
            "note": f"Progress is {progress_status}; keep the result under review before promoting it.",
            "rollback_recommended": False,
            "rollback_target": rollback_target,
            "requires_human_review": True,
            "should_promote": False,
            "changed_file_count": len(changed_files),
            "commit_hash": commit_hash,
        }

    def _build_rollback_summary(self, result: dict) -> dict:
        acceptance = result.get("acceptance_summary") or {}
        attempts = result.get("attempts") or []
        latest_attempt = attempts[-1] if attempts else result
        rollback_target = acceptance.get("rollback_target") or result.get("rollback_commit") or latest_attempt.get("rollback_commit")
        changed_files = latest_attempt.get("changed_files") or result.get("changed_files") or []
        commit_hash = result.get("commit_hash") or latest_attempt.get("commit_hash")
        recommended = bool(acceptance.get("rollback_recommended"))
        if result.get("stop_reason") == "success":
            return {
                "rollback_status": "hold_current_baseline",
                "rollback_ready": bool(rollback_target),
                "rollback_target": rollback_target,
                "current_commit_hash": commit_hash,
                "changed_file_count": len(changed_files),
                "action": "Keep the latest validated patch as the active baseline. No rollback is recommended.",
            }
        if recommended:
            return {
                "rollback_status": "rollback_preferred",
                "rollback_ready": bool(rollback_target),
                "rollback_target": rollback_target,
                "current_commit_hash": commit_hash,
                "changed_file_count": len(changed_files),
                "action": "Rollback to the pre-run baseline before attempting a materially different repair route.",
            }
        return {
            "rollback_status": "rollback_optional",
            "rollback_ready": bool(rollback_target),
            "rollback_target": rollback_target,
            "current_commit_hash": commit_hash,
            "changed_file_count": len(changed_files),
            "action": "Rollback is available but not currently the preferred path. Review the latest patch first.",
        }

    def _build_promotion_summary(self, result: dict) -> dict:
        acceptance = result.get("acceptance_summary") or {}
        failure_summary = result.get("failure_summary") or {}
        rollback = result.get("rollback_summary") or {}
        stop_reason = str(result.get("stop_reason") or "unknown")
        progress_status = str(result.get("progress_status") or failure_summary.get("progress_status") or "unknown")
        commit_hash = acceptance.get("commit_hash") or result.get("commit_hash")
        if acceptance.get("acceptance_status") == "accepted" and stop_reason == "success":
            return {
                "promotion_status": "promote_candidate",
                "promotion_gate": "stable_validated_fix",
                "note": "This patch passed the active validation gate and can be treated as the next stable repair candidate.",
                "should_promote": True,
                "requires_review": False,
                "commit_hash": commit_hash,
            }
        if acceptance.get("acceptance_status") == "review" or progress_status == "improving":
            return {
                "promotion_status": "hold_for_review",
                "promotion_gate": "needs_review",
                "note": "The patch shows some promise, but it should stay under review before becoming a stable baseline.",
                "should_promote": False,
                "requires_review": True,
                "commit_hash": commit_hash,
            }
        if rollback.get("rollback_status") == "rollback_preferred":
            return {
                "promotion_status": "reject_candidate",
                "promotion_gate": "rollback_first",
                "note": "Do not promote this patch. Roll back to the previous stable baseline before continuing.",
                "should_promote": False,
                "requires_review": True,
                "commit_hash": commit_hash,
            }
        return {
            "promotion_status": "reject_candidate",
            "promotion_gate": "unstable_result",
            "note": "The latest patch is not stable enough to promote into the working baseline.",
            "should_promote": False,
            "requires_review": True,
            "commit_hash": commit_hash,
        }

    def _build_stability_summary(self, result: dict) -> dict:
        attempts = result.get("attempts") or []
        attempt_count = len(attempts)
        progress_status = str(result.get("progress_status") or "unknown")
        acceptance = result.get("acceptance_summary") or {}
        stop_reason = str(result.get("stop_reason") or "unknown")
        latest_success = bool(result.get("status") == "ok")
        if latest_success and attempt_count <= 2 and progress_status == "improving":
            return {
                "stability_status": "stable",
                "retry_depth": attempt_count,
                "stop_reason": stop_reason,
                "note": "The repair chain converged quickly and produced a validated patch.",
            }
        if acceptance.get("acceptance_status") == "accepted":
            return {
                "stability_status": "caution",
                "retry_depth": attempt_count,
                "stop_reason": stop_reason,
                "note": "The latest patch passed, but the chain required multiple iterations before stabilizing.",
            }
        if stop_reason == "no_progress_detected" or progress_status in {"stalled", "regressing"}:
            return {
                "stability_status": "fragile",
                "retry_depth": attempt_count,
                "stop_reason": stop_reason,
                "note": "The repair chain is unstable and should not be treated as a reliable baseline yet.",
            }
        return {
            "stability_status": "caution",
            "retry_depth": attempt_count,
            "stop_reason": stop_reason,
            "note": "The repair chain is still evolving and should stay under observation.",
        }
