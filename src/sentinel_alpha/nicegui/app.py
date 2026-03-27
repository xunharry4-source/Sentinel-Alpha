from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sentinel_alpha.config import get_settings

PROGRAMMER_ALLOWED_PREFIXES = (
    "src/sentinel_alpha/strategies/",
    "src/sentinel_alpha/infra/generated_sources/",
    "src/sentinel_alpha/infra/generated_terminals/",
    "tests/",
    "scripts/",
)
PROGRAMMER_PROTECTED_PREFIXES = (
    "src/sentinel_alpha/backtesting/",
    "src/sentinel_alpha/api/workflow_service.py",
    "tests/backtesting/test_metrics_engine_contract.py",
    "tests/backtesting/test_backtest_engine.py",
    "tests/backtesting/test_workflow_backtest_integration.py",
)

try:
    from nicegui import ui
    import nicegui.run as nicegui_run
except ModuleNotFoundError:  # pragma: no cover - runtime dependency guard
    ui = None  # type: ignore[assignment]
    nicegui_run = None  # type: ignore[assignment]


@dataclass
class UiState:
    session_id: str = ""
    snapshot: dict[str, Any] | None = None
    health_payload: dict[str, Any] | None = None
    config_payload: dict[str, Any] | None = None
    config_validation: dict[str, Any] | None = None
    config_test_result: dict[str, Any] | None = None
    local_strategy_logs: list[str] = field(default_factory=list)
    local_simulation_logs: list[str] = field(default_factory=list)
    local_operation_logs: list[str] = field(default_factory=list)


def _api_json(method: str, api_base: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        f"{api_base}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method=method.upper(),
    )
    try:
        with urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        try:
            detail = json.loads(raw)
            message = detail.get("detail") or detail.get("message") or raw or f"HTTP {exc.code}"
        except json.JSONDecodeError:
            message = raw or f"HTTP {exc.code}"
        raise RuntimeError(message) from exc
    except URLError as exc:
        raise RuntimeError(f"API unavailable: {exc.reason}") from exc


async def _call_api(method: str, api_base: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return await asyncio.to_thread(_api_json, method, api_base, path, payload)


def _pretty(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, indent=2)


def _lines_markdown(lines: list[str], empty: str) -> str:
    if not lines:
        return empty
    return "\n".join(f"- {line}" for line in lines)


def _fmt_number(value: Any, digits: int = 2, suffix: str = "") -> str:
    if value in (None, ""):
        return "unknown"
    try:
        return f"{float(value):.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_percent(value: Any) -> str:
    return _fmt_number(value, 2, "%")


def _latest(items: list[dict[str, Any]] | None) -> dict[str, Any]:
    return (items or [])[-1] if items else {}


def _session_summary(snapshot: dict[str, Any] | None) -> list[str]:
    if not snapshot:
        return ["尚未加载会话。"]
    package = snapshot.get("strategy_package") or {}
    latest_intel = _latest(snapshot.get("intelligence_runs"))
    return [
        f"session_id: {snapshot.get('session_id', 'unknown')}",
        f"phase/status: {snapshot.get('phase', 'unknown')} / {snapshot.get('status', 'unknown')}",
        f"capital: {snapshot.get('starting_capital', 'unknown')}",
        f"strategy_version: {package.get('version_label', 'none')}",
        f"latest_intelligence_query: {latest_intel.get('query', 'none')}",
    ]


def _strategy_archive_entries(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    reports = [item for item in (snapshot or {}).get("report_history", []) if item.get("report_type") == "strategy_iteration"]
    entries: list[dict[str, Any]] = []
    for item in reports:
        body = item.get("body") or {}
        pkg = body.get("strategy_package") or {}
        version = pkg.get("version_label")
        if not version:
            continue
        entries.append(
            {
                "report_id": item.get("report_id"),
                "created_at": item.get("created_at"),
                "title": item.get("title"),
                "version": version,
                "strategy_type": pkg.get("strategy_type", "unknown"),
                "pkg": pkg,
                "log_entry": body.get("training_log_entry") or {},
                "research_export": body.get("research_export") or {},
            }
        )
    return entries


def _strategy_research_entries(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    current_pkg = (snapshot or {}).get("strategy_package") or {}
    current_research = current_pkg.get("research_summary") or {}
    if current_pkg.get("version_label") and current_research:
        entries.append(
            {
                "value": f"current:{current_pkg['version_label']}",
                "label": f"[当前] {current_pkg['version_label']}",
                "version": current_pkg["version_label"],
                "created_at": (snapshot or {}).get("updated_at") or (snapshot or {}).get("last_updated") or "current",
                "pkg": current_pkg,
                "research": current_research,
                "export": {},
                "is_current": True,
            }
        )
    for item in _strategy_archive_entries(snapshot):
        export_manifest = item.get("research_export") or {}
        research = export_manifest.get("research_summary") or item.get("pkg", {}).get("research_summary") or item.get("log_entry", {}).get("research_summary") or {}
        value = item["version"]
        if any(existing["value"] == value for existing in entries):
            continue
        entries.append(
            {
                "value": value,
                "label": value,
                "version": value,
                "created_at": item.get("created_at"),
                "pkg": item.get("pkg") or {},
                "research": research,
                "export": export_manifest,
                "is_current": False,
            }
        )
    return entries


def _strategy_status_lines(snapshot: dict[str, Any] | None) -> list[str]:
    pkg = (snapshot or {}).get("strategy_package") or {}
    if not pkg:
        return []
    recommended = pkg.get("recommended_variant") or {}
    return [
        f"当前阶段: {(snapshot or {}).get('phase', 'unknown')}",
        f"当前版本: {pkg.get('version_label', 'unknown')}",
        f"策略类型: {pkg.get('strategy_type', 'unknown')}",
        f"迭代模式: {pkg.get('iteration_mode', 'unknown')}",
        f"目标函数: {pkg.get('objective_metric', 'unknown')}",
        f"推荐候选: {recommended.get('variant_id', 'unknown')}",
        f"推荐理由: {recommended.get('reason', '无')}",
        f"当前标的池: {', '.join(pkg.get('selected_universe') or []) or '无'}",
        f"训练区间: {pkg.get('dataset_plan', {}).get('user_selected_window', {}).get('start') or pkg.get('dataset_plan', {}).get('train', {}).get('start') or 'unknown'} -> {pkg.get('dataset_plan', {}).get('user_selected_window', {}).get('end') or pkg.get('dataset_plan', {}).get('test', {}).get('end') or 'unknown'}",
    ]


def _input_manifest_lines(snapshot: dict[str, Any] | None) -> list[str]:
    manifest = ((snapshot or {}).get("strategy_package") or {}).get("input_manifest") or {}
    lineage = manifest.get("source_lineage") or {}
    data_quality = manifest.get("data_quality") or {}
    lines: list[str] = []
    if manifest.get("data_bundle_id") or manifest.get("feature_snapshot_version"):
        lines.append(f"bundle / {manifest.get('data_bundle_id', 'unknown')} / snapshot={manifest.get('feature_snapshot_version', 'unknown')}")
    if manifest.get("dataset_protocol") or manifest.get("objective_metric"):
        lines.append(
            f"dataset / protocol={manifest.get('dataset_protocol', 'unknown')} / objective={manifest.get('objective_metric', 'unknown')} / walk_forward={manifest.get('walk_forward_windows', 'unknown')}"
        )
    if manifest.get("selected_universe"):
        lines.append(f"universe / size={manifest.get('selected_universe_size', len(manifest.get('selected_universe') or []))} / {', '.join(manifest.get('selected_universe') or [])}")
    if manifest.get("available_sections") or manifest.get("provider_coverage"):
        lines.append(
            f"coverage / sections={', '.join(manifest.get('available_sections') or []) or 'none'} / providers={', '.join(manifest.get('provider_coverage') or []) or 'none'}"
        )
    if data_quality.get("quality_grade"):
        lines.append(
            f"quality / grade={data_quality.get('quality_grade')} / training={data_quality.get('training_readiness', {}).get('status', 'unknown')}"
        )
    if data_quality.get("freshness"):
        freshness = data_quality["freshness"]
        lines.append(f"freshness / gap_hours={freshness.get('max_gap_hours', 'unknown')} / ts_count={freshness.get('known_timestamp_count', 0)}")
    if data_quality.get("alignment_warnings"):
        lines.append(f"freshness / warnings={', '.join(data_quality.get('alignment_warnings') or [])}")
    if lineage:
        lines.append(
            f"lineage / market={lineage.get('market', {}).get('source', 'none')} / intel={lineage.get('intelligence', {}).get('run_id', 'none')} / financials={lineage.get('fundamentals', {}).get('run_id', 'none')}"
        )
        lines.append(
            f"lineage / dark_pool={lineage.get('dark_pool', {}).get('run_id', 'none')} / options={lineage.get('options', {}).get('run_id', 'none')}"
        )
    return lines


def _feature_snapshot_lines(snapshot: dict[str, Any] | None) -> list[str]:
    features = ((snapshot or {}).get("strategy_package") or {}).get("feature_snapshot") or {}
    lines: list[str] = []
    if features.get("meta"):
        meta = features["meta"]
        lines.append(f"meta / version={meta.get('snapshot_version', 'unknown')} / hash={meta.get('snapshot_hash', 'unknown')} / bundle={meta.get('data_bundle_id', 'unknown')}")
    if features.get("data_quality"):
        quality = features["data_quality"]
        lines.append(
            f"data_quality / coverage={quality.get('section_coverage_score', 'unknown')} / providers={quality.get('provider_count', 0)} / grade={quality.get('quality_grade', 'unknown')}"
        )
        lines.append(
            f"data_quality / available={', '.join(quality.get('available_sections') or []) or 'none'} / missing={', '.join(quality.get('missing_sections') or []) or 'none'}"
        )
    if features.get("source_lineage"):
        lineage = features["source_lineage"]
        lines.append(
            f"lineage / market={lineage.get('market', {}).get('source', 'none')} / intel={lineage.get('intelligence', {}).get('run_id', 'none')} / financials={lineage.get('fundamentals', {}).get('run_id', 'none')}"
        )
        lines.append(
            f"lineage / dark_pool={lineage.get('dark_pool', {}).get('run_id', 'none')} / options={lineage.get('options', {}).get('run_id', 'none')}"
        )
    if features.get("behavioral"):
        behavioral = features["behavioral"]
        lines.append(
            f"behavioral / mode={behavioral.get('report_generation_mode', 'unknown')} / status={behavioral.get('analysis_status', 'unknown')} / noise={behavioral.get('noise_sensitivity', 'unknown')}"
        )
    if features.get("intelligence", {}).get("factors"):
        factors = features["intelligence"]["factors"]
        lines.append(
            f"intelligence / credibility={factors.get('credibility_score', 'unknown')} / contradiction={factors.get('contradiction_score', 'unknown')} / docs={features.get('intelligence', {}).get('document_count', 0)}"
        )
    if features.get("fundamentals", {}).get("factors"):
        factors = features["fundamentals"]["factors"]
        lines.append(f"fundamentals / quality={factors.get('quality_score', 'unknown')} / deterioration={factors.get('deterioration_score', 'unknown')}")
    if features.get("dark_pool", {}).get("factors"):
        factors = features["dark_pool"]["factors"]
        lines.append(f"dark_pool / accumulation={factors.get('accumulation_score', 'unknown')} / records={factors.get('record_count', 'unknown')}")
    if features.get("options", {}).get("factors"):
        factors = features["options"]["factors"]
        lines.append(f"options / pressure={factors.get('options_pressure_score', 'unknown')} / oi={factors.get('total_open_interest', 'unknown')}")
    return lines


def _data_bundle_lines(snapshot: dict[str, Any] | None) -> list[str]:
    bundles = (snapshot or {}).get("data_bundles") or []
    return [
        f"{item.get('created_at')} / {item.get('data_bundle_id')} / protocol={item.get('dataset_protocol', 'unknown')} / universe={item.get('selected_universe_size', 0)} / uses={item.get('usage_count', 0)}"
        for item in reversed(bundles)
    ]


def _package_lines(snapshot: dict[str, Any] | None) -> list[str]:
    pkg = (snapshot or {}).get("strategy_package") or {}
    if not pkg:
        return []
    return [
        f"version / {pkg.get('version_label', 'unknown')}",
        f"strategy_type / {pkg.get('strategy_type', 'unknown')}",
        f"objective / {pkg.get('objective_metric', 'unknown')}",
        f"selected_universe / {', '.join(pkg.get('selected_universe') or []) or 'none'}",
        f"recommended_variant / {(pkg.get('recommended_variant') or {}).get('variant_id', 'unknown')}",
        f"data_bundle / {pkg.get('data_bundle_id') or pkg.get('input_manifest', {}).get('data_bundle_id', 'unknown')}",
    ]


def _strategy_checks_lines(snapshot: dict[str, Any] | None) -> list[str]:
    checks = (snapshot or {}).get("strategy_checks") or []
    lines: list[str] = []
    for item in checks:
        lines.append(
            f"{item.get('check_type', 'unknown')} / status={item.get('status', 'unknown')} / score={item.get('score', 'unknown')} / summary={item.get('summary', '无')}"
        )
        for action in item.get("required_fix_actions") or []:
            lines.append(f"required_fix / {action}")
    return lines


def _check_trend_lines(snapshot: dict[str, Any] | None) -> list[str]:
    logs = (snapshot or {}).get("strategy_training_log") or []
    counts: dict[str, int] = {}
    gate_counts = {"passed": 0, "blocked": 0}
    for item in logs:
        for check_type in item.get("failed_checks") or []:
            counts[check_type] = counts.get(check_type, 0) + 1
        gate_status = (item.get("research_summary") or {}).get("final_release_gate_summary", {}).get("gate_status")
        if gate_status in gate_counts:
            gate_counts[gate_status] += 1
    summary = [f"release_gate / passed={gate_counts['passed']} / blocked={gate_counts['blocked']}"]
    summary.extend(f"{name}: {count}" for name, count in sorted(counts.items(), key=lambda pair: pair[1], reverse=True))
    for item in reversed(logs[-8:]):
        failed = ", ".join(item.get("failed_checks") or []) or "无"
        next_focus = "；".join((item.get("research_summary") or {}).get("next_iteration_focus") or []) or "无"
        gate_status = (item.get("research_summary") or {}).get("final_release_gate_summary", {}).get("gate_status", "unknown")
        summary.append(
            f"{item.get('timestamp')} / 第{item.get('iteration_no', '-')}版 / status={item.get('status', 'unknown')} / gate={gate_status} / failed={failed} / next={next_focus}"
        )
    return summary


def _build_repair_routes(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    logs = (snapshot or {}).get("strategy_training_log") or []
    runs = (snapshot or {}).get("programmer_runs") or []
    latest_log = logs[-1] if logs else {}
    latest_run = runs[-1] if runs else {}
    failed_checks = latest_log.get("failed_checks") or []
    next_focus = (latest_log.get("research_summary") or {}).get("next_iteration_focus") or []
    programmer_failure = latest_run.get("failure_type") or ("success" if latest_run.get("status") == "ok" else latest_run.get("status", "unknown"))
    programmer_plan = latest_run.get("repair_plan") or {}
    routes: list[dict[str, Any]] = []

    if "integrity" in failed_checks:
        if programmer_failure == "compile_failure":
            routes.append(
                {
                    "lane": "结构修复",
                    "priority": "P0",
                    "source": "research",
                    "summary": "先修编译和代码结构，再处理 integrity 规则。",
                    "actions": ["修正导入、语法、命名和返回结构", "确保策略输出字段完整", "重新跑 compile + pytest 后再送 integrity 检查"],
                }
            )
        else:
            routes.append(
                {
                    "lane": "完整性修复",
                    "priority": "P1",
                    "source": "research",
                    "summary": "优先按 integrity 失败项修正未来函数、作弊痕迹、硬编码和可疑 rationale。",
                    "actions": ["检查 future/leakage 线索", "减少可疑高置信度硬编码", "根据 required_fix_actions 逐项修正"],
                }
            )
    if "stress_overfit" in failed_checks:
        routes.append(
            {
                "lane": "稳健性修复",
                "priority": "P1" if programmer_failure != "test_failure" else "P0",
                "source": "research",
                "summary": "优先处理过拟合和稳健性问题，降低 train-test gap，提升 walk-forward 稳定性。",
                "actions": ["简化规则和参数", "减少对单一 regime 的依赖", "优先看 validation/test/walk-forward 弱点"],
            }
        )
    if not routes and next_focus:
        routes.append(
            {
                "lane": "默认修复",
                "priority": "P1",
                "source": "research",
                "summary": "优先按研究摘要给出的 next_iteration_focus 执行。",
                "actions": next_focus,
            }
        )
    if programmer_plan.get("actions"):
        routes.append(
            {
                "lane": "代码修复计划",
                "priority": programmer_plan.get("priority", "P1"),
                "source": "programmer",
                "summary": f"Programmer Agent 当前主导失败为 {programmer_failure}。",
                "actions": list(dict.fromkeys(programmer_plan.get("actions") or [])),
            }
        )
    if not routes:
        routes.append(
            {
                "lane": "观察",
                "priority": "P2",
                "source": "research",
                "summary": "当前没有足够的失败信号，先继续积累更多训练和修复记录。",
                "actions": ["继续训练或执行一次 Programmer Agent", "观察 release gate 和失败类型是否收敛"],
            }
        )
    return routes


def _repair_route_lines(snapshot: dict[str, Any] | None) -> list[str]:
    lines: list[str] = []
    for route in _build_repair_routes(snapshot):
        lines.append(f"{route['lane']} / {route['priority']} / {route['source']} / {route['summary']}")
        for action in route["actions"]:
            lines.append(f"动作 / {action}")
    return lines


def _research_summary_lines(snapshot: dict[str, Any] | None) -> list[str]:
    summary = ((snapshot or {}).get("strategy_package") or {}).get("research_summary") or {}
    if not summary:
        return []
    winner = summary.get("winner_selection_summary") or {}
    check_target = summary.get("check_target_summary") or {}
    robustness = summary.get("robustness_summary") or {}
    release_gate = summary.get("final_release_gate_summary") or {}
    evaluation_snapshot = summary.get("evaluation_snapshot") or {}
    lines = [
        f"研究摘要 / {summary.get('research_summary', '无')}",
        f"选择规则 / {summary.get('selection_rule', '无')}",
        f"目标函数 / {summary.get('objective_metric', 'unknown')} / 协议={summary.get('dataset_protocol', 'unknown')} / 候选数={summary.get('candidate_count', 0)}",
        f"最优版本 / {winner.get('winner_variant_id', 'unknown')} / version={winner.get('winner_version', 'unknown')} / test={winner.get('winner_test_objective_score', 'unknown')} / validation={winner.get('winner_validation_objective_score', 'unknown')} / stability={winner.get('winner_stability_score', 'unknown')}",
        f"送检目标 / {check_target.get('variant_id', 'unknown')} / source={check_target.get('source', 'unknown')} / eval_source={check_target.get('evaluation_source', 'unknown')}",
        f"稳健性 / grade={robustness.get('grade', 'unknown')} / stability={robustness.get('stability_score', 'unknown')} / gap={robustness.get('train_test_gap', 'unknown')} / {robustness.get('note', '无')}",
        f"发布门 / status={release_gate.get('gate_status', 'unknown')} / failed={release_gate.get('failed_check_count', 0)} / passed={release_gate.get('passed_check_count', 0)} / blockers={', '.join(release_gate.get('gate_blockers') or []) or '无'}",
        f"评估快照 / source={evaluation_snapshot.get('evaluation_source', 'unknown')} / wf_windows={evaluation_snapshot.get('walk_forward_windows', 0)} / wf_score={evaluation_snapshot.get('walk_forward_score', 'unknown')} / gap={evaluation_snapshot.get('train_test_gap', 'unknown')}",
        f"Train/Validation/Test / {evaluation_snapshot.get('train', {}).get('objective_score', 'unknown')} / {evaluation_snapshot.get('validation', {}).get('objective_score', 'unknown')} / {evaluation_snapshot.get('test', {}).get('objective_score', 'unknown')}",
    ]
    for item in summary.get("evaluation_highlights") or []:
        lines.append(f"评估结论 / {item}")
    if summary.get("next_iteration_focus"):
        lines.append(f"下一轮重点 / {'；'.join(summary.get('next_iteration_focus') or [])}")
    return lines


def _research_code_loop_lines(snapshot: dict[str, Any] | None) -> list[str]:
    logs = list(reversed((snapshot or {}).get("strategy_training_log") or []))[:6]
    runs = list(reversed((snapshot or {}).get("programmer_runs") or []))[:6]
    strategy_counts: dict[str, int] = {}
    programmer_counts: dict[str, int] = {}
    for item in logs:
        for check_type in item.get("failed_checks") or []:
            strategy_counts[check_type] = strategy_counts.get(check_type, 0) + 1
    for run in runs:
        kind = run.get("failure_type") or ("success" if run.get("status") == "ok" else run.get("status", "unknown"))
        programmer_counts[kind] = programmer_counts.get(kind, 0) + 1
    observations: list[str] = []
    if strategy_counts.get("integrity", 0) > 0 and programmer_counts.get("compile_failure", 0) > 0:
        observations.append("完整性失败与 compile_failure 同时偏高，先检查策略代码结构、命名和实现约束。")
    if strategy_counts.get("stress_overfit", 0) > 0 and programmer_counts.get("test_failure", 0) > 0:
        observations.append("过拟合/压力失败与 test_failure 同时偏高，优先修正策略行为和测试预期不一致的问题。")
    return [
        f"策略侧 / {' / '.join(f'{name}={count}' for name, count in strategy_counts.items()) or '无明显失败'}",
        f"编程侧 / {' / '.join(f'{name}={count}' for name, count in programmer_counts.items()) or '无明显失败'}",
        *(observations or ["当前没有观察到明显联动问题。"]),
    ]


def _training_log_lines(state: UiState) -> list[str]:
    remote_logs = (state.snapshot or {}).get("strategy_training_log") or []
    lines = [
        f"{item.get('timestamp')} / 第{item.get('iteration_no', '-')}版 / {item.get('strategy_type', 'unknown')} / {item.get('status', 'unknown')} / failed={', '.join(item.get('failed_checks') or []) or 'none'}"
        for item in reversed(remote_logs[-12:])
    ]
    return state.local_strategy_logs[-12:] + lines


def _variant_compare_lines(snapshot: dict[str, Any] | None) -> list[str]:
    pkg = (snapshot or {}).get("strategy_package") or {}
    baseline = pkg.get("baseline_evaluation") or {}
    candidates = pkg.get("candidate_variants") or []
    if not baseline or not candidates:
        return []
    lines = [
        f"Baseline / 收益 {_fmt_percent(baseline.get('expected_return_pct'))} / 胜率 {_fmt_percent(baseline.get('win_rate_pct'))} / 回撤 {_fmt_percent(baseline.get('drawdown_pct'))} / 最大亏损 {_fmt_percent(baseline.get('max_loss_pct'))} / 目标分 {_fmt_number(baseline.get('objective_score'), 4)}"
    ]
    recommended = (pkg.get("recommended_variant") or {}).get("variant_id")
    for variant in candidates:
        plan = variant.get("plan") or {}
        evaluation = variant.get("evaluation") or {}
        badge = "推荐" if variant.get("variant_id") == recommended else "候选"
        lines.append(
            f"{plan.get('plan_name') or variant.get('variant_id')} / {badge} / 收益 {_fmt_percent(evaluation.get('expected_return_pct'))} / 胜率 {_fmt_percent(evaluation.get('win_rate_pct'))} / 回撤 {_fmt_percent(evaluation.get('drawdown_pct'))} / 最大亏损 {_fmt_percent(evaluation.get('max_loss_pct'))} / 目标分 {_fmt_number(evaluation.get('objective_score'), 4)}"
        )
    return lines


def _backtest_lines(snapshot: dict[str, Any] | None) -> list[str]:
    pkg = (snapshot or {}).get("strategy_package") or {}
    evaluation = (pkg.get("recommended_variant") or {}).get("evaluation") or pkg.get("baseline_evaluation") or {}
    dataset = evaluation.get("dataset_evaluation") or {}
    coverage = evaluation.get("coverage_summary") or ((pkg.get("research_summary") or {}).get("evaluation_snapshot") or {}).get("coverage_summary") or {}
    if not dataset:
        return []
    return [
        f"train / score={_fmt_number(dataset.get('train', {}).get('objective_score'), 4)} / return={_fmt_percent(dataset.get('train', {}).get('expected_return_pct'))} / win_rate={_fmt_percent(dataset.get('train', {}).get('win_rate_pct'))}",
        f"validation / score={_fmt_number(dataset.get('validation', {}).get('objective_score'), 4)} / return={_fmt_percent(dataset.get('validation', {}).get('expected_return_pct'))} / win_rate={_fmt_percent(dataset.get('validation', {}).get('win_rate_pct'))}",
        f"test / score={_fmt_number(dataset.get('test', {}).get('objective_score'), 4)} / return={_fmt_percent(dataset.get('test', {}).get('expected_return_pct'))} / win_rate={_fmt_percent(dataset.get('test', {}).get('win_rate_pct'))} / gross={_fmt_percent(dataset.get('test', {}).get('gross_exposure_pct'))} / turnover={_fmt_percent(dataset.get('test', {}).get('avg_daily_turnover_proxy_pct'))}",
        f"walk_forward / score={_fmt_number(dataset.get('stability', {}).get('walk_forward_score'), 4)} / gap={_fmt_number(dataset.get('stability', {}).get('train_test_gap'), 4)} / stability={_fmt_number(dataset.get('stability', {}).get('score'), 4)}",
        f"coverage / symbols={coverage.get('symbol_count', 'unknown')} / bars={coverage.get('total_bar_count', 'unknown')} / wf_windows={coverage.get('walk_forward_window_count', 0)} / range={coverage.get('date_range', {}).get('start', 'unknown')} -> {coverage.get('date_range', {}).get('end', 'unknown')}",
    ]


def _walk_forward_rows(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    pkg = (snapshot or {}).get("strategy_package") or {}
    evaluation = (pkg.get("recommended_variant") or {}).get("evaluation") or pkg.get("baseline_evaluation") or {}
    return (evaluation.get("dataset_evaluation") or {}).get("walk_forward") or []


def _research_trend_lines(snapshot: dict[str, Any] | None) -> list[str]:
    logs = list(reversed((snapshot or {}).get("strategy_training_log") or []))[:5]
    if not logs:
        return []
    latest = logs[0]
    previous = logs[1] if len(logs) > 1 else {}
    latest_eval = (latest.get("research_summary") or {}).get("evaluation_snapshot") or {}
    previous_eval = (previous.get("research_summary") or {}).get("evaluation_snapshot") or {}
    return [
        f"最近轮次 / {' -> '.join(f'v{item.get('iteration_no', '-')}' for item in logs)}",
        f"gate 趋势 / {(previous.get('research_summary') or {}).get('final_release_gate_summary', {}).get('gate_status', 'unknown')} -> {(latest.get('research_summary') or {}).get('final_release_gate_summary', {}).get('gate_status', 'unknown')}",
        f"test 趋势 / {previous_eval.get('test', {}).get('objective_score', 'unknown')} -> {latest_eval.get('test', {}).get('objective_score', 'unknown')}",
        f"walk_forward 趋势 / {previous_eval.get('walk_forward_score', 'unknown')} -> {latest_eval.get('walk_forward_score', 'unknown')}",
        f"gap 趋势 / {previous_eval.get('train_test_gap', 'unknown')} -> {latest_eval.get('train_test_gap', 'unknown')}",
        f"当前 focus / {'；'.join((latest.get('research_summary') or {}).get('next_iteration_focus') or []) or '无'}",
    ]


def _research_health_lines(snapshot: dict[str, Any] | None) -> list[str]:
    logs = (snapshot or {}).get("strategy_training_log") or []
    if not logs:
        return []
    latest = logs[-1]
    previous = logs[-2] if len(logs) > 1 else {}
    research = latest.get("research_summary") or {}
    prev_eval = (previous.get("research_summary") or {}).get("evaluation_snapshot") or {}
    evaluation = research.get("evaluation_snapshot") or {}
    gate = research.get("final_release_gate_summary", {}).get("gate_status", "unknown")
    robustness = research.get("robustness_summary", {}).get("grade", "unknown")
    status = "warning"
    note = "研究仍需持续观察。"
    if gate == "passed" and robustness == "strong":
        status = "healthy"
        note = "当前研究结果稳定，发布门已通过。"
    elif gate == "blocked" or robustness == "fragile":
        status = "fragile"
        note = "当前研究结果脆弱，仍被检查门阻塞或稳健性不足。"
    return [
        f"status / {status}",
        f"gate / {gate}",
        f"robustness / {robustness}",
        f"note / {note}",
        f"test / {prev_eval.get('test', {}).get('objective_score', 'unknown')} -> {evaluation.get('test', {}).get('objective_score', 'unknown')}",
        f"walk_forward / {prev_eval.get('walk_forward_score', 'unknown')} -> {evaluation.get('walk_forward_score', 'unknown')}",
        f"gap / {prev_eval.get('train_test_gap', 'unknown')} -> {evaluation.get('train_test_gap', 'unknown')}",
        f"focus / {'；'.join(research.get('next_iteration_focus') or []) or '无'}",
    ]


def _history_lines(snapshot: dict[str, Any] | None) -> list[str]:
    logs = (snapshot or {}).get("strategy_training_log") or []
    return [
        f"{item.get('timestamp')} / 第{item.get('iteration_no', '-')}版 / {item.get('strategy_type', 'unknown')} / {item.get('status', 'unknown')} / 失败检查={', '.join(item.get('failed_checks') or []) or '无'} / error={item.get('error', 'none')}"
        for item in reversed(logs)
    ]


def _archive_lines(snapshot: dict[str, Any] | None) -> list[str]:
    return [
        f"{item.get('created_at')} / {item.get('title')} / {item.get('version')} / {item.get('strategy_type')} / {', '.join(item.get('pkg', {}).get('selected_universe') or []) or 'no-universe'}"
        for item in reversed(_strategy_archive_entries(snapshot))
    ]


def _version_compare_lines(snapshot: dict[str, Any] | None, version_a: str, version_b: str) -> list[str]:
    entries = _strategy_archive_entries(snapshot)
    a = next((item for item in entries if item["version"] == version_a), None)
    b = next((item for item in entries if item["version"] == version_b), None)
    if not a or not b:
        return []
    a_eval = (a["pkg"].get("recommended_variant") or {}).get("evaluation") or a["pkg"].get("baseline_evaluation") or {}
    b_eval = (b["pkg"].get("recommended_variant") or {}).get("evaluation") or b["pkg"].get("baseline_evaluation") or {}
    return [
        f"版本A / {a['version']} / {a['strategy_type']}",
        f"版本B / {b['version']} / {b['strategy_type']}",
        f"收益差 / {_fmt_number((b_eval.get('expected_return_pct') or 0) - (a_eval.get('expected_return_pct') or 0), 2, '%')}",
        f"胜率差 / {_fmt_number((b_eval.get('win_rate_pct') or 0) - (a_eval.get('win_rate_pct') or 0), 2, '%')}",
        f"回撤差 / {_fmt_number((b_eval.get('drawdown_pct') or 0) - (a_eval.get('drawdown_pct') or 0), 2, '%')}",
        f"最大亏损差 / {_fmt_number((b_eval.get('max_loss_pct') or 0) - (a_eval.get('max_loss_pct') or 0), 2, '%')}",
        f"目标分差 / {_fmt_number((b_eval.get('objective_score') or 0) - (a_eval.get('objective_score') or 0), 4)}",
        f"版本A失败检查 / {', '.join(a['log_entry'].get('failed_checks') or []) or '无'}",
        f"版本B失败检查 / {', '.join(b['log_entry'].get('failed_checks') or []) or '无'}",
    ]


def _research_detail_lines(snapshot: dict[str, Any] | None, selected_value: str) -> tuple[list[str], dict[str, Any]]:
    entry = next((item for item in _strategy_research_entries(snapshot) if item["value"] == selected_value), None)
    if not entry:
        return [], {}
    export_manifest = entry.get("export") or {}
    research = entry.get("research") or {}
    evaluation = research.get("evaluation_snapshot") or {}
    coverage = evaluation.get("coverage_summary") or export_manifest.get("coverage_summary") or {}
    repair_routes = export_manifest.get("repair_route_summary") or research.get("repair_route_summary") or []
    lines = [
        f"version / {entry['label']}",
        f"created_at / {entry['created_at']}",
        f"winner / {export_manifest.get('winner_variant_id') or research.get('winner_selection_summary', {}).get('winner_variant_id', 'unknown')}",
        f"gate / {export_manifest.get('gate_status') or research.get('final_release_gate_summary', {}).get('gate_status', 'unknown')}",
        f"robustness / {export_manifest.get('robustness_grade') or research.get('robustness_summary', {}).get('grade', 'unknown')}",
        f"bundle / {export_manifest.get('data_bundle_id') or entry.get('pkg', {}).get('data_bundle_id') or entry.get('pkg', {}).get('input_manifest', {}).get('data_bundle_id', 'unknown')}",
        f"quality / {export_manifest.get('quality_grade') or entry.get('pkg', {}).get('input_manifest', {}).get('data_quality', {}).get('quality_grade', 'unknown')}",
        f"check_target / {export_manifest.get('check_target_variant_id') or research.get('check_target_summary', {}).get('variant_id', 'unknown')} / source={export_manifest.get('evaluation_source') or research.get('check_target_summary', {}).get('evaluation_source', 'unknown')}",
        f"train/validation/test / {evaluation.get('train', {}).get('objective_score', 'unknown')} / {evaluation.get('validation', {}).get('objective_score', 'unknown')} / {evaluation.get('test', {}).get('objective_score', 'unknown')}",
        f"walk_forward / {evaluation.get('walk_forward_score', 'unknown')} / windows={evaluation.get('walk_forward_windows', 0)}",
        f"coverage / symbols={coverage.get('symbol_count', 'unknown')} / bars={coverage.get('total_bar_count', 'unknown')} / range={coverage.get('date_range', {}).get('start', 'unknown')} -> {coverage.get('date_range', {}).get('end', 'unknown')}",
        f"next_focus / {'；'.join(export_manifest.get('next_iteration_focus') or research.get('next_iteration_focus') or []) or '无'}",
        f"failed_checks / {', '.join(export_manifest.get('failed_checks') or []) or '无'}",
    ]
    for route in repair_routes:
        lines.append(f"repair_route / {route.get('lane', 'unknown')} / {route.get('priority', 'unknown')} / {route.get('source', 'unknown')} / {route.get('summary', '无摘要')}")
        for action in route.get("actions") or []:
            lines.append(f"repair_action / {action}")
    return lines, {"version": entry["version"], "current": entry["is_current"], "created_at": entry["created_at"], "research_export": export_manifest}


def _failure_evolution_lines(snapshot: dict[str, Any] | None) -> list[str]:
    failures = [
        item
        for item in ((snapshot or {}).get("strategy_training_log") or [])
        if item.get("status") in {"rework_required", "error"}
    ]
    return [
        f"{item.get('timestamp')} / 第{item.get('iteration_no', '-')}版 / {item.get('strategy_type', 'unknown')} / 失败检查={', '.join(item.get('failed_checks') or []) or '无'} / 原因={item.get('analysis_summary') or item.get('error') or '无'}"
        for item in reversed(failures)
    ]


def _release_snapshot_lines(snapshot: dict[str, Any] | None) -> list[str]:
    pkg = (snapshot or {}).get("strategy_package") or {}
    research = pkg.get("research_summary") or {}
    check_target = research.get("check_target_summary") or {}
    gate = research.get("final_release_gate_summary") or {}
    quality = pkg.get("input_manifest", {}).get("data_quality") or {}
    if not pkg.get("version_label"):
        return []
    return [
        f"version / {pkg.get('version_label')}",
        f"winner / {research.get('winner_selection_summary', {}).get('winner_variant_id', 'unknown')}",
        f"gate / {gate.get('gate_status', 'unknown')}",
        f"evaluation_source / {check_target.get('evaluation_source', 'unknown')}",
        f"bundle / {pkg.get('data_bundle_id') or pkg.get('input_manifest', {}).get('data_bundle_id', 'unknown')}",
        f"quality / {quality.get('quality_grade', 'unknown')} / training={quality.get('training_readiness', {}).get('status', 'unknown')}",
        f"gate_reason / {gate.get('reason', '无')}",
    ]


def _analysis_lines(snapshot: dict[str, Any] | None) -> list[str]:
    analysis = ((snapshot or {}).get("strategy_package") or {}).get("analysis") or {}
    if not analysis:
        return []
    previous = analysis.get("previous_failure_reasons") or {}
    return [
        f"目标函数 / {analysis.get('objective_metric', 'unknown')}",
        f"分析摘要 / {analysis.get('summary', '无')}",
        f"当前问题 / {'；'.join(analysis.get('current_strategy_problems') or []) or '无'}",
        f"上次失败 / {previous.get('summary', '无')}",
        f"失败检查 / {', '.join(previous.get('failed_checks') or []) or '无'}",
        f"本轮反馈 / {analysis.get('feedback', '无')}",
    ]


def _strategy_code(snapshot: dict[str, Any] | None) -> str:
    pkg = (snapshot or {}).get("strategy_package") or {}
    if not pkg.get("generated_strategy_code"):
        return "还没有策略代码。"
    recommended = (pkg.get("recommended_variant") or {}).get("variant_id")
    for item in pkg.get("candidate_variants") or []:
        if item.get("variant_id") == recommended and item.get("generated_code"):
            return item["generated_code"]
    return pkg.get("generated_strategy_code") or "还没有策略代码。"


def _model_routing_lines(snapshot: dict[str, Any] | None) -> list[str]:
    pkg = (snapshot or {}).get("strategy_package") or {}
    agent_map = pkg.get("agent_model_map") or {}
    task_map = pkg.get("task_model_map") or {}
    lines = [
        f"Agent / {agent}: {info.get('provider', 'unknown')} / {' -> '.join(info.get('models') or [info.get('model', 'unknown')])}"
        for agent, info in agent_map.items()
    ]
    lines.extend(
        f"Task / {task}: {info.get('provider', 'unknown')} / {' -> '.join(info.get('models') or [info.get('model', 'unknown')])} / temperature={info.get('temperature', 'default')}"
        for task, info in task_map.items()
    )
    return lines


def _token_usage_lines(snapshot: dict[str, Any] | None) -> list[str]:
    usage = (snapshot or {}).get("token_usage") or {}
    totals = list((usage.get("totals") or {}).values())
    aggregate = usage.get("aggregate") or {}
    recent = usage.get("recent_calls") or []
    lines = [
        f"api_requests / {aggregate.get('api_request_count', 0)} / total_tokens={aggregate.get('total_tokens', 0)} / live={aggregate.get('live_request_count', 0)} / fallback={aggregate.get('fallback_request_count', 0)}",
        f"llm_quality / fallback_ratio={aggregate.get('fallback_ratio', 0)} / recent_fallback_ratio={aggregate.get('recent_fallback_ratio', 0)} / cache_hit_ratio={aggregate.get('cache_hit_ratio', 0)} / recent_calls={aggregate.get('recent_call_count', 0)}",
    ]
    lines.extend(
        f"{item.get('task')} / {item.get('provider')}/{item.get('model')} / calls={item.get('calls')} / cache_hits={item.get('cache_hits', 0)} / in={item.get('input_tokens')} / out={item.get('output_tokens')}"
        for item in sorted(totals, key=lambda row: row.get("calls", 0), reverse=True)
    )
    lines.extend(
        f"{item.get('timestamp', 'unknown')} / {item.get('task')} / {item.get('provider')}/{item.get('model')} / in={item.get('input_tokens')} / out={item.get('output_tokens')}"
        for item in reversed(recent[-5:])
    )
    return lines


def _programmer_runs_lines(snapshot: dict[str, Any] | None) -> list[str]:
    runs = (snapshot or {}).get("programmer_runs") or []
    lines: list[str] = []
    for item in reversed(runs):
        lines.append(
            f"{item.get('timestamp', 'unknown')} / {item.get('status', 'unknown')} / failure={item.get('failure_type', 'none')} / commit={item.get('commit_hash', 'none')} / rollback={item.get('rollback_commit', 'none')} / files={', '.join(item.get('changed_files') or []) or 'none'}"
        )
        if item.get("repair_plan", {}).get("actions"):
            lines.append(
                f"repair_plan / {item.get('repair_plan', {}).get('priority', 'P1')} / {'；'.join(item.get('repair_plan', {}).get('actions') or [])}"
            )
        if item.get("validation_detail"):
            lines.append(f"validation_gate / {item.get('validation_detail')}")
    return lines


def _programmer_stats_lines(snapshot: dict[str, Any] | None) -> list[str]:
    runs = (snapshot or {}).get("programmer_runs") or []
    counts: dict[str, int] = {}
    for run in runs:
        kind = run.get("failure_type") or ("success" if run.get("status") == "ok" else "unknown")
        counts[kind] = counts.get(kind, 0) + 1
    lines = [f"{name}: {count}" for name, count in sorted(counts.items(), key=lambda pair: pair[1], reverse=True)]
    lines.extend(
        f"{item.get('timestamp', 'unknown')} / {item.get('failure_type', 'unknown')} / {item.get('validation_detail') or item.get('stderr') or item.get('error') or 'no detail'}"
        for item in reversed([row for row in runs if row.get("failure_type")][-5:])
    )
    return lines


def _programmer_diff(snapshot: dict[str, Any] | None) -> str:
    runs = (snapshot or {}).get("programmer_runs") or []
    if not runs:
        return "还没有代码差异。"
    latest = runs[-1]
    parts = []
    if latest.get("failure_summary"):
        parts.append(_pretty(latest["failure_summary"]))
    if latest.get("repair_plan"):
        parts.append(_pretty(latest["repair_plan"]))
    if latest.get("diff"):
        parts.append(latest["diff"])
    if latest.get("stderr"):
        parts.append(latest["stderr"])
    return "\n\n".join(parts) or "还没有代码差异。"


def _programmer_trend_lines(snapshot: dict[str, Any] | None, filter_value: str) -> list[str]:
    runs = (snapshot or {}).get("programmer_runs") or []
    lines = []
    for run in reversed(runs):
        kind = run.get("failure_type") or ("success" if run.get("status") == "ok" else run.get("status", "unknown"))
        if filter_value != "all" and kind != filter_value:
            continue
        lines.append(
            f"{run.get('timestamp', 'unknown')} / {kind} / attempts={len(run.get('attempts') or []) or 1} / {run.get('validation_detail') or run.get('error') or run.get('stderr') or 'no detail'}"
        )
    return lines[:10]


def _model_result_specs(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    pkg = (snapshot or {}).get("strategy_package") or {}
    models: list[dict[str, Any]] = []
    recommended_variant = pkg.get("recommended_variant") or {}
    recommended = recommended_variant.get("variant_id")
    if recommended_variant.get("evaluation"):
        models.append(
            {
                "title": recommended or "当前推荐策略",
                "subtitle": recommended_variant.get("reason") or "当前推荐结果",
                "evaluation": recommended_variant.get("evaluation") or {},
                "selected": True,
            }
        )
    if pkg.get("baseline_evaluation"):
        models.append({"title": "Baseline", "subtitle": "基准策略", "evaluation": pkg.get("baseline_evaluation") or {}, "selected": False})
    for variant in pkg.get("candidate_variants") or []:
        plan = variant.get("plan") or {}
        if variant.get("variant_id") == recommended and recommended_variant.get("evaluation"):
            continue
        models.append(
            {
                "title": plan.get("plan_name") or variant.get("variant_id", "candidate"),
                "subtitle": plan.get("focus") or "候选策略",
                "evaluation": variant.get("evaluation") or {},
                "selected": variant.get("variant_id") == recommended,
            }
        )
    return [item for item in models if item.get("evaluation")]


def _annual_rows(evaluation: dict[str, Any]) -> list[dict[str, Any]]:
    full_period = (evaluation.get("dataset_evaluation") or {}).get("full_period") or {}
    return evaluation.get("annual_performance") or full_period.get("annual_breakdown") or []


def _latest_intelligence_run(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    return _latest((snapshot or {}).get("intelligence_runs"))


def _intelligence_overview_lines(snapshot: dict[str, Any] | None) -> list[str]:
    run = _latest_intelligence_run(snapshot)
    if not run:
        return []
    report = run.get("report") or {}
    factors = report.get("factors") or {}
    source_urls = report.get("source_urls") or []
    status = run.get("status") or ("warning" if run.get("document_count", 0) == 0 else "ok")
    lines = [
        f"最新查询 / {run.get('query', 'unknown')}",
        f"结果状态 / {status} / 文档数={run.get('document_count', 0)} / {'命中缓存' if run.get('cache_hit') else '实时生成'}",
        f"生成时间 / {run.get('timestamp') or run.get('generated_at') or 'unknown'}",
        f"来源数量 / {len(source_urls)} / credibility={factors.get('credibility_score', 'unknown')} / contradiction={factors.get('contradiction_score', 'unknown')}",
    ]
    if report.get("generation_mode"):
        lines.append(f"摘要模式 / {report.get('generation_mode')}")
    return lines


def _intelligence_briefing_lines(snapshot: dict[str, Any] | None) -> list[str]:
    run = _latest_intelligence_run(snapshot)
    if not run:
        return []
    report = run.get("report") or {}
    summary = report.get("summary") or report.get("report_summary")
    if run.get("status") == "error":
        return [
            f"这次查询失败了 / {run.get('error', 'unknown error')}",
            "当前页面仍然保留这次失败记录，方便你判断是 API、网络还是外部数据源问题。",
        ]
    lines: list[str] = []
    if summary:
        lines.append(summary)
    for key in ("market_impact", "bull_case", "bear_case", "risk_note", "next_step", "recommended_action"):
        value = report.get(key)
        if value:
            lines.append(f"{key} / {value}")
    if not lines:
        lines.append("本次查询已经完成，但摘要结构为空。可以直接看下方来源与原始结构化结果。")
    return lines


def _intelligence_source_lines(snapshot: dict[str, Any] | None) -> list[str]:
    run = _latest_intelligence_run(snapshot)
    documents = (run.get("documents") if run else None) or (snapshot or {}).get("intelligence_documents") or []
    if not documents:
        return []
    lines: list[str] = []
    for idx, item in enumerate(documents[:12], start=1):
        source = item.get("source", "unknown")
        title = item.get("title", "untitled")
        snippet = item.get("snippet") or item.get("summary") or item.get("content") or ""
        url = item.get("url", "no-url")
        snippet = str(snippet).replace("\n", " ").strip()
        if len(snippet) > 140:
            snippet = f"{snippet[:140].rstrip()}..."
        line = f"{idx}. {title} / {source}"
        if snippet:
            line += f" / {snippet}"
        line += f" / {url}"
        lines.append(line)
    return lines


def _market_summary_lines(snapshot: dict[str, Any] | None, key: str) -> list[str]:
    runs_key = {
        "financials": "financials_runs",
        "dark_pool": "dark_pool_runs",
        "options": "options_runs",
    }[key]
    runs = (snapshot or {}).get(runs_key) or []
    latest_run = _latest(runs)
    lines: list[str] = []
    if latest_run:
        status = latest_run.get("status") or "ok"
        lines.append(
            f"最新结果 / {latest_run.get('symbol', 'unknown')} / provider={latest_run.get('provider', 'default')} / status={status} / {'命中缓存' if latest_run.get('cache_hit') else '实时查询'}"
        )
        if latest_run.get("expiration"):
            lines.append(f"到期日 / {latest_run.get('expiration')}")
        if latest_run.get("error"):
            lines.append(f"错误 / {latest_run.get('error')}")
        elif latest_run.get("factors"):
            for factor_key, factor_value in (latest_run.get("factors") or {}).items():
                lines.append(f"{factor_key} / {factor_value}")
        payload = latest_run.get("payload") or {}
        for field in ("summary", "report_summary", "note", "signal", "trend", "bias"):
            if payload.get(field):
                lines.append(f"{field} / {payload.get(field)}")
                break
    lines.extend(
        f"历史 / {item.get('generated_at') or item.get('timestamp') or 'unknown'} / {item.get('symbol', 'unknown')} / {item.get('provider', 'default')}"
        for item in reversed(runs[-5:])
    )
    return lines


def _intelligence_history_lines(snapshot: dict[str, Any] | None) -> list[str]:
    runs = (snapshot or {}).get("intelligence_runs") or []
    history = []
    for item in reversed(runs):
        history.append(
            f"{item.get('timestamp') or item.get('generated_at')} / {item.get('query', 'unknown')} / {item.get('document_count', 0)} docs / cache_hit={'yes' if item.get('cache_hit') else 'no'}"
        )
    return history


def _intelligence_history_entries(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    runs = (snapshot or {}).get("intelligence_runs") or []
    entries: list[dict[str, Any]] = []
    for item in reversed(runs):
        query = item.get("query", "unknown")
        generated_at = item.get("timestamp") or item.get("generated_at") or "unknown"
        status = item.get("status") or ("warning" if item.get("document_count", 0) == 0 else "ok")
        entries.append(
            {
                "value": item.get("run_id") or generated_at,
                "label": f"{generated_at} | {query} | {item.get('document_count', 0)} docs | {status}",
                "run": item,
            }
        )
    return entries


def _intelligence_history_detail_lines(snapshot: dict[str, Any] | None, selected_value: str) -> tuple[list[str], dict[str, Any]]:
    entry = next((item for item in _intelligence_history_entries(snapshot) if item["value"] == selected_value), None)
    if not entry:
        return [], {}
    run = entry["run"] or {}
    report = run.get("report") or {}
    factors = report.get("factors") or {}
    lines = [
        f"查询词 / {run.get('query', 'unknown')}",
        f"时间 / {run.get('timestamp') or run.get('generated_at') or 'unknown'}",
        f"状态 / {run.get('status') or 'ok'} / 文档数={run.get('document_count', 0)} / {'命中缓存' if run.get('cache_hit') else '实时生成'}",
    ]
    if run.get("error"):
        lines.append(f"错误 / {run.get('error')}")
    if report.get("summary") or report.get("report_summary"):
        lines.append(f"摘要 / {report.get('summary') or report.get('report_summary')}")
    if factors:
        lines.append(
            f"因子 / credibility={factors.get('credibility_score', 'unknown')} / contradiction={factors.get('contradiction_score', 'unknown')}"
        )
    source_urls = report.get("source_urls") or []
    if source_urls:
        lines.append(f"来源数量 / {len(source_urls)}")
        lines.extend(f"source / {item}" for item in source_urls[:8])
    return lines, run


def _infer_symbol_from_query(query: str | None) -> str:
    text = (query or "").strip().upper()
    if not text:
        return "UNKNOWN"
    return text.split()[0]


def _intelligence_watchlist_summary_lines(snapshot: dict[str, Any] | None) -> list[str]:
    runs = (snapshot or {}).get("intelligence_runs") or []
    latest_by_symbol: dict[str, dict[str, Any]] = {}
    for item in runs:
        symbol = _infer_symbol_from_query(item.get("query"))
        latest_by_symbol[symbol] = item
    lines: list[str] = []
    for symbol, item in sorted(latest_by_symbol.items()):
        report = item.get("report") or {}
        summary = report.get("summary") or report.get("report_summary") or item.get("error") or "暂无摘要"
        summary = str(summary).replace("\n", " ").strip()
        if len(summary) > 96:
            summary = f"{summary[:96].rstrip()}..."
        status = item.get("status") or ("warning" if item.get("document_count", 0) == 0 else "ok")
        lines.append(
            f"{symbol} / status={status} / docs={item.get('document_count', 0)} / {summary}"
        )
    return lines


def _behavior_report_lines(report: dict[str, Any] | None, label: str) -> list[str]:
    if not report:
        return []
    lines = [
        f"{label} / mode={report.get('report_generation_mode', 'unknown')} / status={report.get('analysis_status', 'unknown')}",
    ]
    if report.get("strategy_type"):
        lines.append(f"strategy / {report.get('strategy_type')} / confidence={report.get('strategy_confidence', 'unknown')}")
    if report.get("recommended_strategy_type") or report.get("recommended_trading_frequency"):
        lines.append(
            f"recommendation / strategy={report.get('recommended_strategy_type', 'unknown')} / frequency={report.get('recommended_trading_frequency', 'unknown')} / timeframe={report.get('recommended_timeframe', 'unknown')}"
        )
    if report.get("execution_quality_note"):
        lines.append(f"execution_quality / {report.get('execution_quality_note')}")
    if report.get("trading_preference_recommendation_note"):
        lines.append(f"preference_note / {report.get('trading_preference_recommendation_note')}")
    if report.get("behavior_tags"):
        lines.append(f"behavior_tags / {', '.join(report.get('behavior_tags') or [])}")
    if report.get("analysis_warning"):
        lines.append(f"warning / {report.get('analysis_warning')}")
    for key in (
        "executed_trade_ratio",
        "partial_fill_ratio",
        "rejected_order_ratio",
        "unfilled_order_ratio",
        "clean_execution_ratio",
        "fast_event_ratio",
        "slow_event_ratio",
    ):
        if key in report:
            lines.append(f"{key} / {report.get(key)}")
    return lines


def _simulation_trade_lines(snapshot: dict[str, Any] | None) -> list[str]:
    records = (snapshot or {}).get("trade_records") or []
    return [
        f"{item.get('timestamp', 'unknown')} / {item.get('symbol', item.get('ticker', 'unknown'))} / action={item.get('action', 'unknown')} / status={item.get('status', item.get('execution_status', 'unknown'))} / pnl={item.get('pnl_pct', item.get('profit_pct', 'unknown'))}"
        for item in reversed(records[-20:])
    ]


def _simulation_scenario_lines(snapshot: dict[str, Any] | None) -> list[str]:
    scenarios = (snapshot or {}).get("scenarios") or []
    return [
        f"{item.get('scenario_id', item.get('id', 'unknown'))} / {item.get('title', item.get('label', 'scenario'))} / status={item.get('status', 'unknown')}"
        for item in reversed(scenarios[-20:])
    ]


def _simulation_market_lines(snapshot: dict[str, Any] | None) -> list[str]:
    market = (snapshot or {}).get("simulation_market") or {}
    current = market.get("current_bar") or {}
    if not market:
        return []
    return [
        f"symbol / {market.get('symbol', 'unknown')}",
        f"provider / {market.get('provider', 'unknown')}",
        f"daily / {market.get('daily_bar_count', 0)} bars / lookback={market.get('daily_lookback', 'unknown')}",
        f"intraday / {market.get('intraday_bar_count', 0)} bars / interval={market.get('intraday_interval', 'unknown')} / lookback={market.get('intraday_lookback', 'unknown')}",
        f"current_time / {market.get('current_timestamp', 'unknown')}",
        f"current_price / {_fmt_number(current.get('close'), 2)}",
        f"drawdown / {_fmt_percent(market.get('current_drawdown_pct'))}",
        f"progress / {_fmt_number(market.get('progress_pct'), 2, '%')} / remaining_steps={market.get('remaining_steps', 'unknown')}",
    ]


def _simulation_chart_option(
    bars: list[dict[str, Any]] | None,
    *,
    title: str,
    current_timestamp: str | None = None,
) -> dict[str, Any]:
    items = bars or []
    x_axis = [str(item.get("timestamp", ""))[5:16].replace("T", " ") for item in items]
    close_values = [float(item.get("close") or 0.0) for item in items]
    current_index = next((index for index, item in enumerate(items) if item.get("timestamp") == current_timestamp), None)
    mark_point = None
    if current_index is not None and 0 <= current_index < len(close_values):
        mark_point = {
            "data": [
                {
                    "name": "current",
                    "coord": [x_axis[current_index], close_values[current_index]],
                    "value": close_values[current_index],
                }
            ]
        }
    return {
        "animation": False,
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "axis"},
        "grid": {"left": 48, "right": 16, "top": 42, "bottom": 36},
        "xAxis": {"type": "category", "data": x_axis, "axisLabel": {"fontSize": 10}},
        "yAxis": {"type": "value", "scale": True, "axisLabel": {"fontSize": 10}},
        "series": [
            {
                "type": "line",
                "smooth": False,
                "data": close_values,
                "lineStyle": {"width": 2, "color": "#1f5551"},
                "itemStyle": {"color": "#c85c3f"},
                "showSymbol": False,
                **({"markPoint": mark_point} if mark_point else {}),
            }
        ],
    }


def _preferences_lines(snapshot: dict[str, Any] | None) -> list[str]:
    prefs = (snapshot or {}).get("trading_preferences") or {}
    if not prefs:
        return []
    return [
        f"frequency / {prefs.get('trading_frequency', 'unknown')}",
        f"timeframe / {prefs.get('preferred_timeframe', 'unknown')}",
        f"rationale / {prefs.get('rationale', '无')}",
        f"conflict_warning / {prefs.get('conflict_warning', '当前没有明显冲突。')}",
    ]


def _preference_recommendation_lines(snapshot: dict[str, Any] | None) -> list[str]:
    report = (snapshot or {}).get("behavioral_user_report") or (snapshot or {}).get("behavioral_report") or {}
    if not report:
        return []
    return [
        f"generation_mode / {report.get('report_generation_mode', 'unknown')}",
        f"analysis_status / {report.get('analysis_status', 'unknown')}",
        f"recommended_frequency / {report.get('recommended_trading_frequency', 'unknown')}",
        f"recommended_timeframe / {report.get('recommended_timeframe', 'unknown')}",
        f"note / {report.get('trading_preference_recommendation_note') or report.get('analysis_warning') or '无'}",
    ]


def _report_history_lines(snapshot: dict[str, Any] | None) -> list[str]:
    reports = (snapshot or {}).get("report_history") or []
    lines: list[str] = []
    for item in reversed(reports[-20:]):
        body = item.get("body") or {}
        pkg = body.get("strategy_package") or {}
        export_manifest = body.get("research_export") or {}
        bundle = export_manifest.get("data_bundle_id") or pkg.get("data_bundle_id")
        winner = export_manifest.get("winner_variant_id")
        gate = export_manifest.get("gate_status")
        suffix = ""
        if pkg.get("version_label"):
            suffix += f" / version={pkg.get('version_label')}"
        if bundle:
            suffix += f" / bundle={bundle}"
        if winner:
            suffix += f" / winner={winner}"
        if gate:
            suffix += f" / gate={gate}"
        lines.append(f"{item.get('created_at', 'unknown')} / {item.get('report_type', 'unknown')} / {item.get('title', 'untitled')}{suffix}")
    return lines


def _feedback_lines(snapshot: dict[str, Any] | None) -> list[str]:
    feedback_log = (snapshot or {}).get("strategy_feedback_log") or []
    return [
        f"{item.get('timestamp', 'unknown')} / {item.get('strategy_type', 'unknown')} / {item.get('feedback', '无')} / source={item.get('source_type', 'strategy_feedback')}"
        for item in reversed(feedback_log[-20:])
    ]


def _history_event_lines(snapshot: dict[str, Any] | None) -> list[str]:
    events = (snapshot or {}).get("history_events") or []
    return [
        f"{item.get('timestamp', 'unknown')} / {item.get('event_type', 'unknown')} / {item.get('summary', '无摘要')}"
        for item in reversed(events[-30:])
    ]


def _data_source_lines(snapshot: dict[str, Any] | None) -> list[str]:
    runs = (snapshot or {}).get("data_source_runs") or []
    return [
        f"{item.get('timestamp', item.get('generated_at', 'unknown'))} / {item.get('provider', 'unknown')} / {item.get('status', 'unknown')} / analysis={((item.get('analysis') or {}).get('generation_mode', 'unknown'))} / smoke={((item.get('smoke_test') or {}).get('status', 'not_run'))} / {item.get('summary', item.get('message', '无摘要'))}"
        for item in reversed(runs[-20:])
    ]


def _terminal_lines(snapshot: dict[str, Any] | None) -> list[str]:
    runs = (snapshot or {}).get("terminal_integration_runs") or []
    return [
        f"{item.get('timestamp', 'unknown')} / {item.get('terminal_name', 'unknown')} / type={item.get('terminal_type', 'unknown')} / status={item.get('status', item.get('readiness_status', 'unknown'))} / reliability={item.get('reliability_status', 'unknown')}"
        for item in reversed(runs[-20:])
    ]


def _monitor_lines(snapshot: dict[str, Any] | None) -> list[str]:
    monitors = (snapshot or {}).get("monitors") or []
    return [
        f"{item.get('monitor_name', item.get('name', 'unknown'))} / severity={item.get('severity', 'unknown')} / status={item.get('status', 'unknown')} / {item.get('summary', item.get('message', '无摘要'))}"
        for item in monitors
    ]


def _configuration_lines(snapshot: dict[str, Any] | None) -> list[str]:
    trade_universe = (snapshot or {}).get("trade_universe") or {}
    prefs = (snapshot or {}).get("trading_preferences") or {}
    pkg = (snapshot or {}).get("strategy_package") or {}
    requested = trade_universe.get("requested") or trade_universe.get("expanded") or []
    return [
        f"execution_mode / {(snapshot or {}).get('execution_mode', 'unknown')}",
        f"trade_universe / type={trade_universe.get('input_type', 'unknown')} / symbols={', '.join(requested) or 'none'}",
        f"trading_preferences / frequency={prefs.get('trading_frequency', 'unknown')} / timeframe={prefs.get('preferred_timeframe', 'unknown')}",
        f"strategy_type / {pkg.get('strategy_type', 'unknown')}",
        f"objective_metric / {pkg.get('objective_metric', 'unknown')}",
        f"version_label / {pkg.get('version_label', 'unknown')}",
    ]


def _validation_lines(payload: dict[str, Any] | None) -> list[str]:
    if not payload:
        return []
    if "validation" in payload and isinstance(payload.get("validation"), dict):
        payload = payload.get("validation")
    lines: list[str] = []
    status = payload.get("status") if isinstance(payload, dict) else None
    if status is not None:
        lines.append(f"status / {status}")
    summary = payload.get("summary") if isinstance(payload, dict) else None
    if summary:
        lines.append(f"summary / {summary}")
    for key in ("errors", "warnings", "recommendations", "missing", "invalid", "checks"):
        value = payload.get(key) if isinstance(payload, dict) else None
        if isinstance(value, list) and value:
            lines.extend(f"{key} / {item}" for item in value[:20])
    if not lines and isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, (str, int, float, bool)):
                lines.append(f"{key} / {value}")
    return lines


def _strategy_input_validation_lines(
    *,
    training_start_value: str | None,
    training_end_value: str | None,
    target_return_value: Any,
    target_win_rate_value: Any,
    target_drawdown_value: Any,
    target_max_loss_value: Any,
) -> tuple[list[str], list[str]]:
    infos: list[str] = []
    errors: list[str] = []

    def _float(value: Any, fallback: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    start_text = (training_start_value or "").strip()
    end_text = (training_end_value or "").strip()
    start_date: date | None = None
    end_date: date | None = None
    if start_text:
        try:
            start_date = date.fromisoformat(start_text)
        except ValueError:
            errors.append("训练开始必须是 YYYY-MM-DD。")
    if end_text:
        try:
            end_date = date.fromisoformat(end_text)
        except ValueError:
            errors.append("训练结束必须是 YYYY-MM-DD。")
    if start_date and end_date:
        window_days = (end_date - start_date).days
        infos.append(f"训练窗口 / {start_text} -> {end_text} / {window_days} 天")
        if window_days <= 0:
            errors.append("训练结束必须晚于训练开始。")
        elif window_days < 180:
            errors.append("训练窗口至少要覆盖 180 天。")
    else:
        infos.append("训练窗口 / 未完整指定，后端将按默认数据窗口切分。")

    target_return_pct = _float(target_return_value, 18.0)
    target_win_rate_pct = _float(target_win_rate_value, 58.0)
    target_drawdown_pct = _float(target_drawdown_value, 12.0)
    target_max_loss_pct = _float(target_max_loss_value, 6.0)
    infos.extend(
        [
            f"目标收益 / {target_return_pct:.2f}%",
            f"目标胜率 / {target_win_rate_pct:.2f}%",
            f"目标回撤 / {target_drawdown_pct:.2f}%",
            f"目标最大亏损 / {target_max_loss_pct:.2f}%",
        ]
    )
    if target_return_pct <= 0:
        errors.append("目标收益必须大于 0。")
    if not 0 < target_win_rate_pct <= 100:
        errors.append("目标胜率必须在 0 到 100 之间。")
    if target_drawdown_pct <= 0:
        errors.append("目标回撤必须大于 0。")
    if target_max_loss_pct <= 0:
        errors.append("目标最大亏损必须大于 0。")
    if target_max_loss_pct > target_drawdown_pct:
        errors.append("目标最大亏损不能大于目标回撤。")
    return infos, errors


def _restore_preview_lines(snapshot: dict[str, Any] | None, selected_version: str | None) -> list[str]:
    entry = next((item for item in _strategy_archive_entries(snapshot) if item["version"] == selected_version), None)
    if not entry:
        return []
    pkg = entry["pkg"] or {}
    targets = pkg.get("objective_targets") or {}
    dataset_plan = pkg.get("dataset_plan") or {}
    window = dataset_plan.get("user_selected_window") or {}
    selected_universe = pkg.get("selected_universe") or []
    return [
        f"恢复版本 / {entry['version']}",
        f"策略类型 / {pkg.get('strategy_type', 'unknown')}",
        f"目标函数 / {pkg.get('objective_metric', 'unknown')}",
        f"目标摘要 / 收益={targets.get('target_return_pct', 'unknown')}% / 胜率={targets.get('target_win_rate_pct', 'unknown')}% / 回撤={targets.get('target_drawdown_pct', 'unknown')}% / 最大亏损={targets.get('target_max_loss_pct', 'unknown')}%",
        f"训练窗口 / {window.get('start', 'unknown')} -> {window.get('end', 'unknown')}",
        f"股票池 / {', '.join(selected_universe[:8]) or 'none'}",
        "说明 / 恢复只会回填当前实验参数，不会自动开始训练。",
    ]


def _run_options(runs: list[dict[str, Any]] | None, label_fields: list[str]) -> dict[str, str]:
    options: dict[str, str] = {}
    for item in reversed(runs or []):
        run_id = item.get("run_id")
        if not run_id:
            continue
        label_parts = [str(item.get(field) or "unknown") for field in label_fields]
        options[run_id] = " / ".join([run_id, *label_parts])
    return options


def _selected_run(runs: list[dict[str, Any]] | None, run_id: str | None) -> dict[str, Any]:
    if not runs:
        return {}
    if run_id:
        matched = next((item for item in runs if item.get("run_id") == run_id), None)
        if matched:
            return matched
    return runs[-1]


def _health_summary_lines(payload: dict[str, Any] | None) -> list[str]:
    if not payload:
        return []
    modules = payload.get("modules") or []
    libraries = payload.get("libraries") or []
    agents = payload.get("agents") or []
    perf = payload.get("performance") or {}
    data_health = payload.get("data_health") or {}
    runtime_health = payload.get("runtime_health") or {}
    return [
        f"overall / {payload.get('status', 'unknown')} / mode={payload.get('service_mode', 'unknown')}",
        f"timestamp / {payload.get('timestamp', 'unknown')}",
        f"modules / total={len(modules)} / ok={sum(1 for item in modules if item.get('status') == 'ok')} / warning={sum(1 for item in modules if item.get('status') == 'warning')} / error={sum(1 for item in modules if item.get('status') == 'error')}",
        f"libraries / total={len(libraries)} / ok={sum(1 for item in libraries if item.get('status') == 'ok')} / warning={sum(1 for item in libraries if item.get('status') == 'warning')} / error={sum(1 for item in libraries if item.get('status') == 'error')}",
        f"agents / total={len(agents)} / idle={sum(1 for item in agents if item.get('status') == 'idle')} / error={sum(1 for item in agents if item.get('status') == 'error')}",
        f"data_health / {data_health.get('status', 'unknown')} / {data_health.get('note', '无')}",
        f"runtime_health / {runtime_health.get('status', 'unknown')} / {runtime_health.get('note', '无')}",
        f"performance / enabled={perf.get('enabled', 'unknown')} / mode={perf.get('mode', 'unknown')}",
    ]


def _health_item_lines(items: list[dict[str, Any]] | None, prefix: str) -> list[str]:
    lines: list[str] = []
    for item in items or []:
        name = item.get("name") or item.get("agent") or "unknown"
        detail = item.get("detail") or item.get("last_detail") or "无详情"
        recommendation = item.get("recommendation") or "No action required."
        status = item.get("status", "unknown")
        lines.append(f"{prefix} / {name} / status={status} / {detail}")
        lines.append(f"recommendation / {recommendation}")
    return lines


def _health_status_color(status: str) -> str:
    if status in {"ok", "healthy", "passed"}:
        return "positive"
    if status in {"warning", "fragile", "idle", "configured"}:
        return "warning"
    if status in {"error", "degraded", "blocked", "fail"}:
        return "negative"
    return "secondary"


def _health_overview_cards(payload: dict[str, Any] | None) -> list[dict[str, str]]:
    if not payload:
        return []
    modules = payload.get("modules") or []
    runtime = payload.get("runtime_health") or {}
    data = payload.get("data_health") or {}
    return [
        {
            "title": "系统总体",
            "value": str(payload.get("status", "unknown")).upper(),
            "detail": f"模式: {payload.get('service_mode', 'unknown')} | 更新时间: {payload.get('timestamp', 'unknown')}",
            "color": _health_status_color(str(payload.get("status", "unknown"))),
        },
        {
            "title": "模块状态",
            "value": f"{sum(1 for item in modules if item.get('status') == 'ok')} 正常 / {sum(1 for item in modules if item.get('status') == 'warning')} 警告 / {sum(1 for item in modules if item.get('status') == 'error')} 错误",
            "detail": "平台模块、依赖和关键链路的当前状态汇总。",
            "color": "secondary",
        },
        {
            "title": "运行稳定性",
            "value": str(runtime.get("status", "unknown")).upper(),
            "detail": str(runtime.get("note", "当前还没有长期运行结论。")),
            "color": _health_status_color(str(runtime.get("status", "unknown"))),
        },
        {
            "title": "数据健康",
            "value": str(data.get("status", "unknown")).upper(),
            "detail": str(data.get("note", "当前还没有数据健康结论。")),
            "color": _health_status_color(str(data.get("status", "unknown"))),
        },
    ]


def _health_attention_lines(payload: dict[str, Any] | None) -> list[str]:
    if not payload:
        return []
    lines: list[str] = []
    for item in payload.get("modules") or []:
        if item.get("status") in {"warning", "error"}:
            lines.append(f"模块 {item.get('name', 'unknown')}: {item.get('detail', '无详情')}")
    for item in payload.get("libraries") or []:
        if item.get("status") in {"warning", "error"}:
            lines.append(f"依赖 {item.get('name', 'unknown')}: {item.get('detail', '无详情')}")
    runtime = payload.get("runtime_health") or {}
    for key, label in (
        ("research", "研究链路"),
        ("repair", "修复链路"),
        ("terminal", "终端链路"),
        ("data", "数据链路"),
        ("llm", "LLM 链路"),
    ):
        section = runtime.get(key) or {}
        if section.get("status") in {"warning", "fragile", "error", "blocked"}:
            lines.append(f"{label}: {section.get('note', '无说明')}")
    if not lines:
        lines.append("当前没有明显的高优先级异常，整体处于可继续工作的状态。")
    return lines[:16]


def _health_action_lines(payload: dict[str, Any] | None) -> list[str]:
    if not payload:
        return []
    actions: list[str] = []
    runtime = payload.get("runtime_health") or {}
    recovery = runtime.get("runtime_recovery_summary") or {}
    actions.extend(recovery.get("actions") or [])
    actions.extend(runtime.get("recommended_actions") or [])
    for key in ("research", "repair", "terminal", "data", "llm"):
        section = runtime.get(key) or {}
        actions.extend(section.get("recovery_actions") or [])
        if section.get("next_action"):
            actions.append(str(section["next_action"]))
    deduped: list[str] = []
    seen: set[str] = set()
    for item in actions:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped[:12]


def _health_people_runtime_lines(payload: dict[str, Any] | None) -> list[str]:
    if not payload:
        return []
    runtime = payload.get("runtime_health") or {}
    data = payload.get("data_health") or {}
    modules = payload.get("modules") or []
    return [
        f"现在适不适合继续用: {str(runtime.get('status', payload.get('status', 'unknown'))).upper()}",
        f"运行判断: {runtime.get('note', '无')}",
        f"数据判断: {data.get('note', '无')}",
        f"关键阻塞: {', '.join((runtime.get('runtime_recovery_summary') or {}).get('blockers') or []) or '无'}",
        f"模块异常数: {sum(1 for item in modules if item.get('status') == 'error')} 错误 / {sum(1 for item in modules if item.get('status') == 'warning')} 警告",
    ]


def _health_problem_group_lines(payload: dict[str, Any] | None, group: str) -> list[str]:
    if not payload:
        return []
    mapping = {
        "modules": ("modules", "模块"),
        "libraries": ("libraries", "依赖"),
        "agents": ("agents", "Agent"),
    }
    key, label = mapping[group]
    items = payload.get(key) or []
    lines = []
    for item in items:
        status = item.get("status", "unknown")
        if status == "ok":
            continue
        name = item.get("name") or item.get("agent") or "unknown"
        lines.append(f"{label} {name} / {status} / {item.get('detail') or item.get('last_detail') or '无详情'}")
        lines.append(f"处理建议 / {item.get('recommendation') or 'No action required.'}")
    return lines


def _validate_programmer_targets(targets: list[str]) -> tuple[bool, str, str]:
    if not targets:
        return False, "warning", "请先填写目标文件。默认应只提交策略文件或明确授权的生成目录。"
    protected_hits = [item for item in targets if any(item == prefix or item.startswith(prefix) for prefix in PROGRAMMER_PROTECTED_PREFIXES)]
    if protected_hits:
        return False, "negative", f"目标文件触碰受保护边界：{', '.join(protected_hits)}。不允许直接修改指标引擎、回测边界或工作流评估逻辑。"
    out_of_scope = [item for item in targets if not any(item.startswith(prefix) for prefix in PROGRAMMER_ALLOWED_PREFIXES)]
    if out_of_scope:
        return False, "negative", f"目标文件超出默认 Programmer Agent 范围：{', '.join(out_of_scope)}。请把修改收敛到策略目录或明确授权的生成目录。"
    if all(item.startswith("tests/") for item in targets):
        return True, "warning", "当前目标只有测试文件。测试应服务于暴露真实问题，不应单独修改测试来绕开实现缺陷。"
    return True, "positive", f"目标范围已收敛到 {len(targets)} 个文件。默认仍会拦截越权改动和受保护边界改动。"


def _default_behavior_events() -> list[dict[str, Any]]:
    return [
        {
            "scenario_id": "bootstrap-drawdown-1",
            "price_drawdown_pct": -4.2,
            "action": "hold",
            "noise_level": 0.82,
            "sentiment_pressure": 0.74,
            "latency_seconds": 210,
            "execution_status": "hold",
            "execution_reason": "Observed news-driven selloff and waited.",
        },
        {
            "scenario_id": "bootstrap-breakout-1",
            "price_drawdown_pct": 1.1,
            "action": "buy",
            "noise_level": 0.36,
            "sentiment_pressure": 0.42,
            "latency_seconds": 85,
            "execution_status": "filled",
            "execution_reason": "Entered after price and volume confirmation.",
        },
        {
            "scenario_id": "bootstrap-gapdown-1",
            "price_drawdown_pct": -6.8,
            "action": "sell",
            "noise_level": 0.67,
            "sentiment_pressure": 0.58,
            "latency_seconds": 52,
            "execution_status": "filled",
            "execution_reason": "Reduced exposure after risk limit breach.",
        },
        {
            "scenario_id": "bootstrap-fade-1",
            "price_drawdown_pct": -2.0,
            "action": "buy",
            "noise_level": 0.48,
            "sentiment_pressure": 0.33,
            "latency_seconds": 130,
            "execution_status": "partial_fill",
            "execution_reason": "Scaled in but liquidity was limited.",
        },
    ]


def run() -> None:
    if ui is None:
        raise ModuleNotFoundError("NiceGUI is not installed. Add dependencies from pyproject.toml and reinstall the project before running the NiceGUI WebUI.")
    if nicegui_run is not None:
        original_setup = nicegui_run.setup

        def _safe_setup() -> None:
            try:
                original_setup()
            except PermissionError:
                nicegui_run.process_pool = None

        nicegui_run.setup = _safe_setup

    settings = get_settings()
    api_base = f"http://{settings.api_host}:{settings.api_port}"
    repo_root = Path(settings.config_path).resolve().parents[1]

    def _resolved_local_root(config_path_value: str, fallback: str) -> Path:
        path = Path(str(config_path_value or fallback))
        if not path.is_absolute():
            path = (repo_root / path).resolve()
        return path

    local_market_root = _resolved_local_root(
        str(settings.market_data_provider_configs.get("local_file", {}).get("base_path", "data/local_market_data/market_data")),
        "data/local_market_data/market_data",
    )
    local_fundamentals_root = _resolved_local_root(
        str(settings.fundamentals_provider_configs.get("local_file", {}).get("base_path", "data/local_market_data/fundamentals")),
        "data/local_market_data/fundamentals",
    )
    local_dark_pool_root = _resolved_local_root(
        str(settings.dark_pool_provider_configs.get("local_file", {}).get("base_path", "data/local_market_data/dark_pool")),
        "data/local_market_data/dark_pool",
    )
    local_options_root = _resolved_local_root(
        str(settings.options_provider_configs.get("local_file", {}).get("base_path", "data/local_market_data/options")),
        "data/local_market_data/options",
    )
    state = UiState()
    session_actions: list[Any] = []
    strategy_actions: list[Any] = []
    simulation_actions: list[Any] = []
    preferences_actions: list[Any] = []
    intelligence_actions: list[Any] = []
    config_actions: list[Any] = []
    data_source_actions: list[Any] = []
    terminal_actions: list[Any] = []
    operations_actions: list[Any] = []
    session_note = None
    strategy_note = None
    simulation_note = None
    preferences_note = None
    intelligence_note = None
    config_note = None
    data_source_note = None
    terminal_note = None
    operations_note = None
    session_spinner = None
    strategy_spinner = None
    simulation_spinner = None
    preferences_spinner = None
    intelligence_spinner = None
    config_spinner = None
    data_source_spinner = None
    terminal_spinner = None
    operations_spinner = None

    ui.colors(primary="#1f5551", secondary="#c85c3f", accent="#7c2f1c", positive="#1f5551", negative="#7c2f1c")
    ui.query("body").classes("bg-slate-50 text-slate-900")

    def render_list_card(container, *, title: str, lines: list[str], empty: str) -> None:
        with container:
            with ui.card().classes("w-full"):
                ui.label(title).classes("text-h6")
                ui.markdown(_lines_markdown(lines, empty)).classes("w-full")

    def render_code_card(container, *, title: str, code: str) -> None:
        with container:
            with ui.card().classes("w-full"):
                ui.label(title).classes("text-h6")
                ui.code(code, language="python").classes("w-full text-sm")

    def render_json_card(container, *, title: str, payload: Any) -> None:
        with container:
            with ui.card().classes("w-full"):
                ui.label(title).classes("text-h6")
                ui.code(_pretty(payload), language="json").classes("w-full text-sm")

    def render_chart_card(container, *, title: str, option: dict[str, Any] | None, empty: str) -> None:
        with container:
            with ui.card().classes("w-full"):
                ui.label(title).classes("text-h6")
                if option is None:
                    ui.markdown(empty).classes("w-full")
                else:
                    ui.echart(option).classes("w-full").style("height: 320px;")

    def populate_select_options(select, options: dict[str, str], fallback: str = "") -> None:
        select.options = options
        select.update()
        if select.value not in options:
            select.value = fallback or (next(iter(options)) if options else None)
            select.update()

    def append_strategy_log(message: str) -> None:
        state.local_strategy_logs.append(message)
        state.local_strategy_logs[:] = state.local_strategy_logs[-20:]

    def append_simulation_log(message: str) -> None:
        state.local_simulation_logs.append(message)
        state.local_simulation_logs[:] = state.local_simulation_logs[-20:]

    def append_operation_log(message: str) -> None:
        state.local_operation_logs.append(message)
        state.local_operation_logs[:] = state.local_operation_logs[-30:]

    def _parse_watchlist(raw_value: str | None) -> list[str]:
        return [item.strip().upper() for item in (raw_value or "").replace("\n", ",").split(",") if item.strip()]

    def _resolve_intelligence_symbols(snapshot: dict[str, Any] | None, query: str | None = None) -> list[str]:
        trade_universe = (snapshot or {}).get("trade_universe") or {}
        symbols = [
            item.strip().upper()
            for item in ((trade_universe.get("requested") or []) or (trade_universe.get("expanded") or []))
            if item
        ]
        if symbols:
            return symbols[:8]
        inferred = _infer_symbol_from_query(query)
        return [inferred] if inferred and inferred != "UNKNOWN" else []

    async def _auto_enrich_market_data(symbols: list[str]) -> tuple[dict[str, Any] | None, list[str]]:
        latest_snapshot = state.snapshot
        completed: list[str] = []
        for symbol in symbols:
            try:
                latest_snapshot = await _call_api(
                    "POST",
                    api_base,
                    f"/api/sessions/{state.session_id}/intelligence/financials",
                    {"symbol": symbol, "provider": None},
                )
                latest_snapshot = await _call_api(
                    "POST",
                    api_base,
                    f"/api/sessions/{state.session_id}/intelligence/dark-pool",
                    {"symbol": symbol, "provider": None},
                )
                latest_snapshot = await _call_api(
                    "POST",
                    api_base,
                    f"/api/sessions/{state.session_id}/intelligence/options",
                    {"symbol": symbol, "provider": None, "expiration": None},
                )
                completed.append(symbol)
            except Exception:
                continue
        return latest_snapshot, completed

    def _set_action_state(actions: list[Any], spinner: Any, active: bool) -> None:
        for action in actions:
            action.disable() if active else action.enable()
        if spinner is not None:
            spinner.visible = active
            spinner.update()

    async def ensure_strategy_prerequisites() -> dict[str, Any]:
        if not state.session_id:
            raise RuntimeError("请先创建或加载会话。")
        snapshot = state.snapshot or {}
        symbols = [item.strip().upper() for item in (universe_symbols.value or "").split(",") if item.strip()]
        if not symbols:
            symbols = ["TSLA", "NVDA", "QQQ"]
            universe_symbols.value = ",".join(symbols)
            universe_symbols.update()
        if snapshot.get("trade_universe") is None:
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/trade-universe",
                {"input_type": universe_type.value, "symbols": symbols, "allow_overfit_override": False},
            )
            append_strategy_log(f"自动补齐交易标的: {', '.join(symbols)}")
        if snapshot.get("behavioral_report") is None:
            for event in _default_behavior_events():
                snapshot = await _call_api(
                    "POST",
                    api_base,
                    f"/api/sessions/{state.session_id}/simulation/events",
                    event,
                )
            last_error: Exception | None = None
            for attempt in range(3):
                try:
                    snapshot = await _call_api(
                        "POST",
                        api_base,
                        f"/api/sessions/{state.session_id}/simulation/complete",
                        {"symbol": symbols[0]},
                    )
                    break
                except Exception as exc:  # pragma: no cover - transient network / LLM failure path
                    last_error = exc
                    if attempt == 2:
                        raise
                    append_strategy_log(f"行为画像生成出现瞬时失败，准备重试 ({attempt + 1}/3): {exc}")
                    await asyncio.sleep(1.5)
            if last_error and snapshot.get("behavioral_report") is None:
                raise last_error
            append_strategy_log("自动补齐行为画像与模拟交易报告。")
        if snapshot.get("trading_preferences") is None:
            report = snapshot.get("behavioral_report") or {}
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/trading-preferences",
                {
                    "trading_frequency": report.get("recommended_trading_frequency") or "medium",
                    "preferred_timeframe": report.get("recommended_timeframe") or "daily",
                    "rationale": "Auto-bootstrap from NiceGUI training workspace.",
                },
            )
            append_strategy_log("自动补齐交易偏好。")
        state.snapshot = snapshot
        return snapshot

    async def load_config_state(show_notify: bool = False) -> None:
        payload = await _call_api("GET", api_base, "/api/config")
        state.config_payload = payload.get("payload") or {}
        state.config_validation = payload.get("validation") or {}
        state.config_test_result = payload
        config_editor.value = _pretty(state.config_payload)
        config_editor.update()
        if show_notify:
            ui.notify("配置已加载。", color="positive")

    def _config_editor_payload() -> dict[str, Any]:
        raw = (config_editor.value or "").strip()
        if not raw:
            raise RuntimeError("配置编辑器为空。")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"配置 JSON 解析失败: {exc}") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("配置根对象必须是 JSON object。")
        return parsed

    async def create_session() -> None:
        _set_action_state(session_actions, session_spinner, True)
        session_note.text = "会话创建与训练前置补齐进行中，请稍候..."
        try:
            payload = {"user_name": user_name.value, "starting_capital": float(starting_capital.value or 100000)}
            snapshot = await _call_api("POST", api_base, "/api/sessions", payload)
            state.session_id = str(snapshot.get("session_id") or "")
            state.snapshot = snapshot
            session_id_input.value = state.session_id
            snapshot = await ensure_strategy_prerequisites()
            state.snapshot = snapshot
            session_note.text = "会话已创建并补齐训练前置条件。"
            ui.notify(f"会话已创建: {state.session_id}", color="positive")
            refresh_all()
        except Exception as exc:  # pragma: no cover - UI feedback path
            session_note.text = f"创建会话失败: {exc}"
            ui.notify(f"创建会话失败: {exc}", color="negative")
        finally:
            _set_action_state(session_actions, session_spinner, False)

    async def load_session() -> None:
        session_id = (session_id_input.value or "").strip()
        if not session_id:
            ui.notify("请输入 session_id", color="warning")
            return
        _set_action_state(session_actions, session_spinner, True)
        session_note.text = "会话加载中，请稍候..."
        try:
            snapshot = await _call_api("GET", api_base, f"/api/sessions/{session_id}")
            state.session_id = session_id
            state.snapshot = snapshot
            session_note.text = "会话已加载。"
            ui.notify("会话已加载", color="positive")
            refresh_all()
        except Exception as exc:  # pragma: no cover - UI feedback path
            session_note.text = f"加载会话失败: {exc}"
            ui.notify(f"加载会话失败: {exc}", color="negative")
        finally:
            _set_action_state(session_actions, session_spinner, False)

    async def reload_config() -> None:
        _set_action_state(config_actions, config_spinner, True)
        config_note.text = "配置加载中，请稍候..."
        try:
            await load_config_state()
            config_note.text = "配置已加载。"
        except Exception as exc:  # pragma: no cover
            config_note.text = f"配置加载失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(config_actions, config_spinner, False)

    async def save_config() -> None:
        _set_action_state(config_actions, config_spinner, True)
        config_note.text = "配置保存中，请稍候..."
        try:
            payload = _config_editor_payload()
            result = await _call_api("POST", api_base, "/api/config", {"payload": payload})
            state.config_payload = result.get("payload") or payload
            state.config_validation = result.get("validation") or {}
            state.config_test_result = result
            config_editor.value = _pretty(state.config_payload)
            config_editor.update()
            config_note.text = "配置已保存。"
        except Exception as exc:  # pragma: no cover
            config_note.text = f"配置保存失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(config_actions, config_spinner, False)

    async def test_config() -> None:
        _set_action_state(config_actions, config_spinner, True)
        config_note.text = "配置全量测试中，请稍候..."
        try:
            payload = _config_editor_payload()
            result = await _call_api("POST", api_base, "/api/config/test", {"payload": payload})
            state.config_test_result = result
            state.config_validation = result.get("validation") or {}
            config_note.text = "配置全量测试已完成。"
        except Exception as exc:  # pragma: no cover
            config_note.text = f"配置全量测试失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(config_actions, config_spinner, False)

    async def test_config_item() -> None:
        _set_action_state(config_actions, config_spinner, True)
        config_note.text = "单项配置测试中，请稍候..."
        try:
            payload = _config_editor_payload()
            result = await _call_api(
                "POST",
                api_base,
                "/api/config/test-item",
                {
                    "payload": payload,
                    "family": config_test_family.value,
                    "provider": (config_test_provider.value or "").strip() or None,
                },
            )
            state.config_test_result = result
            config_note.text = "单项配置测试已完成。"
        except Exception as exc:  # pragma: no cover
            config_note.text = f"单项配置测试失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(config_actions, config_spinner, False)

    async def submit_universe() -> None:
        if not state.session_id:
            ui.notify("请先创建或加载会话", color="warning")
            return
        symbols = [item.strip().upper() for item in (universe_symbols.value or "").split(",") if item.strip()]
        try:
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/trade-universe",
                {"input_type": universe_type.value, "symbols": symbols, "allow_overfit_override": False},
            )
            state.snapshot = snapshot
            append_strategy_log(f"已提交交易标的: {', '.join(symbols) or 'none'}")
            strategy_note.text = "交易标的已更新。"
            refresh_all()
        except Exception as exc:  # pragma: no cover - UI feedback path
            strategy_note.text = f"提交交易标的失败: {exc}"
            ui.notify(str(exc), color="negative")

    async def run_strategy_iteration() -> None:
        if not state.session_id:
            ui.notify("请先创建或加载会话", color="warning")
            return
        validation_lines, validation_errors = _strategy_input_validation_lines(
            training_start_value=training_start.value,
            training_end_value=training_end.value,
            target_return_value=target_return.value,
            target_win_rate_value=target_win_rate.value,
            target_drawdown_value=target_drawdown.value,
            target_max_loss_value=target_max_loss.value,
        )
        if validation_errors:
            strategy_note.text = "训练参数校验失败： " + "；".join(validation_errors)
            refresh_all()
            return
        _set_action_state(strategy_actions, strategy_spinner, True)
        try:
            await ensure_strategy_prerequisites()
        except Exception as exc:  # pragma: no cover - UI feedback path
            strategy_note.text = f"补齐训练前置条件失败: {exc}"
            ui.notify(str(exc), color="negative")
            _set_action_state(strategy_actions, strategy_spinner, False)
            return
        payload = {
            "feedback": strategy_feedback.value,
            "strategy_type": strategy_type.value,
            "auto_iterations": int(auto_iterations.value or 1),
            "iteration_mode": iteration_mode.value,
            "objective_metric": objective_metric.value,
            "target_return_pct": float(target_return.value or 18),
            "target_win_rate_pct": float(target_win_rate.value or 58),
            "target_drawdown_pct": float(target_drawdown.value or 12),
            "target_max_loss_pct": float(target_max_loss.value or 6),
            "training_start_date": training_start.value or None,
            "training_end_date": training_end.value or None,
        }
        strategy_note.text = "策略训练进行中，请稍候..."
        try:
            snapshot = await _call_api("POST", api_base, f"/api/sessions/{state.session_id}/strategy/iterate", payload)
            state.snapshot = snapshot
            append_strategy_log("策略训练已完成。")
            strategy_note.text = "策略训练已完成。"
            ui.notify("策略训练已完成", color="positive")
            refresh_all()
        except Exception as exc:  # pragma: no cover - UI feedback path
            detail = str(exc)
            if "Data Source Expansion workbench" in detail or "Data Source Expansion" in detail:
                strategy_note.text = (
                    "策略训练失败：真实股票数据不足或缺失。请进入“数据源扩展”工作台，提供 API KEY 与接口文档，"
                    "让系统生成并接入真实数据源后，再重新训练。"
                )
            else:
                strategy_note.text = f"策略训练失败: {detail}"
            append_strategy_log(f"策略训练失败: {exc}")
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(strategy_actions, strategy_spinner, False)

    async def expand_data_source_run() -> None:
        if not state.session_id:
            data_source_note.text = "请先创建或加载会话。"
            ui.notify("请先创建或加载会话", color="warning")
            return
        _set_action_state(data_source_actions, data_source_spinner, True)
        data_source_note.text = "数据源扩展方案生成中，请稍候..."
        try:
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/data-source/expand",
                {
                    "api_key": data_source_api_key.value or None,
                    "interface_documentation": data_source_interface_documentation.value or "",
                },
            )
            state.snapshot = snapshot
            latest_run = _latest(snapshot.get("data_source_runs") or [])
            inference = latest_run.get("inference") or {}
            analysis = latest_run.get("analysis") or {}
            generation_mode = analysis.get("generation_mode", "unknown")
            analysis_status = analysis.get("analysis_status", "unknown")
            fallback_reason = analysis.get("fallback_reason")
            local_paths = latest_run.get("local_registry_paths") or []
            data_source_note.text = (
                f"数据源扩展方案已生成。analysis={generation_mode} / status={analysis_status} / "
                f"{latest_run.get('provider_name', 'provider')} / "
                f"{inference.get('category', latest_run.get('category', 'unknown'))} / "
                f"{inference.get('auth_style', 'unknown')}"
                + (f" / fallback={fallback_reason}" if fallback_reason else "")
                + (f" / saved={local_paths[0]}" if local_paths else "")
                + "。"
            )
            refresh_all()
        except Exception as exc:  # pragma: no cover
            data_source_note.text = f"数据源扩展方案生成失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(data_source_actions, data_source_spinner, False)

    async def apply_data_source_run() -> None:
        if not state.session_id:
            data_source_note.text = "请先创建或加载会话。"
            ui.notify("请先创建或加载会话", color="warning")
            return
        _set_action_state(data_source_actions, data_source_spinner, True)
        data_source_note.text = "数据源扩展写入工作区中，请稍候..."
        try:
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/data-source/apply",
                {
                    "run_id": data_source_run_select.value or None,
                    "commit_changes": bool(data_source_commit.value),
                },
            )
            state.snapshot = snapshot
            latest_apply = _latest(snapshot.get("programmer_runs") or [])
            apply_status = latest_apply.get("status", "unknown")
            local_paths = latest_apply.get("local_registry_paths") or []
            if apply_status == "dry_run":
                data_source_note.text = (
                    "数据源扩展 dry-run 已完成，当前只生成方案与应用预演，没有写入工作区。"
                    + (f" 本地清单: {local_paths[0]}。" if local_paths else "")
                )
            else:
                data_source_note.text = f"数据源扩展已提交，status={apply_status}。" + (f" 本地清单: {local_paths[0]}。" if local_paths else "")
            refresh_all()
        except Exception as exc:  # pragma: no cover
            data_source_note.text = f"数据源扩展应用失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(data_source_actions, data_source_spinner, False)

    async def test_data_source_run() -> None:
        if not state.session_id:
            data_source_note.text = "请先创建或加载会话。"
            ui.notify("请先创建或加载会话", color="warning")
            return
        _set_action_state(data_source_actions, data_source_spinner, True)
        data_source_note.text = "数据源扩展 smoke test 运行中，请稍候..."
        try:
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/data-source/test",
                {
                    "run_id": data_source_run_select.value or None,
                    "symbol": data_source_test_symbol.value or "AAPL",
                    "api_key": data_source_api_key.value or None,
                },
            )
            state.snapshot = snapshot
            latest_run = _selected_run(snapshot.get("data_source_runs") or [], data_source_run_select.value) or _latest(snapshot.get("data_source_runs") or [])
            smoke = latest_run.get("smoke_test") or {}
            live = smoke.get("live_fetch") or {}
            local_paths = smoke.get("local_registry_paths") or []
            data_source_note.text = (
                f"数据源扩展 smoke test 已完成。status={smoke.get('status', 'unknown')} / "
                f"live={live.get('status', 'unknown')} / class={live.get('classification', 'unknown')} / "
                f"{live.get('detail', 'no detail')} / 建议: {live.get('next_action', '无')}"
                + (f" / 本地清单={local_paths[0]}" if local_paths else "")
            )
            refresh_all()
        except Exception as exc:  # pragma: no cover
            data_source_note.text = f"数据源扩展 smoke test 失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(data_source_actions, data_source_spinner, False)

    async def approve_strategy() -> None:
        if not state.session_id:
            ui.notify("请先创建或加载会话", color="warning")
            return
        try:
            snapshot = await _call_api("POST", api_base, f"/api/sessions/{state.session_id}/strategy/approve")
            state.snapshot = snapshot
            append_strategy_log("当前策略已确认。")
            strategy_note.text = "当前策略已确认。"
            refresh_all()
        except Exception as exc:  # pragma: no cover - UI feedback path
            strategy_note.text = f"确认当前策略失败: {exc}"
            ui.notify(str(exc), color="negative")

    def apply_repair_feedback() -> None:
        routes = _build_repair_routes(state.snapshot)
        if not routes:
            strategy_note.text = "当前没有可回填的修复反馈。"
            return
        strategy_feedback.value = " | ".join(f"{item['lane']}: {item['summary']} 动作: {'；'.join(item['actions'])}" for item in routes[:2])
        strategy_feedback.update()
        strategy_note.text = "已将修复路由回填到训练反馈。"

    def apply_repair_programmer() -> None:
        routes = _build_repair_routes(state.snapshot)
        if not routes:
            strategy_note.text = "当前没有可回填的修复指令。"
            return
        primary = routes[0]
        programmer_instruction.value = f"按{primary['lane']}优先修复当前策略相关代码，重点：{'；'.join(primary['actions'])}。保持现有风控结构、版本规则和输出契约不变。"
        programmer_context.value = f"{primary['summary']} 最近优先级={primary['priority']} / 来源={primary['source']}。如涉及检查失败，先修复对应 required_fix_actions，再重新运行 compile 与 pytest。"
        programmer_instruction.update()
        programmer_context.update()
        refresh_programmer_scope()
        strategy_note.text = "已将修复路由回填到 Programmer Agent。"

    async def continue_auto_training() -> None:
        iteration_mode.value = "guided"
        if int(auto_iterations.value or 1) < 3:
            auto_iterations.value = 3
            auto_iterations.update()
        iteration_mode.update()
        await run_strategy_iteration()

    def prepare_manual_intervention() -> None:
        iteration_mode.value = "free"
        iteration_mode.update()
        strategy_feedback.props("autofocus")
        strategy_note.text = "已切换到人工介入模式。先补充你的意见，再点击“生成下一版策略”。"

    async def search_intelligence() -> None:
        if not state.session_id:
            intelligence_note.text = "请先创建或加载会话，然后再查询情报。"
            ui.notify("请先创建或加载会话", color="warning")
            return
        query = (intelligence_query.value or "").strip()
        if not query:
            intelligence_note.text = "请输入搜索词。"
            return
        _set_action_state(intelligence_actions, intelligence_spinner, True)
        intelligence_note.text = "情报搜索进行中，请稍候..."
        try:
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/intelligence/search",
                {"query": query, "max_documents": int(intelligence_max.value or 5)},
            )
            symbols = _resolve_intelligence_symbols(snapshot, query)
            enriched_snapshot, enriched_symbols = await _auto_enrich_market_data(symbols)
            if enriched_snapshot is not None:
                snapshot = enriched_snapshot
            state.snapshot = snapshot
            run = _latest(snapshot.get("intelligence_runs"))
            cache_text = "命中缓存" if run.get("cache_hit") else "已完成"
            enrichment_text = f" 已自动补充 {', '.join(enriched_symbols)} 的财报、暗池和期权数据。" if enriched_symbols else ""
            intelligence_note.text = f"情报搜索{cache_text}。{enrichment_text}".strip()
            refresh_all()
        except Exception as exc:  # pragma: no cover - UI feedback path
            intelligence_note.text = f"情报搜索失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(intelligence_actions, intelligence_spinner, False)

    async def search_watchlist_intelligence() -> None:
        if not state.session_id:
            intelligence_note.text = "请先创建或加载会话，然后再查询当前股票列表情报。"
            ui.notify("请先创建或加载会话", color="warning")
            return
        symbols = _resolve_intelligence_symbols(state.snapshot, intelligence_query.value)
        if not symbols:
            intelligence_note.text = "当前会话还没有股票列表。先在策略页提交交易标的，或在查询里直接写股票代码。"
            return
        template = (intelligence_query.value or "latest market news risks catalysts").strip()
        if "{symbol}" not in template:
            template = "{symbol} " + template
        _set_action_state(intelligence_actions, intelligence_spinner, True)
        intelligence_note.text = f"正在批量查询 {len(symbols)} 个股票，请稍候..."
        completed: list[str] = []
        failed: list[str] = []
        try:
            latest_snapshot = state.snapshot
            for symbol in symbols:
                query = template.format(symbol=symbol)
                latest_snapshot = await _call_api(
                    "POST",
                    api_base,
                    f"/api/sessions/{state.session_id}/intelligence/search",
                    {"query": query, "max_documents": int(intelligence_max.value or 5)},
                )
                run = _latest((latest_snapshot or {}).get("intelligence_runs"))
                if run.get("status") == "error":
                    failed.append(symbol)
                else:
                    completed.append(symbol)
            if latest_snapshot is not None:
                latest_snapshot, enriched_symbols = await _auto_enrich_market_data(symbols)
            if latest_snapshot is not None:
                state.snapshot = latest_snapshot
            intelligence_note.text = (
                f"批量查询完成。成功 {len(completed)} 个，失败 {len(failed)} 个。"
                + (f" 已自动补充 {len(enriched_symbols)} 个股票的最新市场数据。" if 'enriched_symbols' in locals() and enriched_symbols else "")
                + (f" 失败列表: {', '.join(failed)}" if failed else "")
            )
            refresh_all()
        except Exception as exc:  # pragma: no cover - UI feedback path
            intelligence_note.text = f"批量情报查询失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(intelligence_actions, intelligence_spinner, False)

    def apply_preference_recommendation() -> None:
        report = (state.snapshot or {}).get("behavioral_user_report") or (state.snapshot or {}).get("behavioral_report") or {}
        if report.get("report_generation_mode") != "live_llm":
            preferences_note.text = report.get("analysis_warning") or "当前只有规则统计，不自动应用为智能推荐。"
            return
        if not report.get("recommended_trading_frequency"):
            preferences_note.text = "当前还没有可应用的测试推荐。"
            return
        preference_frequency.value = report.get("recommended_trading_frequency") or preference_frequency.value
        preference_timeframe.value = report.get("recommended_timeframe") or preference_timeframe.value
        preference_rationale.value = report.get("trading_preference_recommendation_note") or preference_rationale.value
        preference_frequency.update()
        preference_timeframe.update()
        preference_rationale.update()
        preferences_note.text = report.get("trading_preference_recommendation_note") or "已应用测试推荐。"

    async def save_preferences() -> None:
        if not state.session_id:
            ui.notify("请先创建或加载会话", color="warning")
            return
        _set_action_state(preferences_actions, preferences_spinner, True)
        preferences_note.text = "交易偏好保存中，请稍候..."
        try:
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/trading-preferences",
                {
                    "trading_frequency": preference_frequency.value,
                    "preferred_timeframe": preference_timeframe.value,
                    "rationale": preference_rationale.value or None,
                },
            )
            state.snapshot = snapshot
            preferences_note.text = "交易偏好已保存。"
            refresh_all()
        except Exception as exc:  # pragma: no cover - UI feedback path
            preferences_note.text = f"保存交易偏好失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(preferences_actions, preferences_spinner, False)

    async def add_simulation_event() -> None:
        if not state.session_id:
            ui.notify("请先创建或加载会话", color="warning")
            return
        _set_action_state(simulation_actions, simulation_spinner, True)
        simulation_note.text = "行为事件提交中，请稍候..."
        try:
            market = ((state.snapshot or {}).get("simulation_market") or {})
            active_symbol = (
                market.get("symbol")
                or (((state.snapshot or {}).get("trade_universe") or {}).get("symbols") or [None])[0]
                or "TSLA"
            )
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/simulation/events",
                {
                    "scenario_id": "simulation-market",
                    "action": simulation_action.value or "hold",
                    "symbol": active_symbol,
                },
            )
            state.snapshot = snapshot
            market = snapshot.get("simulation_market") or {}
            append_simulation_log(
                f"{market.get('symbol', active_symbol or 'SIM')} / {simulation_action.value} / {market.get('current_timestamp', 'unknown')} / drawdown={market.get('current_drawdown_pct', 'unknown')}"
            )
            simulation_note.text = "行为事件已追加。"
            refresh_all()
        except Exception as exc:  # pragma: no cover - UI feedback path
            simulation_note.text = f"追加行为事件失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(simulation_actions, simulation_spinner, False)

    async def record_simulation_action(action: str) -> None:
        simulation_action.value = action
        simulation_action.update()
        await add_simulation_event()

    async def initialize_simulation_market_run() -> None:
        if not state.session_id:
            ui.notify("请先创建或加载会话", color="warning")
            return
        snapshot = state.snapshot or {}
        market = snapshot.get("simulation_market") or {}
        trade_universe = snapshot.get("trade_universe") or {}
        symbols = trade_universe.get("symbols") or []
        symbol = (
            (market.get("symbol") or "").strip().upper()
            or (symbols[0].strip().upper() if symbols else "")
            or "TSLA"
        )
        _set_action_state(simulation_actions, simulation_spinner, True)
        simulation_note.text = "模拟市场加载中，请稍候..."
        try:
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/simulation/market/initialize",
                {
                    "symbol": symbol,
                    "daily_lookback": "6mo",
                    "intraday_lookback": "5d",
                    "intraday_interval": "5m",
                },
            )
            state.snapshot = snapshot
            market = snapshot.get("simulation_market") or {}
            current = market.get("current_bar") or {}
            simulation_drawdown.value = float(market.get("current_drawdown_pct") or 0.0)
            simulation_drawdown.update()
            append_simulation_log(f"{symbol} / market_initialized / {current.get('timestamp', 'unknown')}")
            simulation_note.text = "模拟市场已加载，可以查看日线图、5 分钟线图并按时间推进。"
            refresh_all()
        except Exception as exc:  # pragma: no cover - UI feedback path
            simulation_note.text = f"模拟市场初始化失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(simulation_actions, simulation_spinner, False)

    async def advance_simulation_market_run() -> None:
        if not state.session_id:
            ui.notify("请先创建或加载会话", color="warning")
            return
        _set_action_state(simulation_actions, simulation_spinner, True)
        simulation_note.text = "模拟时钟推进中，请稍候..."
        try:
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/simulation/market/advance",
                {"steps": 1},
            )
            state.snapshot = snapshot
            market = snapshot.get("simulation_market") or {}
            current = market.get("current_bar") or {}
            simulation_drawdown.value = float(market.get("current_drawdown_pct") or 0.0)
            simulation_drawdown.update()
            append_simulation_log(
                f"{market.get('symbol', 'SIM')} / advanced / {current.get('timestamp', 'unknown')} / close={current.get('close', 'unknown')}"
            )
            simulation_note.text = "模拟时钟已推进，图表与当前价格已刷新。"
            refresh_all()
        except Exception as exc:  # pragma: no cover - UI feedback path
            simulation_note.text = f"推进模拟时钟失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(simulation_actions, simulation_spinner, False)

    async def complete_simulation_run() -> None:
        if not state.session_id:
            ui.notify("请先创建或加载会话", color="warning")
            return
        market = ((state.snapshot or {}).get("simulation_market") or {})
        if not market:
            simulation_note.text = "请先加载模拟市场。"
            ui.notify("请先加载模拟市场", color="warning")
            return
        if int(market.get("cursor") or 0) <= 0:
            simulation_note.text = "请先推进模拟时钟，再生成行为画像。"
            ui.notify("请先推进模拟时钟", color="warning")
            return
        if not ((state.snapshot or {}).get("history_events") or []) or not any(
            item.get("event_type") == "behavior_event_recorded" for item in ((state.snapshot or {}).get("history_events") or [])
        ):
            simulation_note.text = "请先在市场推进过程中做至少一次买入、卖出或不交易。"
            ui.notify("请先记录至少一次用户动作", color="warning")
            return
        symbols = ((state.snapshot or {}).get("trade_universe") or {}).get("symbols") or []
        symbol = (market.get("symbol") or "").strip().upper() or (symbols[0].strip().upper() if symbols else "") or "TSLA"
        _set_action_state(simulation_actions, simulation_spinner, True)
        simulation_note.text = "模拟完成与行为画像生成中，请稍候..."
        try:
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/simulation/complete",
                {"symbol": symbol},
            )
            state.snapshot = snapshot
            append_simulation_log(f"{symbol} / completed")
            simulation_note.text = "行为画像已生成。"
            refresh_all()
        except Exception as exc:  # pragma: no cover - UI feedback path
            simulation_note.text = f"完成模拟失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(simulation_actions, simulation_spinner, False)

    async def refresh_market_data() -> None:
        if not state.session_id:
            intelligence_note.text = "请先创建或加载会话，然后再刷新最新市场数据。"
            ui.notify("请先创建或加载会话", color="warning")
            return
        symbols = _resolve_intelligence_symbols(state.snapshot, intelligence_query.value)
        if not symbols:
            intelligence_note.text = "当前没有可用股票列表。先提交交易标的，或在查询里带上股票代码。"
            return
        _set_action_state(intelligence_actions, intelligence_spinner, True)
        intelligence_note.text = f"正在刷新 {len(symbols)} 个股票的最新财报、暗池和期权数据..."
        try:
            snapshot, enriched_symbols = await _auto_enrich_market_data(symbols)
            if snapshot is not None:
                state.snapshot = snapshot
            intelligence_note.text = (
                f"最新市场数据刷新完成。"
                + (f" 已覆盖 {', '.join(enriched_symbols)}。" if enriched_symbols else "")
            )
            refresh_all()
        except Exception as exc:  # pragma: no cover - UI feedback path
            intelligence_note.text = f"刷新最新市场数据失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(intelligence_actions, intelligence_spinner, False)

    async def expand_terminal_run() -> None:
        if not state.session_id:
            terminal_note.text = "请先创建或加载会话。"
            ui.notify("请先创建或加载会话", color="warning")
            return
        _set_action_state(terminal_actions, terminal_spinner, True)
        terminal_note.text = "终端接入方案生成中，请稍候..."
        try:
            field_map_raw = (terminal_field_map.value or "").strip()
            field_map = json.loads(field_map_raw) if field_map_raw else None
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/terminal/expand",
                {
                    "terminal_name": terminal_name.value,
                    "terminal_type": terminal_type.value,
                    "official_docs_url": terminal_official_docs_url.value,
                    "docs_search_url": terminal_docs_search_url.value or None,
                    "api_base_url": terminal_api_base_url.value,
                    "api_key_envs": _parse_watchlist(terminal_api_key_envs.value),
                    "auth_style": terminal_auth_style.value,
                    "order_endpoint": terminal_order_endpoint.value,
                    "cancel_endpoint": terminal_cancel_endpoint.value,
                    "order_status_endpoint": terminal_order_status_endpoint.value,
                    "positions_endpoint": terminal_positions_endpoint.value,
                    "balances_endpoint": terminal_balances_endpoint.value,
                    "docs_summary": terminal_docs_summary.value,
                    "user_notes": terminal_user_notes.value or None,
                    "response_field_map": field_map,
                },
            )
            state.snapshot = snapshot
            terminal_note.text = "终端接入方案已生成。"
            refresh_all()
        except Exception as exc:  # pragma: no cover
            terminal_note.text = f"终端接入方案生成失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(terminal_actions, terminal_spinner, False)

    async def apply_terminal_run() -> None:
        if not state.session_id:
            terminal_note.text = "请先创建或加载会话。"
            ui.notify("请先创建或加载会话", color="warning")
            return
        _set_action_state(terminal_actions, terminal_spinner, True)
        terminal_note.text = "终端接入结果写入工作区中，请稍候..."
        try:
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/terminal/apply",
                {"run_id": terminal_run_select.value or None, "commit_changes": bool(terminal_commit.value)},
            )
            state.snapshot = snapshot
            latest_apply = _latest(snapshot.get("programmer_runs") or [])
            apply_status = latest_apply.get("status", "unknown")
            if apply_status == "dry_run":
                terminal_note.text = "终端接入 dry-run 已完成，当前只生成方案与应用预演，没有写入工作区。"
            else:
                terminal_note.text = f"终端接入结果已提交，status={apply_status}。"
            refresh_all()
        except Exception as exc:  # pragma: no cover
            terminal_note.text = f"终端接入应用失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(terminal_actions, terminal_spinner, False)

    async def test_terminal_run() -> None:
        if not state.session_id:
            terminal_note.text = "请先创建或加载会话。"
            ui.notify("请先创建或加载会话", color="warning")
            return
        _set_action_state(terminal_actions, terminal_spinner, True)
        terminal_note.text = "终端 smoke test 运行中，请稍候..."
        try:
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/terminal/test",
                {"run_id": terminal_run_select.value or None},
            )
            state.snapshot = snapshot
            terminal_note.text = "终端 smoke test 已完成。"
            refresh_all()
        except Exception as exc:  # pragma: no cover
            terminal_note.text = f"终端 smoke test 失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(terminal_actions, terminal_spinner, False)

    async def generate_operation_scenarios() -> None:
        if not state.session_id:
            operations_note.text = "请先创建或加载会话。"
            ui.notify("请先创建或加载会话", color="warning")
            return
        _set_action_state(operations_actions, operations_spinner, True)
        operations_note.text = "场景生成中，请稍候..."
        try:
            snapshot = await _call_api("POST", api_base, f"/api/sessions/{state.session_id}/generate-scenarios")
            state.snapshot = snapshot
            append_operation_log("已生成新一批场景。")
            operations_note.text = "场景已生成。"
            refresh_all()
        except Exception as exc:  # pragma: no cover
            operations_note.text = f"场景生成失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(operations_actions, operations_spinner, False)

    async def append_operation_market_snapshot() -> None:
        if not state.session_id:
            operations_note.text = "请先创建或加载会话。"
            ui.notify("请先创建或加载会话", color="warning")
            return
        _set_action_state(operations_actions, operations_spinner, True)
        operations_note.text = "市场快照写入中，请稍候..."
        try:
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/market-snapshots",
                {
                    "symbol": operation_market_symbol.value,
                    "timeframe": operation_market_timeframe.value,
                    "open_price": float(operation_market_open.value),
                    "high_price": float(operation_market_high.value),
                    "low_price": float(operation_market_low.value),
                    "close_price": float(operation_market_close.value),
                    "volume": float(operation_market_volume.value),
                    "source": operation_market_source.value,
                    "regime_tag": operation_market_regime.value or None,
                },
            )
            state.snapshot = snapshot
            append_operation_log(f"市场快照已写入: {operation_market_symbol.value}")
            operations_note.text = "市场快照已写入。"
            refresh_all()
        except Exception as exc:  # pragma: no cover
            operations_note.text = f"市场快照写入失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(operations_actions, operations_spinner, False)

    async def append_operation_information_event() -> None:
        if not state.session_id:
            operations_note.text = "请先创建或加载会话。"
            ui.notify("请先创建或加载会话", color="warning")
            return
        _set_action_state(operations_actions, operations_spinner, True)
        operations_note.text = "信息流事件写入中，请稍候..."
        try:
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/information-events",
                {
                    "events": [
                        {
                            "channel": operation_info_channel.value,
                            "source": operation_info_source.value,
                            "title": operation_info_title.value,
                            "body": operation_info_body.value,
                            "trading_day": operation_info_day.value or None,
                            "author": operation_info_author.value or None,
                            "handle": operation_info_handle.value or None,
                            "info_tag": operation_info_tag.value or None,
                            "sentiment_score": float(operation_info_sentiment.value),
                            "metadata": {},
                        }
                    ]
                },
            )
            state.snapshot = snapshot
            append_operation_log(f"信息流事件已写入: {operation_info_title.value}")
            operations_note.text = "信息流事件已写入。"
            refresh_all()
        except Exception as exc:  # pragma: no cover
            operations_note.text = f"信息流事件写入失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(operations_actions, operations_spinner, False)

    async def append_operation_trade_execution() -> None:
        if not state.session_id:
            operations_note.text = "请先创建或加载会话。"
            ui.notify("请先创建或加载会话", color="warning")
            return
        _set_action_state(operations_actions, operations_spinner, True)
        operations_note.text = "交易执行记录写入中，请稍候..."
        try:
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/trade-executions",
                {
                    "symbol": operation_trade_symbol.value,
                    "side": operation_trade_side.value,
                    "quantity": float(operation_trade_quantity.value),
                    "price": float(operation_trade_price.value),
                    "notional": float(operation_trade_notional.value),
                    "execution_mode": operation_trade_mode.value,
                    "strategy_version": operation_trade_strategy_version.value or None,
                    "realized_pnl_pct": float(operation_trade_pnl.value),
                    "user_initiated": True,
                    "note": operation_trade_note.value or None,
                },
            )
            state.snapshot = snapshot
            append_operation_log(f"交易执行记录已写入: {operation_trade_symbol.value} / {operation_trade_side.value}")
            operations_note.text = "交易执行记录已写入。"
            refresh_all()
        except Exception as exc:  # pragma: no cover
            operations_note.text = f"交易执行记录写入失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(operations_actions, operations_spinner, False)

    async def set_operation_deployment() -> None:
        if not state.session_id:
            operations_note.text = "请先创建或加载会话。"
            ui.notify("请先创建或加载会话", color="warning")
            return
        _set_action_state(operations_actions, operations_spinner, True)
        operations_note.text = "部署模式设置中，请稍候..."
        try:
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/deployment",
                {"execution_mode": operation_deployment_mode.value},
            )
            state.snapshot = snapshot
            append_operation_log(f"部署模式已切换到 {operation_deployment_mode.value}")
            operations_note.text = "部署模式已更新。"
            refresh_all()
        except Exception as exc:  # pragma: no cover
            operations_note.text = f"部署模式更新失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(operations_actions, operations_spinner, False)

    async def run_programmer_agent() -> None:
        if not state.session_id:
            ui.notify("请先创建或加载会话", color="warning")
            return
        targets = [item.strip() for item in (programmer_targets.value or "").split(",") if item.strip()]
        ok, _, message = _validate_programmer_targets(targets)
        if not ok:
            programmer_scope_note.text = message
            strategy_note.text = message
            return
        _set_action_state(strategy_actions, strategy_spinner, True)
        strategy_note.text = "Programmer Agent 执行中，请稍候..."
        try:
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/programmer/execute",
                {
                    "instruction": (programmer_instruction.value or "").strip(),
                    "target_files": targets,
                    "context": (programmer_context.value or "").strip(),
                    "commit_changes": True,
                },
            )
            state.snapshot = snapshot
            strategy_note.text = f"Programmer Agent 已执行，status={_latest(snapshot.get('programmer_runs')).get('status', 'unknown')}。"
            refresh_all()
        except Exception as exc:  # pragma: no cover - UI feedback path
            strategy_note.text = f"Programmer Agent 执行失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(strategy_actions, strategy_spinner, False)

    async def refresh_health(show_notify: bool = True) -> None:
        try:
            payload = await _call_api("GET", api_base, "/api/system-health")
            state.health_payload = payload
            health_overview_panel.clear()
            with health_overview_panel:
                grid = ui.grid(columns=2).classes("w-full gap-4")
                for card in _health_overview_cards(payload):
                    with grid:
                        with ui.card().classes("w-full"):
                            with ui.row().classes("w-full items-center justify-between"):
                                ui.label(card["title"]).classes("text-h6")
                                ui.badge(card["value"], color=card["color"])
                            ui.label(card["detail"]).classes("text-sm text-slate-600")
            health_summary_panel.clear()
            render_list_card(health_summary_panel, title="一句话结论", lines=_health_people_runtime_lines(payload), empty="当前还没有系统健康摘要。")
            health_attention_panel.clear()
            render_list_card(health_attention_panel, title="当前需要注意的问题", lines=_health_attention_lines(payload), empty="当前没有明显问题。")
            health_actions_panel.clear()
            render_list_card(health_actions_panel, title="建议你下一步做什么", lines=_health_action_lines(payload), empty="当前没有额外建议动作。")
            health_modules_panel.clear()
            render_list_card(health_modules_panel, title="异常模块", lines=_health_problem_group_lines(payload, "modules"), empty="当前没有模块级异常。")
            health_libraries_panel.clear()
            render_list_card(health_libraries_panel, title="异常依赖", lines=_health_problem_group_lines(payload, "libraries"), empty="当前没有依赖级异常。")
            health_agents_panel.clear()
            render_list_card(health_agents_panel, title="异常 Agent", lines=_health_problem_group_lines(payload, "agents"), empty="当前没有 Agent 级异常。")
            health_payload_panel.clear()
            render_json_card(health_payload_panel, title="系统健康 JSON", payload=payload)
            if show_notify:
                ui.notify("系统健康信息已刷新", color="positive")
        except Exception as exc:  # pragma: no cover - UI feedback path
            state.health_payload = None
            health_overview_panel.clear()
            health_summary_panel.clear()
            render_list_card(health_summary_panel, title="系统健康摘要", lines=[f"error / {exc}"], empty="系统健康检查失败。")
            health_attention_panel.clear()
            render_list_card(health_attention_panel, title="当前需要注意的问题", lines=[str(exc)], empty="系统健康检查失败。")
            health_actions_panel.clear()
            render_list_card(health_actions_panel, title="建议你下一步做什么", lines=["先确认本地 API 是否可用，再重新刷新健康页。"], empty="系统健康检查失败。")
            health_modules_panel.clear()
            render_list_card(health_modules_panel, title="模块健康", lines=[], empty="系统健康检查失败，当前没有模块信息。")
            health_libraries_panel.clear()
            render_list_card(health_libraries_panel, title="依赖库健康", lines=[], empty="系统健康检查失败，当前没有依赖库信息。")
            health_agents_panel.clear()
            render_list_card(health_agents_panel, title="Agent 健康", lines=[], empty="系统健康检查失败，当前没有 Agent 信息。")
            health_payload_panel.clear()
            render_json_card(health_payload_panel, title="系统健康 JSON", payload={"error": str(exc)})
            if show_notify:
                ui.notify(str(exc), color="negative")

    def restore_version() -> None:
        selected = restore_version_select.value
        entry = next((item for item in _strategy_archive_entries(state.snapshot) if item["version"] == selected), None)
        if not entry:
            strategy_note.text = "没有可恢复的版本。"
            return
        pkg = entry["pkg"]
        if pkg.get("strategy_type"):
            strategy_type.value = pkg["strategy_type"]
            strategy_type.update()
        strategy_feedback.value = pkg.get("feedback", strategy_feedback.value)
        strategy_feedback.update()
        if pkg.get("objective_metric"):
            objective_metric.value = pkg["objective_metric"]
            objective_metric.update()
        targets = pkg.get("objective_targets") or {}
        for field, value in (
            (target_return, targets.get("target_return_pct", 18)),
            (target_win_rate, targets.get("target_win_rate_pct", 58)),
            (target_drawdown, targets.get("target_drawdown_pct", 12)),
            (target_max_loss, targets.get("target_max_loss_pct", 6)),
        ):
            field.value = value
            field.update()
        if pkg.get("iteration_mode"):
            iteration_mode.value = pkg["iteration_mode"]
            iteration_mode.update()
        if pkg.get("auto_iterations_requested"):
            auto_iterations.value = pkg["auto_iterations_requested"]
            auto_iterations.update()
        if pkg.get("selected_universe"):
            universe_symbols.value = ",".join(pkg["selected_universe"])
            universe_symbols.update()
        window = (pkg.get("dataset_plan") or {}).get("user_selected_window") or {}
        training_start.value = window.get("start", training_start.value)
        training_end.value = window.get("end", training_end.value)
        training_start.update()
        training_end.update()
        strategy_note.text = f"已恢复版本 {entry['version']} 到当前实验配置。你可以先检查参数，再决定是否继续训练。"

    def refresh_programmer_scope() -> None:
        targets = [item.strip() for item in (programmer_targets.value or "").split(",") if item.strip()]
        _, color, message = _validate_programmer_targets(targets)
        programmer_scope_note.text = message
        programmer_scope_note.classes(replace=f"text-{color}")

    def refresh_all() -> None:
        snapshot = state.snapshot or {}
        session_summary_panel.clear()
        render_list_card(session_summary_panel, title="当前会话摘要", lines=_session_summary(state.snapshot), empty="尚未加载会话。")
        session_json_panel.clear()
        render_json_card(session_json_panel, title="会话 JSON", payload=snapshot)

        parameters_status_panel.clear()
        render_list_card(parameters_status_panel, title="当前训练状态", lines=_strategy_status_lines(state.snapshot), empty="当前还没有训练状态。")
        parameters_validation_panel.clear()
        validation_lines, validation_errors = _strategy_input_validation_lines(
            training_start_value=training_start.value,
            training_end_value=training_end.value,
            target_return_value=target_return.value,
            target_win_rate_value=target_win_rate.value,
            target_drawdown_value=target_drawdown.value,
            target_max_loss_value=target_max_loss.value,
        )
        render_list_card(
            parameters_validation_panel,
            title="训练参数校验",
            lines=validation_lines + ([f"错误 / {item}" for item in validation_errors] if validation_errors else ["状态 / 当前输入可提交训练"]),
            empty="当前还没有训练参数。",
        )
        parameters_manifest_panel.clear()
        render_list_card(parameters_manifest_panel, title="训练输入说明", lines=_input_manifest_lines(state.snapshot), empty="还没有训练输入说明。")
        parameters_features_panel.clear()
        render_list_card(parameters_features_panel, title="训练特征快照", lines=_feature_snapshot_lines(state.snapshot), empty="还没有训练特征。")
        parameters_bundles_panel.clear()
        render_list_card(parameters_bundles_panel, title="输入数据包注册表", lines=_data_bundle_lines(state.snapshot), empty="还没有输入数据包记录。")
        parameters_package_panel.clear()
        render_list_card(parameters_package_panel, title="策略包", lines=_package_lines(state.snapshot), empty="还没有策略包。")

        training_checks_panel.clear()
        render_list_card(training_checks_panel, title="检查结果", lines=_strategy_checks_lines(state.snapshot), empty="等待策略检查。")
        training_trend_panel.clear()
        render_list_card(training_trend_panel, title="检查失败趋势", lines=_check_trend_lines(state.snapshot), empty="还没有检查趋势。")
        training_repair_panel.clear()
        render_list_card(training_repair_panel, title="修复建议路由", lines=_repair_route_lines(state.snapshot), empty="还没有修复路由建议。")
        training_research_panel.clear()
        render_list_card(training_research_panel, title="研究结论", lines=_research_summary_lines(state.snapshot), empty="还没有研究摘要。")
        training_loop_panel.clear()
        render_list_card(training_loop_panel, title="研究与编程联动", lines=_research_code_loop_lines(state.snapshot), empty="还没有联动趋势。")
        training_logs_panel.clear()
        render_list_card(training_logs_panel, title="训练日志", lines=_training_log_lines(state), empty="还没有训练日志。")

        results_models_panel.clear()
        models = _model_result_specs(state.snapshot)
        if not models:
            render_list_card(results_models_panel, title="策略模型绩效", lines=[], empty="完成一轮策略训练后，这里会显示每个策略模型的总计和按年绩效。")
        else:
            with results_models_panel:
                grid = ui.grid(columns=1).classes("w-full gap-4")
                for model in models:
                    evaluation = model["evaluation"]
                    full_period = (evaluation.get("dataset_evaluation") or {}).get("full_period") or {}
                    with grid:
                        with ui.card().classes("w-full"):
                            with ui.row().classes("w-full items-center justify-between"):
                                with ui.column().classes("gap-1"):
                                    ui.label(model["title"]).classes("text-h6")
                                    ui.label(model["subtitle"]).classes("text-sm text-slate-600")
                                ui.badge("当前推荐" if model["selected"] else "候选模型", color="positive" if model["selected"] else "secondary")
                            ui.markdown(
                                _lines_markdown(
                                    [
                                        f"总计来源 / {evaluation.get('evaluation_source', 'unknown')}",
                                        f"总计收益 / {_fmt_percent(full_period.get('expected_return_pct', evaluation.get('expected_return_pct')))}",
                                        f"总计复利收益 / {_fmt_percent(full_period.get('compounded_return_pct', evaluation.get('expected_return_pct')))}",
                                        f"总计最大亏损 / {_fmt_percent(full_period.get('max_loss_pct', evaluation.get('max_loss_pct')))}",
                                        f"总计最大回撤 / {_fmt_percent(full_period.get('drawdown_pct', evaluation.get('drawdown_pct')))}",
                                        f"总计胜率 / {_fmt_percent(full_period.get('win_rate_pct', evaluation.get('win_rate_pct')))}",
                                        f"总计平均亏损 / {_fmt_percent(full_period.get('avg_loss_trade_pct'))}",
                                        f"总计平均盈利 / {_fmt_percent(full_period.get('avg_gain_trade_pct'))}",
                                        f"总计盈利笔数 / {full_period.get('winning_trade_count', 0)}",
                                        f"总计亏损笔数 / {full_period.get('losing_trade_count', 0)}",
                                    ],
                                    "当前还没有总计绩效数据。",
                                )
                            )
                            rows = _annual_rows(evaluation)
                            if rows:
                                ui.table(
                                    columns=[
                                        {"name": "year", "label": "年份", "field": "year"},
                                        {"name": "return_pct", "label": "收益", "field": "return_pct"},
                                        {"name": "compounded_return_pct", "label": "复利收益", "field": "compounded_return_pct"},
                                        {"name": "max_loss_pct", "label": "最大亏损", "field": "max_loss_pct"},
                                        {"name": "max_drawdown_pct", "label": "最大回撤", "field": lambda row: row.get("max_drawdown_pct", row.get("drawdown_pct"))},
                                        {"name": "win_rate_pct", "label": "胜率", "field": "win_rate_pct"},
                                        {"name": "avg_loss_trade_pct", "label": "平均亏损", "field": "avg_loss_trade_pct"},
                                        {"name": "avg_gain_trade_pct", "label": "平均盈利", "field": "avg_gain_trade_pct"},
                                    ],
                                    rows=rows,
                                    row_key="year",
                                    pagination=10,
                                ).classes("w-full")
                            else:
                                ui.label("当前还没有按年绩效数据。").classes("text-slate-500")

        results_compare_panel.clear()
        render_list_card(results_compare_panel, title="基准与双方案对比", lines=_variant_compare_lines(state.snapshot), empty="还没有方案对比。")
        results_backtest_panel.clear()
        render_list_card(results_backtest_panel, title="回测与分段评估", lines=_backtest_lines(state.snapshot), empty="还没有回测结果。")
        results_walkforward_panel.clear()
        walk_rows = _walk_forward_rows(state.snapshot)
        if walk_rows:
            with results_walkforward_panel:
                with ui.card().classes("w-full"):
                    ui.label("滚动窗口结果").classes("text-h6")
                    ui.table(
                        columns=[
                            {"name": "window_id", "label": "窗口", "field": "window_id"},
                            {"name": "objective_score", "label": "目标分", "field": "objective_score"},
                            {"name": "expected_return_pct", "label": "收益", "field": "expected_return_pct"},
                            {"name": "win_rate_pct", "label": "胜率", "field": "win_rate_pct"},
                            {"name": "drawdown_pct", "label": "回撤", "field": "drawdown_pct"},
                            {"name": "max_loss_pct", "label": "最大亏损", "field": "max_loss_pct"},
                        ],
                        rows=walk_rows,
                        row_key="window_id",
                        pagination=10,
                    ).classes("w-full")
        else:
            render_list_card(results_walkforward_panel, title="滚动窗口结果", lines=[], empty="还没有 walk-forward 结果。")
        results_research_trend_panel.clear()
        render_list_card(results_research_trend_panel, title="研究趋势摘要", lines=_research_trend_lines(state.snapshot), empty="还没有研究趋势摘要。")
        results_research_health_panel.clear()
        render_list_card(results_research_health_panel, title="研究健康结论", lines=_research_health_lines(state.snapshot), empty="还没有研究健康结论。")

        history_iterations_panel.clear()
        render_list_card(history_iterations_panel, title="策略迭代历史", lines=_history_lines(state.snapshot), empty="还没有策略迭代历史。")
        history_archive_panel.clear()
        render_list_card(history_archive_panel, title="策略报告归档", lines=_archive_lines(state.snapshot), empty="还没有策略报告归档。")
        archive_entries = _strategy_archive_entries(state.snapshot)
        archive_options = {item["version"]: item["version"] for item in archive_entries}
        populate_select_options(restore_version_select, archive_options)
        populate_select_options(compare_version_a, archive_options)
        populate_select_options(compare_version_b, archive_options)
        history_compare_panel.clear()
        render_list_card(
            history_compare_panel,
            title="版本对比",
            lines=_version_compare_lines(state.snapshot, compare_version_a.value or "", compare_version_b.value or ""),
            empty="还没有版本对比结果。",
        )
        history_restore_preview_panel.clear()
        render_list_card(
            history_restore_preview_panel,
            title="恢复预览",
            lines=_restore_preview_lines(state.snapshot, restore_version_select.value or ""),
            empty="请选择一个历史版本查看恢复预览。",
        )
        history_code_panel.clear()
        entry = next((item for item in archive_entries if item["version"] == (history_code_select.value or "")), None)
        render_code_card(history_code_panel, title="历史版本代码", code=_strategy_code({"strategy_package": entry["pkg"]} if entry else None))

        research_entries = _strategy_research_entries(state.snapshot)
        research_options = {item["value"]: item["label"] for item in research_entries}
        populate_select_options(research_compare_a, research_options)
        populate_select_options(research_compare_b, research_options)
        populate_select_options(research_detail_select, research_options)
        history_research_compare_panel.clear()
        a_detail, a_export = _research_detail_lines(state.snapshot, research_compare_a.value or "")
        b_detail, b_export = _research_detail_lines(state.snapshot, research_compare_b.value or "")
        compare_lines = []
        if a_detail and b_detail:
            compare_lines = [
                f"版本A / {research_options.get(research_compare_a.value)}",
                f"版本B / {research_options.get(research_compare_b.value)}",
                f"gate / {(a_export.get('research_export') or {}).get('gate_status', 'unknown')} -> {(b_export.get('research_export') or {}).get('gate_status', 'unknown')}",
                f"winner / {(a_export.get('research_export') or {}).get('winner_variant_id', 'unknown')} -> {(b_export.get('research_export') or {}).get('winner_variant_id', 'unknown')}",
                f"next_focus A / {'；'.join((a_export.get('research_export') or {}).get('next_iteration_focus') or []) or '无'}",
                f"next_focus B / {'；'.join((b_export.get('research_export') or {}).get('next_iteration_focus') or []) or '无'}",
            ]
        render_list_card(history_research_compare_panel, title="研究归档对比", lines=compare_lines, empty="还没有研究归档对比结果。")
        history_research_detail_panel.clear()
        detail_lines, detail_export = _research_detail_lines(state.snapshot, research_detail_select.value or "")
        render_list_card(history_research_detail_panel, title="研究归档详情", lines=detail_lines, empty="还没有研究归档详情。")
        history_research_detail_json_panel.clear()
        render_json_card(history_research_detail_json_panel, title="研究导出 JSON", payload=detail_export)
        history_failure_panel.clear()
        render_list_card(history_failure_panel, title="失败原因演化", lines=_failure_evolution_lines(state.snapshot), empty="当前还没有失败原因演化记录。")

        artifacts_release_panel.clear()
        render_list_card(artifacts_release_panel, title="研究发布摘要", lines=_release_snapshot_lines(state.snapshot), empty="还没有研究发布摘要。")
        artifacts_analysis_panel.clear()
        render_list_card(artifacts_analysis_panel, title="问题分析", lines=_analysis_lines(state.snapshot), empty="还没有分析结果。")
        artifacts_code_panel.clear()
        render_code_card(artifacts_code_panel, title="推荐代码", code=_strategy_code(state.snapshot))
        artifacts_model_panel.clear()
        render_list_card(artifacts_model_panel, title="模型矩阵", lines=_model_routing_lines(state.snapshot), empty="还没有模型路由信息。")
        artifacts_token_panel.clear()
        render_list_card(artifacts_token_panel, title="本轮 LLM 消耗", lines=_token_usage_lines(state.snapshot), empty="还没有 token 使用信息。")
        artifacts_programmer_runs_panel.clear()
        render_list_card(artifacts_programmer_runs_panel, title="Programmer Agent 记录", lines=_programmer_runs_lines(state.snapshot), empty="还没有 Programmer Agent 记录。")
        artifacts_programmer_stats_panel.clear()
        render_list_card(artifacts_programmer_stats_panel, title="失败类型统计", lines=_programmer_stats_lines(state.snapshot), empty="还没有 Programmer Agent 统计。")
        artifacts_programmer_trend_panel.clear()
        render_list_card(
            artifacts_programmer_trend_panel,
            title="失败趋势",
            lines=_programmer_trend_lines(state.snapshot, programmer_trend_filter.value or "all"),
            empty="还没有 Programmer Agent 趋势时间线。",
        )
        artifacts_programmer_diff_panel.clear()
        render_code_card(artifacts_programmer_diff_panel, title="代码差异 / 失败摘要", code=_programmer_diff(state.snapshot))

        history_entries = _intelligence_history_entries(state.snapshot)
        history_options = {item["value"]: item["label"] for item in history_entries}
        populate_select_options(intelligence_history_select, history_options)
        intelligence_overview_panel.clear()
        render_list_card(intelligence_overview_panel, title="当前情报概览", lines=_intelligence_overview_lines(state.snapshot), empty="当前还没有情报概览。")
        intelligence_watchlist_panel.clear()
        render_list_card(intelligence_watchlist_panel, title="股票情报总览", lines=_intelligence_watchlist_summary_lines(state.snapshot), empty="当前还没有按股票汇总的情报结果。")
        intelligence_briefing_panel.clear()
        render_list_card(intelligence_briefing_panel, title="情报简报", lines=_intelligence_briefing_lines(state.snapshot), empty="当前还没有情报简报。")
        intelligence_documents_panel.clear()
        render_list_card(intelligence_documents_panel, title="来源与文档", lines=_intelligence_source_lines(state.snapshot), empty="当前还没有情报来源。")
        intelligence_history_panel.clear()
        render_list_card(intelligence_history_panel, title="查询历史时间线", lines=_intelligence_history_lines(state.snapshot), empty="当前还没有查询历史。")
        intelligence_history_detail_panel.clear()
        detail_lines, detail_payload = _intelligence_history_detail_lines(state.snapshot, intelligence_history_select.value or "")
        render_list_card(intelligence_history_detail_panel, title="历史查询详情", lines=detail_lines, empty="请选择一条历史查询查看详情。")
        intelligence_history_payload_panel.clear()
        render_json_card(intelligence_history_payload_panel, title="选中历史查询 JSON", payload=detail_payload)
        intelligence_financials_panel.clear()
        render_list_card(intelligence_financials_panel, title="财报摘要", lines=_market_summary_lines(state.snapshot, "financials"), empty="当前还没有财报摘要。")
        intelligence_dark_pool_panel.clear()
        render_list_card(intelligence_dark_pool_panel, title="暗池摘要", lines=_market_summary_lines(state.snapshot, "dark_pool"), empty="当前还没有暗池摘要。")
        intelligence_options_panel.clear()
        render_list_card(intelligence_options_panel, title="期权摘要", lines=_market_summary_lines(state.snapshot, "options"), empty="当前还没有期权摘要。")
        intelligence_payload_panel.clear()
        render_json_card(
            intelligence_payload_panel,
            title="最新结构化结果",
            payload={
                "latest_intelligence_run": _latest(snapshot.get("intelligence_runs") or []),
                "intelligence_runs": snapshot.get("intelligence_runs") or [],
                "intelligence_documents": snapshot.get("intelligence_documents") or [],
                "financials_runs": snapshot.get("financials_runs") or [],
                "dark_pool_runs": snapshot.get("dark_pool_runs") or [],
                "options_runs": snapshot.get("options_runs") or [],
            },
        )

        simulation_market_panel.clear()
        render_list_card(simulation_market_panel, title="模拟市场状态", lines=_simulation_market_lines(state.snapshot), empty="先加载模拟市场数据，建立日线与 5 分钟线回放。")
        simulation_daily_chart_panel.clear()
        simulation_market = snapshot.get("simulation_market") or {}
        render_chart_card(
            simulation_daily_chart_panel,
            title="日线图",
            option=(
                _simulation_chart_option(
                    simulation_market.get("daily_visible_bars") or simulation_market.get("daily_bars") or [],
                    title="日线收盘轨迹",
                    current_timestamp=(simulation_market.get("current_daily_bar") or {}).get("timestamp"),
                )
                if simulation_market
                else None
            ),
            empty="当前还没有日线数据。",
        )
        simulation_intraday_chart_panel.clear()
        render_chart_card(
            simulation_intraday_chart_panel,
            title="5 分钟线图",
            option=(
                _simulation_chart_option(
                    simulation_market.get("current_day_visible_bars") or simulation_market.get("current_day_bars") or [],
                    title="当前模拟日 5 分钟轨迹",
                    current_timestamp=simulation_market.get("current_timestamp"),
                )
                if simulation_market
                else None
            ),
            empty="当前还没有 5 分钟线数据。",
        )
        simulation_summary_panel.clear()
        render_list_card(
            simulation_summary_panel,
            title="模拟与执行摘要",
            lines=state.local_simulation_logs[-10:] + _behavior_report_lines(snapshot.get("behavioral_system_report") or snapshot.get("behavioral_report"), "system"),
            empty="当前还没有模拟摘要。",
        )
        simulation_user_panel.clear()
        render_list_card(
            simulation_user_panel,
            title="用户行为报告",
            lines=_behavior_report_lines(snapshot.get("behavioral_user_report") or snapshot.get("behavioral_report"), "user"),
            empty="当前还没有用户行为报告。",
        )
        simulation_system_panel.clear()
        render_list_card(
            simulation_system_panel,
            title="系统行为报告",
            lines=_behavior_report_lines(snapshot.get("behavioral_system_report") or snapshot.get("behavioral_report"), "system"),
            empty="当前还没有系统行为报告。",
        )
        simulation_trade_panel.clear()
        render_list_card(simulation_trade_panel, title="交易执行记录", lines=_simulation_trade_lines(state.snapshot), empty="当前还没有交易执行记录。")
        simulation_scenario_panel.clear()
        render_list_card(simulation_scenario_panel, title="场景记录", lines=_simulation_scenario_lines(state.snapshot), empty="当前还没有场景记录。")

        preferences_current_panel.clear()
        render_list_card(preferences_current_panel, title="当前交易偏好", lines=_preferences_lines(state.snapshot), empty="当前还没有交易偏好。")
        preferences_recommend_panel.clear()
        render_list_card(preferences_recommend_panel, title="行为推荐", lines=_preference_recommendation_lines(state.snapshot), empty="等待行为测试推荐。")
        preferences_payload_panel.clear()
        render_json_card(
            preferences_payload_panel,
            title="偏好与行为 JSON",
            payload={
                "trading_preferences": snapshot.get("trading_preferences") or {},
                "behavioral_user_report": snapshot.get("behavioral_user_report") or {},
                "behavioral_system_report": snapshot.get("behavioral_system_report") or {},
            },
        )

        report_latest_panel.clear()
        render_list_card(report_latest_panel, title="当前研究结论", lines=_research_summary_lines(state.snapshot), empty="当前还没有策略研究结论。")
        report_archive_panel.clear()
        render_list_card(report_archive_panel, title="报告归档", lines=_report_history_lines(state.snapshot), empty="当前还没有报告归档。")
        report_feedback_panel.clear()
        render_list_card(report_feedback_panel, title="用户意见记录", lines=_feedback_lines(state.snapshot), empty="当前还没有用户意见记录。")
        report_execution_panel.clear()
        render_list_card(
            report_execution_panel,
            title="执行质量",
            lines=_behavior_report_lines(snapshot.get("behavioral_system_report") or snapshot.get("behavioral_report"), "execution"),
            empty="当前还没有执行质量结论。",
        )
        report_payload_panel.clear()
        render_json_card(
            report_payload_panel,
            title="报告 JSON",
            payload={
                "report_history": snapshot.get("report_history") or [],
                "strategy_feedback_log": snapshot.get("strategy_feedback_log") or [],
                "behavioral_user_report": snapshot.get("behavioral_user_report") or {},
                "behavioral_system_report": snapshot.get("behavioral_system_report") or {},
            },
        )

        configuration_panel.clear()
        render_list_card(configuration_panel, title="当前配置", lines=_configuration_lines(state.snapshot), empty="当前还没有配置。")
        configuration_validation_panel.clear()
        render_list_card(configuration_validation_panel, title="配置校验摘要", lines=_validation_lines(state.config_validation), empty="当前还没有配置校验结果。")
        configuration_test_panel.clear()
        render_list_card(configuration_test_panel, title="最近一次配置测试", lines=_validation_lines(state.config_test_result), empty="当前还没有配置测试结果。")
        configuration_json_panel.clear()
        render_json_card(
            configuration_json_panel,
            title="配置 JSON",
            payload={
                "trade_universe": snapshot.get("trade_universe") or {},
                "trading_preferences": snapshot.get("trading_preferences") or {},
                "strategy_package": snapshot.get("strategy_package") or {},
                "system_config": state.config_payload or {},
            },
        )
        data_source_options = _run_options(snapshot.get("data_source_runs") or [], ["provider_name", "category", "timestamp"])
        populate_select_options(data_source_run_select, data_source_options)
        data_source_panel.clear()
        render_list_card(data_source_panel, title="数据源扩展记录", lines=_data_source_lines(state.snapshot), empty="当前还没有数据源扩展记录。")
        data_source_detail_panel.clear()
        render_json_card(data_source_detail_panel, title="选中数据源扩展详情", payload=_selected_run(snapshot.get("data_source_runs") or [], data_source_run_select.value))
        data_bundle_panel.clear()
        render_list_card(data_bundle_panel, title="输入数据包记录", lines=_data_bundle_lines(state.snapshot), empty="当前还没有输入数据包记录。")
        operations_control_panel.clear()
        render_list_card(operations_control_panel, title="本地运行操作日志", lines=state.local_operation_logs, empty="当前还没有运行控制日志。")
        operations_panel.clear()
        render_list_card(operations_panel, title="运行事件", lines=_history_event_lines(state.snapshot), empty="当前还没有运行事件。")
        operations_monitor_panel.clear()
        render_list_card(operations_monitor_panel, title="监控信号", lines=_monitor_lines(state.snapshot), empty="当前还没有监控信号。")
        terminal_options = _run_options(snapshot.get("terminal_integration_runs") or [], ["terminal_name", "terminal_type", "timestamp"])
        populate_select_options(terminal_run_select, terminal_options)
        terminal_panel.clear()
        render_list_card(terminal_panel, title="终端集成记录", lines=_terminal_lines(state.snapshot), empty="当前还没有终端集成记录。")
        terminal_detail_panel.clear()
        render_json_card(terminal_detail_panel, title="选中终端接入详情", payload=_selected_run(snapshot.get("terminal_integration_runs") or [], terminal_run_select.value))

        prefs = snapshot.get("trading_preferences") or {}
        if prefs:
            if prefs.get("trading_frequency"):
                preference_frequency.value = prefs.get("trading_frequency")
                preference_frequency.update()
            if prefs.get("preferred_timeframe"):
                preference_timeframe.value = prefs.get("preferred_timeframe")
                preference_timeframe.update()
            preference_rationale.value = prefs.get("rationale") or preference_rationale.value
            preference_rationale.update()
        refresh_programmer_scope()

    with ui.header(elevated=True).classes("items-center justify-between"):
        with ui.column().classes("gap-0"):
            ui.label("Sentinel-Alpha NiceGUI").classes("text-h5")
            ui.label("现有 FastAPI 后端之上的 NiceGUI 主工作台").classes("text-sm text-slate-200")
        with ui.row().classes("items-center gap-3"):
            ui.link("API Docs", f"{api_base}/docs").props("target=_blank").classes("text-white")

    with ui.column().classes("w-full max-w-7xl mx-auto p-6 gap-6"):
        with ui.card().classes("w-full"):
            ui.markdown(
                "当前入口已经切到 NiceGUI。页面结构已覆盖 `会话 / 配置 / 策略 / 模拟 / 偏好 / 报告 / 数据源扩展 / 运行 / 终端集成 / 情报 / 健康`，并继续直接调用现有 FastAPI API。"
            )

        with ui.tabs().classes("w-full") as root_tabs:
            session_tab = ui.tab("会话")
            configuration_tab = ui.tab("配置")
            strategy_tab = ui.tab("策略")
            simulation_tab = ui.tab("模拟")
            preferences_tab = ui.tab("偏好")
            report_tab = ui.tab("报告")
            data_source_tab = ui.tab("数据源扩展")
            operations_tab = ui.tab("运行")
            terminal_tab = ui.tab("终端集成")
            intelligence_tab = ui.tab("情报")
            health_tab = ui.tab("健康")

        with ui.tab_panels(root_tabs, value=session_tab).classes("w-full"):
            with ui.tab_panel(session_tab):
                with ui.grid(columns=2).classes("w-full gap-4"):
                    with ui.card().classes("w-full"):
                        ui.label("会话管理").classes("text-h6")
                        user_name = ui.input("用户名", value="nicegui-user").classes("w-full")
                        starting_capital = ui.number("初始资金", value=100000, min=1).classes("w-full")
                        session_id_input = ui.input("session_id", value="").classes("w-full")
                        with ui.row().classes("gap-3"):
                            session_actions.append(ui.button("创建会话", on_click=create_session))
                            session_actions.append(ui.button("加载会话", on_click=load_session, color="secondary"))
                            session_spinner = ui.spinner(size="sm")
                            session_spinner.visible = False
                        session_note = ui.label("创建会话后会自动补齐交易标的、行为画像和交易偏好。").classes("text-sm text-slate-600")
                        ui.markdown(f"API Base: `{api_base}`")
                    session_summary_panel = ui.column().classes("w-full gap-4")
                session_json_panel = ui.column().classes("w-full gap-4")

            with ui.tab_panel(configuration_tab):
                with ui.card().classes("w-full"):
                    ui.label("系统配置工作台").classes("text-h6")
                    ui.label("这里可以加载、编辑、保存并测试当前系统配置。").classes("text-sm text-slate-600")
                    config_editor = ui.textarea("配置 JSON", value="{}").props("autogrow").classes("w-full")
                    with ui.grid(columns=2).classes("w-full gap-4"):
                        config_test_family = ui.select(
                            {
                                "market_data": "market_data",
                                "fundamentals": "fundamentals",
                                "dark_pool": "dark_pool",
                                "options_data": "options_data",
                                "llm": "llm",
                                "programmer_agent": "programmer_agent",
                            },
                            value="market_data",
                            label="单项测试 family",
                        ).classes("w-full")
                        config_test_provider = ui.input("单项测试 provider", value="").classes("w-full")
                    with ui.row().classes("gap-3 mt-3"):
                        config_actions.append(ui.button("重新加载配置", on_click=reload_config, color="secondary"))
                        config_actions.append(ui.button("保存配置", on_click=save_config))
                        config_actions.append(ui.button("全量测试配置", on_click=test_config, color="secondary"))
                        config_actions.append(ui.button("测试单项配置", on_click=test_config_item, color="secondary"))
                        config_spinner = ui.spinner(size="sm")
                        config_spinner.visible = False
                    config_note = ui.label("配置会保存到当前 settings.toml，并立即按当前环境重新校验。").classes("text-sm text-slate-600")
                with ui.grid(columns=2).classes("w-full gap-4"):
                    configuration_panel = ui.column().classes("w-full gap-4")
                    configuration_validation_panel = ui.column().classes("w-full gap-4")
                    configuration_test_panel = ui.column().classes("w-full gap-4")
                    configuration_json_panel = ui.column().classes("w-full gap-4")

            with ui.tab_panel(strategy_tab):
                with ui.tabs().classes("w-full") as strategy_tabs:
                    strategy_parameters_tab = ui.tab("策略参数与目标")
                    strategy_training_tab = ui.tab("训练页面")
                    strategy_results_tab = ui.tab("结果页面")
                    strategy_history_tab = ui.tab("历史页面")
                    strategy_artifacts_tab = ui.tab("成果页面")

                with ui.card().classes("w-full"):
                    ui.label("策略公共配置").classes("text-h6")
                    with ui.grid(columns=2).classes("w-full gap-4"):
                        universe_type = ui.select({"stocks": "股票", "etfs": "ETF", "sector": "板块"}, value="stocks", label="标的类型").classes("w-full")
                        universe_symbols = ui.input("标的列表", value="TSLA,NVDA,QQQ").classes("w-full")
                        training_start = ui.input("训练开始", placeholder="YYYY-MM-DD").classes("w-full")
                        training_end = ui.input("训练结束", placeholder="YYYY-MM-DD").classes("w-full")
                        strategy_type = ui.select(
                            {
                                "rule_based_aligned": "Rule-Based Aligned",
                                "trend_following_aligned": "Trend Following Aligned",
                                "mean_reversion_aligned": "Mean Reversion Aligned",
                            },
                            value="rule_based_aligned",
                            label="策略类型",
                        ).classes("w-full")
                        strategy_feedback = ui.input("训练反馈", value="Reduce concentration and avoid earnings week.").classes("w-full")
                        objective_metric = ui.select(
                            {"return": "收益", "win_rate": "胜率", "drawdown": "回撤", "max_loss": "最大亏损"},
                            value="return",
                            label="优化目标",
                        ).classes("w-full")
                        iteration_mode = ui.select({"guided": "自动迭代", "free": "自由迭代"}, value="guided", label="迭代模式").classes("w-full")
                        target_return = ui.number("目标收益 %", value=18).classes("w-full")
                        target_win_rate = ui.number("目标胜率 %", value=58).classes("w-full")
                        target_drawdown = ui.number("目标回撤 %", value=12).classes("w-full")
                        target_max_loss = ui.number("目标最大亏损 %", value=6).classes("w-full")
                        auto_iterations = ui.number("自动轮数", value=3, min=1, max=10).classes("w-full")
                    with ui.row().classes("gap-3 mt-4"):
                        strategy_actions.append(ui.button("提交交易标的", on_click=submit_universe, color="secondary"))
                        strategy_actions.append(ui.button("生成下一版策略", on_click=run_strategy_iteration))
                        strategy_actions.append(ui.button("确认当前策略", on_click=approve_strategy, color="secondary"))
                        strategy_spinner = ui.spinner(size="sm")
                        strategy_spinner.visible = False
                    strategy_note = ui.label("每个策略版本都会自动经过 Integrity 与 Stress/Overfit 检查。").classes("text-sm text-slate-600")

                with ui.tab_panels(strategy_tabs, value=strategy_parameters_tab).classes("w-full"):
                    with ui.tab_panel(strategy_parameters_tab):
                        parameters_status_panel = ui.column().classes("w-full gap-4")
                        with ui.grid(columns=2).classes("w-full gap-4"):
                            parameters_validation_panel = ui.column().classes("w-full gap-4")
                            parameters_manifest_panel = ui.column().classes("w-full gap-4")
                            parameters_features_panel = ui.column().classes("w-full gap-4")
                            parameters_bundles_panel = ui.column().classes("w-full gap-4")
                            parameters_package_panel = ui.column().classes("w-full gap-4")

                    with ui.tab_panel(strategy_training_tab):
                        with ui.card().classes("w-full"):
                            ui.label("训练控制").classes("text-h6")
                            ui.label("这里负责启动训练、继续自动迭代、回填修复建议，以及让用户在需要时介入。").classes("text-sm text-slate-600")
                            with ui.row().classes("gap-3 mt-2"):
                                strategy_actions.append(ui.button("回填修复反馈", on_click=apply_repair_feedback, color="secondary"))
                                strategy_actions.append(ui.button("回填修复指令", on_click=apply_repair_programmer, color="secondary"))
                                strategy_actions.append(ui.button("继续自动训练", on_click=continue_auto_training, color="primary"))
                                strategy_actions.append(ui.button("我来介入后再训练", on_click=prepare_manual_intervention, color="secondary"))
                        with ui.grid(columns=2).classes("w-full gap-4"):
                            training_checks_panel = ui.column().classes("w-full gap-4")
                            training_trend_panel = ui.column().classes("w-full gap-4")
                            training_repair_panel = ui.column().classes("w-full gap-4")
                            training_research_panel = ui.column().classes("w-full gap-4")
                            training_loop_panel = ui.column().classes("w-full gap-4")
                            training_logs_panel = ui.column().classes("w-full gap-4")

                    with ui.tab_panel(strategy_results_tab):
                        results_models_panel = ui.column().classes("w-full gap-4")
                        with ui.grid(columns=2).classes("w-full gap-4"):
                            results_compare_panel = ui.column().classes("w-full gap-4")
                            results_backtest_panel = ui.column().classes("w-full gap-4")
                            results_walkforward_panel = ui.column().classes("w-full gap-4")
                            results_research_trend_panel = ui.column().classes("w-full gap-4")
                            results_research_health_panel = ui.column().classes("w-full gap-4")

                    with ui.tab_panel(strategy_history_tab):
                        with ui.grid(columns=2).classes("w-full gap-4"):
                            history_iterations_panel = ui.column().classes("w-full gap-4")
                            with ui.column().classes("w-full gap-4"):
                                with ui.card().classes("w-full"):
                                    ui.label("恢复版本").classes("text-h6")
                                    restore_version_select = ui.select({}, label="恢复版本").classes("w-full")
                                    ui.button("恢复为当前实验版本", on_click=restore_version, color="secondary")
                                history_restore_preview_panel = ui.column().classes("w-full gap-4")
                                history_archive_panel = ui.column().classes("w-full gap-4")
                            with ui.column().classes("w-full gap-4"):
                                with ui.card().classes("w-full"):
                                    ui.label("版本对比").classes("text-h6")
                                    compare_version_a = ui.select({}, label="版本 A").classes("w-full")
                                    compare_version_b = ui.select({}, label="版本 B").classes("w-full")
                                history_compare_panel = ui.column().classes("w-full gap-4")
                                with ui.card().classes("w-full"):
                                    ui.label("历史版本代码").classes("text-h6")
                                    history_code_select = ui.select({}, label="查看版本", on_change=lambda _: refresh_all()).classes("w-full")
                                history_code_panel = ui.column().classes("w-full gap-4")
                            with ui.column().classes("w-full gap-4"):
                                with ui.card().classes("w-full"):
                                    ui.label("研究归档").classes("text-h6")
                                    research_compare_a = ui.select({}, label="研究版本 A").classes("w-full")
                                    research_compare_b = ui.select({}, label="研究版本 B").classes("w-full")
                                    research_detail_select = ui.select({}, label="研究详情").classes("w-full")
                                history_research_compare_panel = ui.column().classes("w-full gap-4")
                                history_research_detail_panel = ui.column().classes("w-full gap-4")
                                history_research_detail_json_panel = ui.column().classes("w-full gap-4")
                                history_failure_panel = ui.column().classes("w-full gap-4")

                    with ui.tab_panel(strategy_artifacts_tab):
                        with ui.grid(columns=2).classes("w-full gap-4"):
                            artifacts_release_panel = ui.column().classes("w-full gap-4")
                            artifacts_analysis_panel = ui.column().classes("w-full gap-4")
                            artifacts_code_panel = ui.column().classes("w-full gap-4")
                            artifacts_model_panel = ui.column().classes("w-full gap-4")
                            artifacts_token_panel = ui.column().classes("w-full gap-4")
                            with ui.column().classes("w-full gap-4"):
                                with ui.card().classes("w-full"):
                                    ui.label("Programmer Agent").classes("text-h6")
                                    programmer_targets = ui.input("目标文件", value="src/sentinel_alpha/strategies/rule_based.py", on_change=lambda _: refresh_programmer_scope()).classes("w-full")
                                    programmer_instruction = ui.input("修改指令", value="调整策略参数，并保留现有风控结构。").classes("w-full")
                                    programmer_context = ui.input("附加上下文", value="优先处理最新失败原因，并保持版本命名与检查流程不变。").classes("w-full")
                                    programmer_scope_note = ui.label("Programmer Agent 默认只应修改策略文件或明确授权的生成目录。").classes("text-sm")
                                    ui.button("执行 Programmer Agent", on_click=run_programmer_agent)
                                    programmer_trend_filter = ui.select(
                                        {
                                            "all": "全部",
                                            "success": "success",
                                            "compile_failure": "compile_failure",
                                            "test_failure": "test_failure",
                                            "execution_failure": "execution_failure",
                                            "validation_failure": "validation_failure",
                                            "commit_failure": "commit_failure",
                                            "disabled": "disabled",
                                            "misconfigured": "misconfigured",
                                        },
                                        value="all",
                                        label="趋势过滤",
                                        on_change=lambda _: refresh_all(),
                                    ).classes("w-full")
                                artifacts_programmer_runs_panel = ui.column().classes("w-full gap-4")
                                artifacts_programmer_stats_panel = ui.column().classes("w-full gap-4")
                                artifacts_programmer_trend_panel = ui.column().classes("w-full gap-4")
                                artifacts_programmer_diff_panel = ui.column().classes("w-full gap-4")

            with ui.tab_panel(simulation_tab):
                with ui.card().classes("w-full"):
                    ui.label("模拟交易与行为测试").classes("text-h6")
                    ui.label("系统会自动使用当前会话股票池的第一个标的建立日线与 5 分钟线回放。你只需要推进市场，并在每个市场时点选择买入、卖出或不交易。").classes("text-sm text-slate-600")
                    simulation_action = ui.select({"buy": "buy", "sell": "sell", "hold": "hold"}, value="hold", label="最近动作").classes("hidden")
                    with ui.row().classes("gap-3 mt-3"):
                        simulation_actions.append(ui.button("加载模拟市场", on_click=initialize_simulation_market_run, color="secondary"))
                        simulation_actions.append(ui.button("推进模拟时钟", on_click=advance_simulation_market_run, color="secondary"))
                        simulation_actions.append(ui.button("买入", on_click=lambda: record_simulation_action("buy"), color="positive"))
                        simulation_actions.append(ui.button("卖出", on_click=lambda: record_simulation_action("sell"), color="negative"))
                        simulation_actions.append(ui.button("不交易", on_click=lambda: record_simulation_action("hold"), color="secondary"))
                        simulation_actions.append(ui.button("完成模拟并生成画像", on_click=complete_simulation_run))
                        simulation_spinner = ui.spinner(size="sm")
                        simulation_spinner.visible = False
                    simulation_note = ui.label("先加载模拟市场，再按固定 5 分钟节奏推进时钟，然后只通过买入、卖出、不交易三个动作记录你的行为。").classes("text-sm text-slate-600")
                with ui.grid(columns=2).classes("w-full gap-4"):
                    simulation_market_panel = ui.column().classes("w-full gap-4")
                    simulation_daily_chart_panel = ui.column().classes("w-full gap-4")
                    simulation_intraday_chart_panel = ui.column().classes("w-full gap-4")
                    simulation_summary_panel = ui.column().classes("w-full gap-4")
                    simulation_user_panel = ui.column().classes("w-full gap-4")
                    simulation_system_panel = ui.column().classes("w-full gap-4")
                    simulation_trade_panel = ui.column().classes("w-full gap-4")
                    simulation_scenario_panel = ui.column().classes("w-full gap-4")

            with ui.tab_panel(preferences_tab):
                with ui.card().classes("w-full"):
                    ui.label("交易偏好设置").classes("text-h6")
                    ui.label("这里直接承接行为推荐，并保存你的交易频率、周期和理由。").classes("text-sm text-slate-600")
                    with ui.grid(columns=3).classes("w-full gap-4"):
                        preference_frequency = ui.select({"low": "低频", "medium": "中频", "high": "高频"}, value="medium", label="交易频率").classes("w-full")
                        preference_timeframe = ui.select({"minute": "分钟线", "daily": "日线", "weekly": "周线"}, value="daily", label="偏好周期").classes("w-full")
                        preference_rationale = ui.input("偏好说明", value="Prefer balanced cadence with manageable monitoring load.").classes("w-full")
                    with ui.row().classes("gap-3 mt-3"):
                        preferences_actions.append(ui.button("应用行为推荐", on_click=apply_preference_recommendation, color="secondary"))
                        preferences_actions.append(ui.button("保存交易偏好", on_click=save_preferences))
                        preferences_spinner = ui.spinner(size="sm")
                        preferences_spinner.visible = False
                    preferences_note = ui.label("如果你的选择与行为测试冲突，这里会给出冲突提示。").classes("text-sm text-slate-600")
                with ui.grid(columns=2).classes("w-full gap-4"):
                    preferences_current_panel = ui.column().classes("w-full gap-4")
                    preferences_recommend_panel = ui.column().classes("w-full gap-4")
                preferences_payload_panel = ui.column().classes("w-full gap-4")

            with ui.tab_panel(report_tab):
                with ui.card().classes("w-full"):
                    ui.label("报告中心").classes("text-h6")
                    ui.label("这里聚合当前研究结论、历史报告、用户意见和执行质量，不再依赖旧静态 report 页面。").classes("text-sm text-slate-600")
                with ui.grid(columns=2).classes("w-full gap-4"):
                    report_latest_panel = ui.column().classes("w-full gap-4")
                    report_archive_panel = ui.column().classes("w-full gap-4")
                    report_feedback_panel = ui.column().classes("w-full gap-4")
                    report_execution_panel = ui.column().classes("w-full gap-4")
                report_payload_panel = ui.column().classes("w-full gap-4")

            with ui.tab_panel(data_source_tab):
                with ui.card().classes("w-full"):
                    ui.label("数据源扩展工作台").classes("text-h6")
                    ui.label("只需要提供 API KEY 和接口文档。系统会优先使用 LLM 分析非结构化接口文档，产出结构化接入规范；如果 LLM 不可用或输出非法结构，再回退到规则兜底分析，然后生成代码与测试。").classes("text-sm text-slate-600")
                    with ui.grid(columns=2).classes("w-full gap-4"):
                        data_source_api_key = ui.input("API KEY", password=True, password_toggle_button=True).classes("w-full")
                        data_source_interface_documentation = ui.textarea(
                            "接口文档",
                            value="https://docs.example.com/reference\nBase URL: https://api.example.com\nREST JSON API with symbol quote and history endpoints. Authorization header uses bearer token.",
                        ).props("autogrow").classes("w-full")
                    with ui.row().classes("gap-3 mt-3"):
                        data_source_actions.append(ui.button("生成数据源扩展方案", on_click=expand_data_source_run))
                        data_source_run_select = ui.select({}, label="应用已有 run").classes("w-72")
                        data_source_test_symbol = ui.input("测试股票", value="AAPL").classes("w-40")
                        data_source_actions.append(ui.button("测试数据源扩展", on_click=test_data_source_run, color="secondary"))
                        data_source_commit = ui.switch("提交改动", value=True)
                        data_source_actions.append(ui.button("应用数据源扩展", on_click=apply_data_source_run, color="secondary"))
                        data_source_spinner = ui.spinner(size="sm")
                        data_source_spinner.visible = False
                    data_source_note = ui.label("这里会基于最小输入完成 LLM 文档分析、结构化 spec 生成、代码与测试草案生成。生成后请执行“测试数据源扩展”，确认 smoke test 结果；如果提供 API KEY，还会尝试 live fetch。").classes("text-sm text-slate-600")
                with ui.card().classes("w-full"):
                    ui.label("本地数据路径与支持格式").classes("text-subtitle1")
                    ui.markdown(
                        "\n".join(
                            [
                                f"- 行情目录: `{local_market_root}`",
                                f"- 财报目录: `{local_fundamentals_root}`",
                                f"- 暗池目录: `{local_dark_pool_root}`",
                                f"- 期权目录: `{local_options_root}`",
                            ]
                        )
                    ).classes("text-sm text-slate-700")
                    ui.markdown(
                        "\n".join(
                            [
                                "- 行情历史文件: `data/local_market_data/market_data/{SYMBOL}_{interval}.csv` 或 `.json`",
                                "- 例子: `data/local_market_data/market_data/AAPL_1d.csv`",
                                "- 实时报价文件: `data/local_market_data/market_data/{SYMBOL}_quote.json` 或 `.csv`",
                                "- 例子: `data/local_market_data/market_data/AAPL_quote.json`",
                                "- 财报文件: `data/local_market_data/fundamentals/{SYMBOL}_financials.json`",
                                "- 例子: `data/local_market_data/fundamentals/AAPL_financials.json`",
                                "- 暗池文件: `data/local_market_data/dark_pool/{SYMBOL}_dark_pool.json`",
                                "- 期权文件: `data/local_market_data/options/{SYMBOL}_options.json`",
                                "- 历史 CSV 必须至少包含: `timestamp, open, high, low, close, volume`",
                            ]
                        )
                    ).classes("text-sm")
                    ui.label("本地历史 CSV 例子").classes("text-sm font-medium text-slate-700")
                    ui.code(
                        "timestamp,open,high,low,close,volume\n"
                        "2026-03-24T00:00:00Z,180.2,183.1,179.8,182.5,53200000\n"
                        "2026-03-25T00:00:00Z,182.5,184.4,181.7,183.9,48700000\n",
                        language="csv",
                    ).classes("w-full")
                    ui.label("本地报价 JSON 例子").classes("text-sm font-medium text-slate-700")
                    ui.code(
                        '{\n'
                        '  "provider": "local_file",\n'
                        '  "symbol": "AAPL",\n'
                        '  "price": 183.9,\n'
                        '  "open": 182.5,\n'
                        '  "high": 184.4,\n'
                        '  "low": 181.7,\n'
                        '  "previous_close": 182.5,\n'
                        '  "timestamp": "2026-03-25T20:00:00Z"\n'
                        '}',
                        language="json",
                    ).classes("w-full")
                    ui.label("本地财报 JSON 例子").classes("text-sm font-medium text-slate-700")
                    ui.code(
                        '{\n'
                        '  "provider": "local_file",\n'
                        '  "symbol": "AAPL",\n'
                        '  "normalized": {\n'
                        '    "entity_name": "Apple Inc.",\n'
                        '    "report_period": "2025-12-31",\n'
                        '    "statements": [\n'
                        '      {"period_end": "2025-12-31", "revenue": 391000000000, "net_income": 97000000000}\n'
                        '    ]\n'
                        '  }\n'
                        '}',
                        language="json",
                    ).classes("w-full")
                with ui.grid(columns=2).classes("w-full gap-4"):
                    data_source_panel = ui.column().classes("w-full gap-4")
                    data_source_detail_panel = ui.column().classes("w-full gap-4")
                    data_bundle_panel = ui.column().classes("w-full gap-4")

            with ui.tab_panel(operations_tab):
                with ui.card().classes("w-full"):
                    ui.label("运行控制工作台").classes("text-h6")
                    with ui.grid(columns=2).classes("w-full gap-4"):
                        with ui.card().classes("w-full"):
                            ui.label("场景与部署").classes("text-h6")
                            operation_deployment_mode = ui.select({"autonomous": "autonomous", "advice_only": "advice_only"}, value="advice_only", label="部署模式").classes("w-full")
                            with ui.row().classes("gap-3 mt-3"):
                                operations_actions.append(ui.button("生成场景", on_click=generate_operation_scenarios))
                                operations_actions.append(ui.button("更新部署模式", on_click=set_operation_deployment, color="secondary"))
                        with ui.card().classes("w-full"):
                            ui.label("市场快照").classes("text-h6")
                            with ui.grid(columns=4).classes("w-full gap-4"):
                                operation_market_symbol = ui.input("Symbol", value="TSLA").classes("w-full")
                                operation_market_timeframe = ui.input("Timeframe", value="1d").classes("w-full")
                                operation_market_source = ui.input("Source", value="manual").classes("w-full")
                                operation_market_regime = ui.input("Regime", value="risk_on").classes("w-full")
                                operation_market_open = ui.number("Open", value=100).classes("w-full")
                                operation_market_high = ui.number("High", value=104).classes("w-full")
                                operation_market_low = ui.number("Low", value=98).classes("w-full")
                                operation_market_close = ui.number("Close", value=102).classes("w-full")
                                operation_market_volume = ui.number("Volume", value=1000000).classes("w-full")
                            operations_actions.append(ui.button("写入市场快照", on_click=append_operation_market_snapshot, color="secondary"))
                        with ui.card().classes("w-full"):
                            ui.label("信息流事件").classes("text-h6")
                            with ui.grid(columns=3).classes("w-full gap-4"):
                                operation_info_channel = ui.select({"focus": "focus", "news": "news", "chat": "chat", "discussion": "discussion"}, value="news", label="Channel").classes("w-full")
                                operation_info_source = ui.input("Source", value="manual-feed").classes("w-full")
                                operation_info_day = ui.input("Trading Day", value="").classes("w-full")
                                operation_info_title = ui.input("Title", value="Manual information event").classes("w-full")
                                operation_info_author = ui.input("Author", value="operator").classes("w-full")
                                operation_info_handle = ui.input("Handle", value="manual").classes("w-full")
                                operation_info_tag = ui.input("Tag", value="macro").classes("w-full")
                                operation_info_sentiment = ui.number("Sentiment", value=0.2, step=0.1).classes("w-full")
                                operation_info_body = ui.textarea("Body", value="Manual information event body.").props("autogrow").classes("w-full")
                            operations_actions.append(ui.button("写入信息流事件", on_click=append_operation_information_event, color="secondary"))
                        with ui.card().classes("w-full"):
                            ui.label("交易执行记录").classes("text-h6")
                            with ui.grid(columns=4).classes("w-full gap-4"):
                                operation_trade_symbol = ui.input("Symbol", value="TSLA").classes("w-full")
                                operation_trade_side = ui.select({"buy": "buy", "sell": "sell"}, value="buy", label="Side").classes("w-full")
                                operation_trade_quantity = ui.number("Quantity", value=10).classes("w-full")
                                operation_trade_price = ui.number("Price", value=100).classes("w-full")
                                operation_trade_notional = ui.number("Notional", value=1000).classes("w-full")
                                operation_trade_mode = ui.select({"manual": "manual", "advice_only": "advice_only", "autonomous": "autonomous"}, value="manual", label="Mode").classes("w-full")
                                operation_trade_strategy_version = ui.input("Strategy Version", value="manual").classes("w-full")
                                operation_trade_pnl = ui.number("Realized PnL %", value=0).classes("w-full")
                                operation_trade_note = ui.input("Note", value="manual execution").classes("w-full")
                            operations_actions.append(ui.button("写入交易执行记录", on_click=append_operation_trade_execution, color="secondary"))
                    with ui.row().classes("gap-3 mt-3"):
                        operations_spinner = ui.spinner(size="sm")
                        operations_spinner.visible = False
                    operations_note = ui.label("这里负责把运行控制相关事件写入当前 session。").classes("text-sm text-slate-600")
                with ui.grid(columns=2).classes("w-full gap-4"):
                    operations_control_panel = ui.column().classes("w-full gap-4")
                    operations_panel = ui.column().classes("w-full gap-4")
                    operations_monitor_panel = ui.column().classes("w-full gap-4")

            with ui.tab_panel(terminal_tab):
                with ui.card().classes("w-full"):
                    ui.label("终端集成工作台").classes("text-h6")
                    with ui.grid(columns=3).classes("w-full gap-4"):
                        terminal_name = ui.input("终端名称", value="demo-terminal").classes("w-full")
                        terminal_type = ui.select(
                            {
                                "broker_api": "broker_api",
                                "desktop_terminal": "desktop_terminal",
                                "rest_gateway": "rest_gateway",
                                "fix_gateway": "fix_gateway",
                                "local_sdk": "local_sdk",
                            },
                            value="broker_api",
                            label="终端类型",
                        ).classes("w-full")
                        terminal_official_docs_url = ui.input("官方文档 URL", value="https://docs.example.com/terminal").classes("w-full")
                        terminal_docs_search_url = ui.input("文档搜索 URL", value="").classes("w-full")
                        terminal_api_base_url = ui.input("API Base URL", value="https://api.example.com").classes("w-full")
                        terminal_api_key_envs = ui.input("API Key ENV 列表", value="BROKER_API_KEY").classes("w-full")
                        terminal_auth_style = ui.select({"header": "header", "query": "query", "bearer": "bearer"}, value="header", label="鉴权方式").classes("w-full")
                        terminal_order_endpoint = ui.input("Order Endpoint", value="/orders").classes("w-full")
                        terminal_cancel_endpoint = ui.input("Cancel Endpoint", value="/orders/{id}/cancel").classes("w-full")
                        terminal_order_status_endpoint = ui.input("Order Status Endpoint", value="/orders/{id}").classes("w-full")
                        terminal_positions_endpoint = ui.input("Positions Endpoint", value="/positions").classes("w-full")
                        terminal_balances_endpoint = ui.input("Balances Endpoint", value="/balances").classes("w-full")
                        terminal_docs_summary = ui.textarea("文档摘要", value="Terminal docs summary for generated integration.").props("autogrow").classes("w-full")
                        terminal_user_notes = ui.textarea("用户备注", value="").props("autogrow").classes("w-full")
                        terminal_field_map = ui.textarea("响应字段映射 JSON", value="{}").props("autogrow").classes("w-full")
                    with ui.row().classes("gap-3 mt-3"):
                        terminal_actions.append(ui.button("生成终端接入方案", on_click=expand_terminal_run))
                        terminal_run_select = ui.select({}, label="选择 run").classes("w-72")
                        terminal_commit = ui.switch("提交改动", value=True)
                        terminal_actions.append(ui.button("应用终端接入", on_click=apply_terminal_run, color="secondary"))
                        terminal_actions.append(ui.button("测试终端接入", on_click=test_terminal_run, color="secondary"))
                        terminal_spinner = ui.spinner(size="sm")
                        terminal_spinner.visible = False
                    terminal_note = ui.label("这里会生成终端接入包，并支持应用与 smoke test。").classes("text-sm text-slate-600")
                with ui.grid(columns=2).classes("w-full gap-4"):
                    terminal_panel = ui.column().classes("w-full gap-4")
                    terminal_detail_panel = ui.column().classes("w-full gap-4")

            with ui.tab_panel(intelligence_tab):
                with ui.grid(columns=3).classes("w-full gap-4"):
                    with ui.column().classes("w-full gap-4"):
                        with ui.card().classes("w-full"):
                            ui.label("情报中心").classes("text-h6")
                            ui.label("这里应该先看到情报结论与历史，再决定是否继续细查来源、财报、暗池和期权。").classes("text-sm text-slate-600")
                            intelligence_note = ui.label("搜索结果会挂到当前 session，并自动进入下方历史记录。").classes("text-sm text-slate-600")
                        with ui.card().classes("w-full"):
                            ui.label("单次情报查询").classes("text-h6")
                            intelligence_query = ui.input("查询词", value="TSLA latest market news risks catalysts").classes("w-full")
                            intelligence_max = ui.number("返回数量", value=5, min=1, max=10).classes("w-full")
                            with ui.row().classes("gap-3 mt-3"):
                                intelligence_actions.append(ui.button("查询这条情报", on_click=search_intelligence))
                                intelligence_spinner = ui.spinner(size="sm")
                                intelligence_spinner.visible = False
                        with ui.card().classes("w-full"):
                            ui.label("当前股票列表批量查询").classes("text-h6")
                            ui.label("不用再输入股票列表。系统会直接使用当前会话的交易标的；如果当前会话没有股票池，则从查询词里推断股票代码。").classes("text-sm text-slate-600")
                            with ui.row().classes("gap-3 mt-3"):
                                intelligence_actions.append(ui.button("查询当前股票列表情报", on_click=search_watchlist_intelligence, color="primary"))
                                intelligence_actions.append(ui.button("刷新最新市场数据", on_click=refresh_market_data, color="secondary"))
                        with ui.card().classes("w-full"):
                            ui.label("市场数据补充方式").classes("text-h6")
                            ui.label("情报查询完成后，系统会自动补查当前股票列表的最新财报、暗池和期权数据。你不需要再输入股票代码或其他市场参数。").classes("text-sm text-slate-600")
                    with ui.column().classes("w-full gap-4 col-span-2"):
                        intelligence_overview_panel = ui.column().classes("w-full gap-4")
                        intelligence_watchlist_panel = ui.column().classes("w-full gap-4")
                        intelligence_briefing_panel = ui.column().classes("w-full gap-4")
                        with ui.card().classes("w-full"):
                            ui.label("历史情报查看").classes("text-h6")
                            intelligence_history_select = ui.select({}, label="选择一条历史查询", on_change=lambda _: refresh_all()).classes("w-full")
                        with ui.grid(columns=2).classes("w-full gap-4"):
                            intelligence_documents_panel = ui.column().classes("w-full gap-4")
                            intelligence_history_panel = ui.column().classes("w-full gap-4")
                            intelligence_history_detail_panel = ui.column().classes("w-full gap-4")
                            intelligence_history_payload_panel = ui.column().classes("w-full gap-4")
                            intelligence_financials_panel = ui.column().classes("w-full gap-4")
                            intelligence_dark_pool_panel = ui.column().classes("w-full gap-4")
                            intelligence_options_panel = ui.column().classes("w-full gap-4")
                            intelligence_payload_panel = ui.column().classes("w-full gap-4")

            with ui.tab_panel(health_tab):
                with ui.card().classes("w-full"):
                    ui.label("系统健康").classes("text-h6")
                    ui.label("这里优先给人类看的运营结论、风险和建议动作。原始 JSON 放在底部只作排查用途。").classes("text-sm text-slate-600")
                    ui.button("刷新系统健康", on_click=refresh_health, color="secondary")
                health_overview_panel = ui.column().classes("w-full gap-4")
                with ui.grid(columns=2).classes("w-full gap-4"):
                    health_summary_panel = ui.column().classes("w-full gap-4")
                    health_attention_panel = ui.column().classes("w-full gap-4")
                    health_actions_panel = ui.column().classes("w-full gap-4")
                    health_modules_panel = ui.column().classes("w-full gap-4")
                    health_libraries_panel = ui.column().classes("w-full gap-4")
                    health_agents_panel = ui.column().classes("w-full gap-4")
                health_payload_panel = ui.column().classes("w-full gap-4")

    refresh_all()
    ui.timer(0.1, lambda: asyncio.create_task(refresh_health(False)), once=True)
    ui.timer(0.2, lambda: asyncio.create_task(load_config_state(False)), once=True)
    ui.run(
        title="Sentinel-Alpha NiceGUI",
        host=settings.frontend_host,
        port=settings.frontend_port,
        reload=os.getenv("SENTINEL_UI_RELOAD", "0").lower() in {"1", "true", "yes", "on"},
        show=False,
    )


if __name__ in {"__main__", "__mp_main__"}:
    run()
