from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
import time
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
    auto_session_bootstrapped: bool = False
    health_payload: dict[str, Any] | None = None
    config_payload: dict[str, Any] | None = None
    config_validation: dict[str, Any] | None = None
    config_test_result: dict[str, Any] | None = None
    data_source_health: dict[str, Any] | None = None
    agent_activity_feed: list[dict[str, Any]] = field(default_factory=list)
    local_strategy_logs: list[str] = field(default_factory=list)
    local_simulation_logs: list[str] = field(default_factory=list)
    local_operation_logs: list[str] = field(default_factory=list)
    simulation_focus_started_at: float | None = None
    simulation_loss_refresh_count: int = 0
    simulation_loss_refresh_drawdown_trigger_pct: float | None = None
    simulation_last_advance_at: float | None = None


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


def _join_nonempty(parts: list[str], sep: str = " / ") -> str:
    return sep.join(part for part in parts if str(part).strip())


def _classify_external_issue(message: str | None) -> tuple[str, str]:
    text = str(message or "").strip()
    lowered = text.lower()
    if not text:
        return "结果为空", "当前没有返回可展示的数据，可以稍后重试或检查数据源权限。"
    if any(keyword in lowered for keyword in ("invalid api key", "invalid token", "unauthorized", "401", "forbidden", "403")):
        return "鉴权失败", "请检查 API KEY、套餐权限或 endpoint 授权范围。"
    if any(keyword in lowered for keyword in ("payment", "billing", "plan", "quota", "credit", "429", "rate limit")):
        return "套餐或额度限制", "请检查供应商套餐、额度和速率限制，必要时升级套餐或稍后重试。"
    if any(keyword in lowered for keyword in ("not found", "404", "unsupported", "not supported", "missing capability")):
        return "接口能力不足", "当前接口可能未提供这类数据；如需自动能力，请补充更完整的技术文档或更换供应商。"
    if any(keyword in lowered for keyword in ("timeout", "connection", "temporarily", "unavailable", "network", "reset by peer")):
        return "网络或供应商波动", "这更像临时外部依赖波动，建议稍后重试并查看历史记录是否连续失败。"
    if any(keyword in lowered for keyword in ("empty", "no data", "no results", "no documents")):
        return "当前无数据", "当前查询没有拿到结果，可以换查询词、补充股票池，或稍后再试。"
    return "外部数据失败", "请结合错误详情判断是文档、权限、套餐还是供应商稳定性问题。"


def _session_summary(snapshot: dict[str, Any] | None) -> list[str]:
    if not snapshot:
        return ["默认会话初始化中。"]
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


def _strategy_trading_entries(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    current_pkg = (snapshot or {}).get("strategy_package") or {}
    if current_pkg.get("version_label"):
        entries.append(
            {
                "value": f"current:{current_pkg['version_label']}",
                "label": f"[当前] {current_pkg['version_label']}",
                "version": current_pkg["version_label"],
                "source": "current",
                "pkg": current_pkg,
            }
        )
    for item in _strategy_archive_entries(snapshot):
        version = item.get("version")
        if not version or any(existing["version"] == version for existing in entries):
            continue
        entries.append(
            {
                "value": version,
                "label": f"[历史] {version}",
                "version": version,
                "source": "archive",
                "pkg": item.get("pkg") or {},
            }
        )
    return entries


def _strategy_status_lines(snapshot: dict[str, Any] | None) -> list[str]:
    pkg = (snapshot or {}).get("strategy_package") or {}
    if not pkg:
        return []
    recommended = pkg.get("recommended_variant") or {}
    status_summary = (snapshot or {}).get("strategy_status_summary") or {}
    active = (snapshot or {}).get("active_trading_strategy") or {}
    return [
        f"策略健康状态: {status_summary.get('health_status', 'unknown')}",
        f"策略当前状态: {status_summary.get('current_status', 'unknown')}",
        f"交易限制状态: {status_summary.get('trading_restriction_status', 'unknown')}",
        f"当前交易策略: {active.get('version_label', 'unknown')} / source={active.get('source', 'unknown')} / ref={active.get('strategy_ref', 'unknown')}",
        f"状态说明: {status_summary.get('reason', '无')}",
        f"交易限制说明: {status_summary.get('trading_restriction_summary', '无')}",
        f"当前阶段: {(snapshot or {}).get('phase', 'unknown')}",
        f"当前版本: {pkg.get('version_label', 'unknown')}",
        f"策略类型: {pkg.get('strategy_type', 'unknown')}",
        f"策略方式: {pkg.get('strategy_method', '未说明') or '未说明'}",
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
    requirements = manifest.get("strategy_data_requirements") or {}
    if requirements:
        lines.append(
            f"strategy_requirements / status={requirements.get('status', 'unknown')} / required={', '.join(requirements.get('required_sections') or []) or 'none'} / missing={', '.join(requirements.get('missing_required_sections') or []) or 'none'}"
        )
        lines.extend(f"数据要求说明 / {item}" for item in (requirements.get("guidance") or [])[:4])
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
    lines: list[str] = []
    for item in reversed(remote_logs[-12:]):
        gate = (item.get("research_summary") or {}).get("final_release_gate_summary", {}).get("gate_status", "unknown")
        failed = ", ".join(item.get("failed_checks") or []) or "无"
        focus = "；".join((item.get("research_summary") or {}).get("next_iteration_focus") or []) or "无"
        summary = item.get("analysis_summary") or item.get("error") or "无摘要"
        strategy_method = item.get("strategy_method") or "未说明"
        restriction_summary = (item.get("trade_execution_limits") or {}).get("summary") or "未设置交易限制"
        requirement_status = (item.get("strategy_data_requirements") or {}).get("status") or "unknown"
        lines.append(
            _join_nonempty(
                [
                    f"{item.get('timestamp')}",
                    f"第{item.get('iteration_no', '-')}版",
                    f"状态={item.get('status', 'unknown')}",
                    f"gate={gate}",
                    f"失败检查={failed}",
                ]
            )
        )
        lines.append(f"本轮结论 / {summary}")
        lines.append(f"策略方式 / {strategy_method} / 数据要求={requirement_status} / 交易限制={restriction_summary}")
        if focus != "无":
            lines.append(f"下一步 / {focus}")
    local_logs = [f"本地记录 / {item}" for item in state.local_strategy_logs[-12:]]
    return local_logs + lines


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
    by_agent = usage.get("by_agent") or {}
    aggregate = usage.get("aggregate") or {}
    recent = usage.get("recent_calls") or []
    recommendations = usage.get("model_switch_recommendations") or []
    lines = [
        f"总体调用 / 请求={aggregate.get('api_request_count', 0)} / 总 token={aggregate.get('total_tokens', 0)} / 实时={aggregate.get('live_request_count', 0)} / fallback={aggregate.get('fallback_request_count', 0)}",
        f"稳定性 / fallback_ratio={aggregate.get('fallback_ratio', 0)} / recent_fallback_ratio={aggregate.get('recent_fallback_ratio', 0)} / cache_hit_ratio={aggregate.get('cache_hit_ratio', 0)} / recent_calls={aggregate.get('recent_call_count', 0)}",
    ]
    lines.extend(
        f"Agent / {agent} / calls={info.get('calls', 0)} / total_tokens={info.get('total_tokens', 0)} / fallback_ratio={info.get('fallback_ratio', 0)} / models={', '.join(info.get('models') or []) or 'none'}"
        for agent, info in sorted(by_agent.items(), key=lambda pair: pair[1].get("calls", 0), reverse=True)
    )
    lines.extend(
        f"{item.get('task')} / {item.get('provider')}/{item.get('model')} / calls={item.get('calls')} / cache_hits={item.get('cache_hits', 0)} / in={item.get('input_tokens')} / out={item.get('output_tokens')}"
        for item in sorted(totals, key=lambda row: row.get("calls", 0), reverse=True)
    )
    lines.extend(
        f"模型建议 / {item.get('agent')} / {item.get('message')}"
        for item in recommendations
    )
    lines.extend(
        f"{item.get('timestamp', 'unknown')} / {item.get('owner_agent', item.get('task'))} / {item.get('task')} / {item.get('provider')}/{item.get('model')} / in={item.get('input_tokens')} / out={item.get('output_tokens')}"
        for item in reversed(recent[-5:])
    )
    return lines


def _programmer_runs_lines(snapshot: dict[str, Any] | None) -> list[str]:
    runs = (snapshot or {}).get("programmer_runs") or []
    lines: list[str] = []
    for item in reversed(runs):
        chain = item.get("repair_chain_summary") or {}
        acceptance = item.get("acceptance_summary") or {}
        rollback = item.get("rollback_summary") or {}
        promotion = item.get("promotion_summary") or {}
        dry_run = not bool(item.get("commit_hash")) and "dry-run" in str(item.get("validation_detail", "")).lower()
        lines.append(
            _join_nonempty(
                [
                    f"{item.get('timestamp', 'unknown')}",
                    f"状态={item.get('status', 'unknown')}",
                    f"失败类型={item.get('failure_type', 'none')}",
                    f"{'dry-run' if dry_run else 'commit'}={item.get('commit_hash', '未写入') if not dry_run else '未写入'}",
                    f"files={', '.join(item.get('changed_files') or []) or 'none'}",
                ]
            )
        )
        if item.get("scope_violation"):
            lines.append(f"边界拦截 / {item.get('scope_violation')}")
        if item.get("repair_plan", {}).get("actions"):
            lines.append(
                f"修复计划 / {item.get('repair_plan', {}).get('priority', 'P1')} / {'；'.join(item.get('repair_plan', {}).get('actions') or [])}"
            )
        if item.get("validation_detail"):
            lines.append(f"验证结果 / {item.get('validation_detail')}")
        if chain:
            lines.append(
                f"修复链路 / status={chain.get('chain_status', 'unknown')} / decision={chain.get('primary_decision', 'unknown')} / next_mode={chain.get('next_mode', 'unknown')}"
            )
        if acceptance:
            lines.append(f"接受判断 / {acceptance.get('note', '无')}")
        if rollback:
            lines.append(f"回退建议 / {rollback.get('note', '无')}")
        if promotion:
            lines.append(f"提升建议 / {promotion.get('note', '无')}")
    return lines


def _programmer_stats_lines(snapshot: dict[str, Any] | None) -> list[str]:
    runs = (snapshot or {}).get("programmer_runs") or []
    counts: dict[str, int] = {}
    for run in runs:
        kind = run.get("failure_type") or ("success" if run.get("status") == "ok" else "unknown")
        counts[kind] = counts.get(kind, 0) + 1
    lines = [f"失败统计 / {name}: {count}" for name, count in sorted(counts.items(), key=lambda pair: pair[1], reverse=True)]
    lines.extend(
        f"最近失败 / {item.get('timestamp', 'unknown')} / {item.get('failure_type', 'unknown')} / {item.get('validation_detail') or item.get('stderr') or item.get('error') or 'no detail'}"
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
        issue, action = _classify_external_issue(run.get("error"))
        return [
            f"这次查询失败了 / {issue}",
            f"错误详情 / {run.get('error', 'unknown error')}",
            f"建议 / {action}",
            "当前页面仍然保留这次失败记录，方便你判断是查询词问题、API 问题，还是外部数据源问题。",
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
            issue, action = _classify_external_issue(latest_run.get("error"))
            lines.append(f"状态判断 / {issue}")
            lines.append(f"错误 / {latest_run.get('error')}")
            lines.append(f"建议 / {action}")
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


def _intelligence_history_run_cards(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    runs = list((snapshot or {}).get("intelligence_runs") or [])
    cards: list[dict[str, Any]] = []
    for item in reversed(runs):
        report = item.get("report") or {}
        translated_documents = list(report.get("translated_documents") or item.get("documents") or [])
        first_document = translated_documents[0] if translated_documents else {}
        cards.append(
            {
                "run_id": item.get("run_id") or item.get("generated_at") or "unknown",
                "query": item.get("query", "unknown"),
                "symbol": _infer_symbol_from_query(item.get("query")),
                "timestamp": item.get("timestamp") or item.get("generated_at") or "unknown",
                "document_count": item.get("document_count", 0),
                "cache_hit": bool(item.get("cache_hit")),
                "status": item.get("status") or ("warning" if item.get("document_count", 0) == 0 else "ok"),
                "localized_summary": report.get("summary") or report.get("report_summary") or "无中文总结",
                "translated_headline": first_document.get("translated_title") or first_document.get("title") or "无标题",
                "original_headline": first_document.get("title") or "无原标题",
                "translated_summary": first_document.get("brief_summary_cn") or first_document.get("translated_summary") or first_document.get("summary") or "无中文摘要",
                "source": first_document.get("source") or "unknown",
                "url": first_document.get("url") or "",
                "translated_documents": translated_documents,
            }
        )
    return cards


def _intelligence_history_filter_options(snapshot: dict[str, Any] | None) -> tuple[dict[str, str], dict[str, str]]:
    cards = _intelligence_history_run_cards(snapshot)
    symbols = sorted({str(item.get("symbol") or "UNKNOWN") for item in cards})
    sources = sorted({str(item.get("source") or "unknown") for item in cards})
    return (
        {"all": "全部股票", **{item: item for item in symbols}},
        {"all": "全部来源", **{item: item for item in sources}},
    )


def _filter_intelligence_history_cards(
    cards: list[dict[str, Any]],
    *,
    symbol_filter: str = "all",
    source_filter: str = "all",
    translated_only: bool = False,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for item in cards:
        if symbol_filter != "all" and str(item.get("symbol") or "UNKNOWN") != symbol_filter:
            continue
        if source_filter != "all" and str(item.get("source") or "unknown") != source_filter:
            continue
        if translated_only and not str(item.get("translated_summary") or "").strip():
            continue
        filtered.append(item)
    return filtered


def _normalize_intelligence_topic(text: str | None) -> str:
    raw = str(text or "").strip().lower()
    if not raw:
        return "unknown"
    normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", raw)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _parse_iso_datetime(value: str | None) -> Any:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")) if "T" in text else datetime.fromisoformat(f"{text}T00:00:00")
    except Exception:
        return None


def _group_intelligence_history_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for item in cards:
        headline = str(item.get("translated_headline") or item.get("original_headline") or "unknown")
        key = (str(item.get("symbol") or "UNKNOWN"), _normalize_intelligence_topic(headline))
        bucket = groups.setdefault(
            key,
            {
                "symbol": item.get("symbol") or "UNKNOWN",
                "topic": headline,
                "count": 0,
                "latest_timestamp": item.get("timestamp") or "unknown",
                "sources": set(),
                "queries": [],
                "queries_timestamps": [],
                "localized_summary": item.get("localized_summary") or "无中文总结",
            },
        )
        bucket["count"] = int(bucket["count"]) + 1
        if str(item.get("timestamp") or "") > str(bucket.get("latest_timestamp") or ""):
            bucket["latest_timestamp"] = item.get("timestamp") or bucket.get("latest_timestamp")
            bucket["localized_summary"] = item.get("localized_summary") or bucket.get("localized_summary")
        if item.get("source"):
            bucket["sources"].add(str(item.get("source")))
        bucket["queries"].append(item.get("query") or "unknown")
        bucket["queries_timestamps"].append(item.get("timestamp") or "")
    result: list[dict[str, Any]] = []
    for item in groups.values():
        result.append(
            {
                "symbol": item["symbol"],
                "topic": item["topic"],
                "count": item["count"],
                "latest_timestamp": item["latest_timestamp"],
                "source_count": len(item["sources"]),
                "sources": sorted(item["sources"]),
                "queries": item["queries"],
                "queries_timestamps": item["queries_timestamps"],
                "localized_summary": item["localized_summary"],
            }
        )
    for item in result:
        risk_flags: list[str] = []
        next_actions: list[str] = []
        timestamps = sorted(
            [
                parsed
                for parsed in (_parse_iso_datetime(ts) for ts in item.get("queries_timestamps", []) if ts)
                if parsed is not None
            ]
        )
        count = int(item.get("count") or 0)
        if count >= 2:
            risk_flags.append("同一主题被重复查询，存在确认偏误风险")
            next_actions.append("先复用已有结论，再判断是否真的需要继续搜索同一主题")
        if len(timestamps) >= 2:
            latest = timestamps[-1]
            previous = timestamps[-2]
            try:
                delta_seconds = (latest - previous).total_seconds()
            except Exception:
                delta_seconds = 0
            if delta_seconds <= 3600:
                risk_flags.append("同一主题在短时间内被再次查询，存在焦虑确认风险")
                next_actions.append("短时间内先暂停重复确认，优先检查是否由回撤或波动触发")
        item["risk_flags"] = risk_flags
        item["next_actions"] = next_actions
    return sorted(result, key=lambda item: (str(item.get("latest_timestamp") or ""), int(item.get("count") or 0)), reverse=True)


def _intelligence_history_analysis_lines(snapshot: dict[str, Any] | None) -> list[str]:
    analysis = (snapshot or {}).get("intelligence_history_analysis") or {}
    if not analysis:
        return []
    return [
        f"查询节奏 / {analysis.get('query_frequency_summary', '无')}",
        f"是否频繁查询 / {'是' if analysis.get('is_frequent_querying') else '否'}",
        f"重复搜索 / {analysis.get('repeated_search_summary', '无')}",
        f"是否频繁重复搜索 / {'是' if analysis.get('is_repeated_searching') else '否'}",
        f"重复主题组 / {analysis.get('repeated_topic_group_count', 0)}",
        f"短时重复主题组 / {analysis.get('burst_topic_group_count', 0)}",
        f"是否存在主题级确认偏误 / {'是' if analysis.get('has_topic_confirmation_bias') else '否'}",
        f"是否存在主题级焦虑确认 / {'是' if analysis.get('has_topic_anxiety_confirmation') else '否'}",
        f"历史结论 / {analysis.get('history_summary', '无')}",
        f"模拟建议 / {analysis.get('simulation_training_note', '无')}",
        f"分析方式 / {analysis.get('generation_mode', 'unknown')} / {analysis.get('analysis_status', 'unknown')}",
        *(f"风险 / {item}" for item in (analysis.get("risk_flags") or [])),
        *(f"下一步 / {item}" for item in (analysis.get("next_actions") or [])),
    ]


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


def _intelligence_history_document_lines(run: dict[str, Any] | None) -> list[str]:
    report = (run or {}).get("report") or {}
    documents = list(report.get("translated_documents") or (run or {}).get("documents") or [])
    lines: list[str] = []
    for index, item in enumerate(documents[:8], start=1):
        lines.extend(
            [
                f"第{index}条 / 来源={item.get('source', 'unknown')}",
                f"中文标题 / {item.get('translated_title') or item.get('title') or '无'}",
                f"原文标题 / {item.get('title') or '无'}",
                f"中文摘要 / {item.get('brief_summary_cn') or item.get('translated_summary') or item.get('summary') or '无'}",
                f"链接 / {item.get('url') or '无'}",
            ]
        )
    return lines


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
        "avg_chart_focus_seconds",
        "anxiety_refresh_event_ratio",
        "manual_intervention_rate",
        "trust_decay_score",
    ):
        if key in report:
            lines.append(f"{key} / {report.get(key)}")
    capture = report.get("behavior_capture_summary") or {}
    if capture:
        lines.append(
            "行为捕获 / "
            f"avg_focus={capture.get('avg_chart_focus_seconds', 0)}s / "
            f"refresh={capture.get('avg_loss_refresh_count', 0)} / "
            f"manual={capture.get('manual_intervention_count', 0)} / "
            f"trust_decay={capture.get('trust_decay_score', 0)}"
        )
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


def _simulation_training_state_lines(snapshot: dict[str, Any] | None) -> list[str]:
    state = (snapshot or {}).get("simulation_training_state") or {}
    if not state:
        return []
    return [
        f"当前阶段 / {state.get('lifecycle_stage', 'unknown')}",
        f"模拟状态 / {state.get('invalidation_status', 'unknown')}",
        f"当前行为样本 / {state.get('behavior_event_count', 0)} / 训练后新增={state.get('post_training_behavior_event_count', 0)}",
        f"最近训练策略 / {state.get('latest_strategy_version', '未训练')}",
        f"下一步 / {state.get('next_action', '无')}",
        *(f"失效原因 / {item}" for item in (state.get("invalidation_reasons") or [])),
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


def _habit_goal_current_lines(snapshot: dict[str, Any] | None) -> list[str]:
    current = ((snapshot or {}).get("habit_goal_evolution") or {}).get("current") or {}
    if not current:
        return []
    return [
        f"当前结论 / {current.get('combined_summary', '无')}",
        f"习惯判断 / {current.get('habit_summary', '无')}",
        f"目标判断 / {current.get('goal_summary', '无')}",
        f"当前重点 / {current.get('current_focus', '无')}",
        f"分析方式 / {current.get('generation_mode', 'unknown')} / {current.get('analysis_status', 'unknown')}",
        f"交易限制 / {current.get('trading_restriction_summary', '无')}",
        (
            "行为捕获 / "
            f"avg_focus={((current.get('behavior_capture_summary') or {}).get('avg_chart_focus_seconds', 0))}s / "
            f"refresh={((current.get('behavior_capture_summary') or {}).get('avg_loss_refresh_count', 0))} / "
            f"manual={((current.get('behavior_capture_summary') or {}).get('manual_intervention_count', 0))} / "
            f"trust_decay={((current.get('behavior_capture_summary') or {}).get('trust_decay_score', 0))}"
        ),
    ]


def _habit_goal_risk_lines(snapshot: dict[str, Any] | None) -> list[str]:
    current = ((snapshot or {}).get("habit_goal_evolution") or {}).get("current") or {}
    if not current:
        return []
    return [
        *(f"风险 / {item}" for item in (current.get("risk_flags") or [])),
        *(f"下一步 / {item}" for item in (current.get("next_actions") or [])),
        *(f"需要你补充 / {item}" for item in (current.get("required_user_inputs") or [])),
        f"一致性判断 / {current.get('consistency_assessment', '无')}",
        f"置信说明 / {current.get('confidence_note', '无')}",
    ]


def _habit_goal_shift_lines(snapshot: dict[str, Any] | None) -> list[str]:
    current = ((snapshot or {}).get("habit_goal_evolution") or {}).get("current") or {}
    if not current:
        return []
    return [
        f"习惯变化 / {current.get('habit_shift', '无')}",
        f"目标变化 / {current.get('goal_shift', '无')}",
    ]


def _habit_goal_history_lines(snapshot: dict[str, Any] | None) -> list[str]:
    history = ((snapshot or {}).get("habit_goal_evolution") or {}).get("history") or []
    return [
        f"{item.get('timestamp', 'unknown')} / {item.get('source_type', 'unknown')} / {item.get('source_ref', 'unknown')} / {item.get('combined_summary', '无摘要')}"
        for item in reversed(history[-30:])
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


def _execution_mode_label(mode: str | None) -> str:
    mapping = {
        "autonomous": "自动执行",
        "advice_only": "仅建议，不自动下单",
        "manual": "人工记录",
    }
    return mapping.get(str(mode or "").strip(), str(mode or "未设置"))


def _operation_overview_lines(snapshot: dict[str, Any] | None) -> list[str]:
    payload = snapshot or {}
    active = payload.get("active_trading_strategy") or {}
    status = payload.get("strategy_status_summary") or {}
    universe = payload.get("trade_universe") or {}
    requested = [str(item).strip().upper() for item in (universe.get("requested") or universe.get("symbols") or []) if str(item).strip()]
    events = payload.get("history_events") or []
    monitors = payload.get("monitors") or []
    latest_trade = next((item for item in reversed(events) if item.get("event_type") == "trade_execution_recorded"), None)
    latest_info = next((item for item in reversed(events) if item.get("event_type") == "information_event_recorded"), None)
    return [
        f"当前执行模式 / {_execution_mode_label(payload.get('execution_mode'))}",
        f"当前交易策略 / {active.get('version_label', '未选择')} / 健康={status.get('health_status', 'unknown')} / 状态={status.get('current_status', 'unknown')}",
        f"当前股票池 / {', '.join(requested) or '未设置'}",
        f"最近交易记录 / {(latest_trade or {}).get('summary', '当前还没有交易记录。')}",
        f"最近消息记录 / {(latest_info or {}).get('summary', '当前还没有消息记录。')}",
        f"监控提醒数量 / {len(monitors)}",
    ]


def _operation_local_log_lines(local_logs: list[str] | None) -> list[str]:
    return [f"页面记录 / {item}" for item in (local_logs or [])[-20:]]


def _agent_activity_lines(entries: list[dict[str, Any]] | None) -> list[str]:
    items = entries or []
    return [
        f"{item.get('sequence', '?')} / {item.get('timestamp', 'unknown')} / {item.get('agent', 'unknown')} / "
        f"{item.get('operation', 'unknown')} / {item.get('status', 'unknown')} / {item.get('detail', '无摘要')}"
        for item in reversed(items[-80:])
    ]


def _data_source_lines(snapshot: dict[str, Any] | None) -> list[str]:
    runs = (snapshot or {}).get("data_source_runs") or []
    return [
        f"{item.get('timestamp', item.get('generated_at', 'unknown'))} / {item.get('provider', 'unknown')} / {item.get('status', 'unknown')} / analysis={((item.get('analysis') or {}).get('generation_mode', 'unknown'))} / smoke={((item.get('smoke_test') or {}).get('status', 'not_run'))} / {item.get('summary', item.get('message', '无摘要'))}"
        for item in reversed(runs[-20:])
    ]


def _data_source_health_lines(payload: dict[str, Any] | None) -> list[str]:
    health = payload or {}
    summary = health.get("summary") or {}
    return [
        f"当前状态 / {health.get('status', 'unknown')}",
        f"一句话结论 / {summary.get('conclusion', '无结论')}",
        f"已配置数据源 / {summary.get('configured_provider_count', 0)}",
        f"扩展 run / {summary.get('expanded_run_count', 0)}",
        f"健康 run / {summary.get('healthy_runs', 0)}",
        f"警告 run / {summary.get('warning_runs', 0)}",
        f"待测试 run / {summary.get('generated_not_tested_runs', 0)}",
    ]


def _data_source_health_action_lines(payload: dict[str, Any] | None) -> list[str]:
    summary = (payload or {}).get("summary") or {}
    actions = [str(item) for item in summary.get("next_actions") or [] if str(item).strip()]
    notes = [str(item) for item in summary.get("notes") or [] if str(item).strip()]
    return [*(f"note / {item}" for item in notes), *(f"action / {item}" for item in actions)]


def _configured_provider_health_lines(payload: dict[str, Any] | None) -> list[str]:
    health = payload or {}
    configured = health.get("configured_providers") or {}
    lines: list[str] = []
    for family in ["market_data", "fundamentals", "dark_pool", "options_data"]:
        for item in configured.get(family) or []:
            lines.append(
                f"{family} / {item.get('provider', 'unknown')} / status={item.get('status', 'unknown')} / "
                f"enabled={item.get('enabled', False)} / {item.get('detail', '')}"
            )
    return lines


def _configured_provider_health_rows(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    health = payload or {}
    configured = health.get("configured_providers") or {}
    rows: list[dict[str, Any]] = []
    for family in ["market_data", "fundamentals", "dark_pool", "options_data"]:
        for item in configured.get(family) or []:
            rows.append(
                {
                    "family": family,
                    "provider": item.get("provider", "unknown"),
                    "status": item.get("status", "unknown"),
                    "enabled": "是" if item.get("enabled", False) else "否",
                    "api_key": "已配置" if item.get("api_key_present") else "未配置",
                    "base_url": item.get("base_url", "") or "-",
                    "detail": item.get("detail", "") or "-",
                }
            )
    return rows


def _expanded_run_health_lines(payload: dict[str, Any] | None) -> list[str]:
    runs = (payload or {}).get("expanded_runs") or []
    return [
        f"{item.get('run_id', 'unknown')} / {item.get('provider_name', 'unknown')} / {item.get('category', 'unknown')} / "
        f"status={item.get('status', 'unknown')} / smoke={item.get('smoke_status', 'not_run')} / "
        f"live={item.get('live_fetch_status', 'not_run')} / apply={item.get('apply_status', 'not_applied')}"
        for item in runs
    ]


def _terminal_lines(snapshot: dict[str, Any] | None) -> list[str]:
    runs = (snapshot or {}).get("terminal_integration_runs") or []
    lines: list[str] = []
    for item in reversed(runs[-20:]):
        readiness = item.get("integration_readiness_summary") or {}
        exchange = item.get("exchange_support_summary") or {}
        required_missing = ",".join(readiness.get("missing_required_capabilities") or []) or "none"
        optional_missing = ",".join(readiness.get("missing_optional_capabilities") or []) or "none"
        lines.append(
            f"{item.get('timestamp', 'unknown')} / {item.get('terminal_name', 'unknown')} / type={item.get('terminal_type', 'unknown')} / "
            f"auto_trading_ready={readiness.get('automatic_trading_ready', False)} / required_missing={required_missing} / optional_missing={optional_missing} / "
            f"exchange_scope={exchange.get('scope', 'unknown')}"
        )
    return lines


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
        f"strategy_method / {pkg.get('strategy_method', '未说明') or '未说明'}",
        f"objective_metric / {pkg.get('objective_metric', 'unknown')}",
        f"trade_execution_limits / {(pkg.get('trade_execution_limits') or {}).get('summary', '未设置')}",
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
    max_trade_allocation_pct_value: Any | None = None,
    max_trade_amount_value: Any | None = None,
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
    max_trade_allocation_pct = _float(max_trade_allocation_pct_value, 10.0)
    max_trade_amount_raw = _float(max_trade_amount_value, 0.0) if max_trade_amount_value not in (None, "") else None
    max_trade_amount = max_trade_amount_raw if max_trade_amount_raw and max_trade_amount_raw > 0 else None
    infos.extend(
        [
            f"目标收益 / {target_return_pct:.2f}%",
            f"目标胜率 / {target_win_rate_pct:.2f}%",
            f"目标回撤 / {target_drawdown_pct:.2f}%",
            f"目标最大亏损 / {target_max_loss_pct:.2f}%",
            f"单笔交易资金占比上限 / {max_trade_allocation_pct:.2f}%",
            f"单笔交易金额上限 / {max_trade_amount:.2f}" if max_trade_amount is not None else "单笔交易金额上限 / 未额外设置",
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
    if not 0 < max_trade_allocation_pct <= 100:
        errors.append("单笔交易资金占比上限必须在 0 到 100 之间。")
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
            with ui.card().classes("w-full border border-slate-200 shadow-sm rounded-xl"):
                ui.label(title).classes("text-h6")
                ui.markdown(_lines_markdown(lines, empty)).classes("w-full")

    def render_intelligence_history_cards(container, *, title: str, cards: list[dict[str, Any]], empty: str) -> None:
        with container:
            with ui.card().classes("w-full border border-slate-200 shadow-sm rounded-xl"):
                ui.label(title).classes("text-h6")
                if not cards:
                    ui.label(empty).classes("text-sm text-slate-500")
                for item in cards:
                    with ui.expansion(
                        f"{item.get('timestamp')} / {item.get('query')} / {item.get('document_count', 0)} docs / {item.get('status')}"
                    ).classes("w-full"):
                        ui.label(f"中文总结：{item.get('localized_summary', '无')}").classes("text-sm")
                        ui.label(f"中文标题：{item.get('translated_headline', '无')}").classes("text-sm")
                        ui.label(f"原文标题：{item.get('original_headline', '无')}").classes("text-sm text-slate-600")
                        ui.label(f"中文摘要：{item.get('translated_summary', '无')}").classes("text-sm")
                        ui.label(f"来源：{item.get('source', 'unknown')}").classes("text-xs text-slate-500")
                        if item.get("url"):
                            ui.link(str(item.get("url")), str(item.get("url")), new_tab=True).classes("text-xs")

    def render_intelligence_topic_groups(container, *, title: str, groups: list[dict[str, Any]], empty: str) -> None:
        with container:
            with ui.card().classes("w-full border border-slate-200 shadow-sm rounded-xl"):
                ui.label(title).classes("text-h6")
                if not groups:
                    ui.label(empty).classes("text-sm text-slate-500")
                for item in groups:
                    with ui.expansion(
                        f"{item.get('latest_timestamp')} / {item.get('symbol')} / {item.get('topic')} / 重复={item.get('count')}"
                    ).classes("w-full"):
                        ui.label(f"最新总结：{item.get('localized_summary', '无')}").classes("text-sm")
                        ui.label(f"来源数：{item.get('source_count', 0)} / 来源={', '.join(item.get('sources') or []) or 'unknown'}").classes("text-sm text-slate-600")
                        ui.label(f"相关查询：{'; '.join(item.get('queries') or [])}").classes("text-sm")
                        for risk in item.get("risk_flags") or []:
                            ui.label(f"风险：{risk}").classes("text-sm text-red-700")
                        for action in item.get("next_actions") or []:
                            ui.label(f"建议：{action}").classes("text-sm text-amber-700")

    def render_code_card(container, *, title: str, code: str) -> None:
        with container:
            with ui.card().classes("w-full border border-slate-200 shadow-sm rounded-xl"):
                ui.label(title).classes("text-h6")
                ui.code(code, language="python").classes("w-full text-sm")

    def render_json_card(container, *, title: str, payload: Any) -> None:
        with container:
            with ui.card().classes("w-full border border-slate-200 shadow-sm rounded-xl"):
                ui.label(title).classes("text-h6")
                ui.code(_pretty(payload), language="json").classes("w-full text-sm")

    def render_table_card(
        container,
        *,
        title: str,
        columns: list[dict[str, Any]],
        rows: list[dict[str, Any]],
        empty: str,
        row_key: str = "provider",
    ) -> None:
        with container:
            with ui.card().classes("w-full border border-slate-200 shadow-sm rounded-xl"):
                ui.label(title).classes("text-h6")
                if not rows:
                    ui.markdown(empty).classes("w-full")
                else:
                    ui.table(columns=columns, rows=rows, row_key=row_key, pagination=10).classes("w-full")

    def render_chart_card(container, *, title: str, option: dict[str, Any] | None, empty: str) -> None:
        with container:
            with ui.card().classes("w-full border border-slate-200 shadow-sm rounded-xl"):
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
        sync_llm_config_inputs(state.config_payload)
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

    def sync_llm_config_inputs(payload: dict[str, Any] | None) -> None:
        llm_section = ((payload or {}).get("llm") or {})
        default_provider_input.value = llm_section.get("default_provider") or "google"
        default_models_input.value = ", ".join(llm_section.get("default_models") or [])
        default_temperature_input.value = float(llm_section.get("default_temperature") or 0.2)
        default_max_tokens_input.value = int(llm_section.get("default_max_tokens") or 1200)
        for control in (
            default_provider_input,
            default_models_input,
            default_temperature_input,
            default_max_tokens_input,
        ):
            control.update()
        agents = (llm_section.get("agents") or {})
        selected_agent = str(agent_model_agent_select.value or "strategy_evolver")
        agent_cfg = agents.get(selected_agent) or {}
        agent_model_provider_input.value = agent_cfg.get("provider") or llm_section.get("default_provider") or "google"
        agent_model_models_input.value = ", ".join(agent_cfg.get("models") or [])
        agent_model_temperature_input.value = float(agent_cfg.get("temperature") or llm_section.get("default_temperature") or 0.2)
        agent_model_max_tokens_input.value = int(agent_cfg.get("max_tokens") or llm_section.get("default_max_tokens") or 1200)
        for control in (
            agent_model_provider_input,
            agent_model_models_input,
            agent_model_temperature_input,
            agent_model_max_tokens_input,
        ):
            control.update()

    def apply_llm_forms_to_editor() -> dict[str, Any]:
        payload = _config_editor_payload()
        llm_section = payload.setdefault("llm", {})
        llm_section["default_provider"] = str(default_provider_input.value or "google").strip() or "google"
        llm_section["default_models"] = [item.strip() for item in str(default_models_input.value or "").split(",") if item.strip()]
        llm_section["default_temperature"] = float(default_temperature_input.value or 0.2)
        llm_section["default_max_tokens"] = int(default_max_tokens_input.value or 1200)
        agents = llm_section.setdefault("agents", {})
        selected_agent = str(agent_model_agent_select.value or "strategy_evolver").strip()
        agents[selected_agent] = {
            "provider": str(agent_model_provider_input.value or llm_section["default_provider"]).strip() or llm_section["default_provider"],
            "models": [item.strip() for item in str(agent_model_models_input.value or "").split(",") if item.strip()] or list(llm_section["default_models"]),
            "temperature": float(agent_model_temperature_input.value or llm_section["default_temperature"]),
            "max_tokens": int(agent_model_max_tokens_input.value or llm_section["default_max_tokens"]),
        }
        config_editor.value = _pretty(payload)
        config_editor.update()
        state.config_payload = payload
        return payload

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
            state.data_source_health = await _call_api("GET", api_base, f"/api/sessions/{state.session_id}/data-source/health")
            session_note.text = "会话已创建并补齐训练前置条件。"
            ui.notify(f"会话已创建: {state.session_id}", color="positive")
            refresh_all()
        except Exception as exc:  # pragma: no cover - UI feedback path
            session_note.text = f"创建会话失败: {exc}"
            ui.notify(f"创建会话失败: {exc}", color="negative")
        finally:
            _set_action_state(session_actions, session_spinner, False)

    async def ensure_default_session() -> None:
        if state.auto_session_bootstrapped or state.session_id:
            return
        state.auto_session_bootstrapped = True
        session_note.text = "默认会话初始化中，请稍候..."
        try:
            await create_session()
        except Exception:  # pragma: no cover - create_session already emits UI feedback
            pass

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
            state.data_source_health = await _call_api("GET", api_base, f"/api/sessions/{state.session_id}/data-source/health")
            session_note.text = "会话已加载。"
            ui.notify("会话已加载", color="positive")
            refresh_all()
        except Exception as exc:  # pragma: no cover - UI feedback path
            session_note.text = f"加载会话失败: {exc}"
            ui.notify(f"加载会话失败: {exc}", color="negative")
        finally:
            _set_action_state(session_actions, session_spinner, False)

    async def refresh_agent_activity() -> None:
        if not state.session_id:
            return
        try:
            payload = await _call_api("GET", api_base, f"/api/sessions/{state.session_id}/agent-activity")
            state.agent_activity_feed = list(payload.get("events") or [])
        except Exception:
            return

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
            sync_llm_config_inputs(state.config_payload)
            config_note.text = "配置已保存。" + (f" 已自动备份到 {result.get('backup_path')}。" if result.get("backup_path") else "")
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
            config_note.text = "配置全量测试已完成。" + (f" 已自动备份到 {result.get('backup_path')}。" if result.get("backup_path") else "")
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
            config_note.text = "单项配置测试已完成。" + (f" 已自动备份到 {result.get('backup_path')}。" if result.get("backup_path") else "")
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
            max_trade_allocation_pct_value=max_trade_allocation_pct.value,
            max_trade_amount_value=max_trade_amount.value,
        )
        if validation_errors:
            strategy_note.text = "训练参数校验失败： " + "；".join(validation_errors)
            refresh_all()
            return
        max_trade_pct_value = float(max_trade_allocation_pct.value or 10)
        raw_max_trade_amount = float(max_trade_amount.value) if max_trade_amount.value not in (None, "") else None
        max_trade_amount_value = raw_max_trade_amount if raw_max_trade_amount and raw_max_trade_amount > 0 else None
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
            "strategy_method": strategy_method.value or None,
            "strategy_description": strategy_description.value or None,
            "auto_iterations": int(auto_iterations.value or 1),
            "iteration_mode": iteration_mode.value,
            "objective_metric": objective_metric.value,
            "target_return_pct": float(target_return.value or 18),
            "target_win_rate_pct": float(target_win_rate.value or 58),
            "target_drawdown_pct": float(target_drawdown.value or 12),
            "target_max_loss_pct": float(target_max_loss.value or 6),
            "max_trade_allocation_pct": max_trade_pct_value,
            "max_trade_amount": max_trade_amount_value,
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
                    "策略训练失败：真实股票数据不足或缺失。系统已经先尝试自动补充历史数据，但当前可用 provider 仍不足。"
                    "请进入“数据源扩展”工作台，提供 API KEY 与接口文档，生成并测试真实数据源后再重新训练。"
                )
            elif "当前策略方式所需数据不足" in detail:
                strategy_note.text = detail
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
            state.data_source_health = await _call_api("GET", api_base, f"/api/sessions/{state.session_id}/data-source/health")
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
            state.data_source_health = await _call_api("GET", api_base, f"/api/sessions/{state.session_id}/data-source/health")
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
            state.data_source_health = await _call_api("GET", api_base, f"/api/sessions/{state.session_id}/data-source/health")
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

    def load_selected_data_source_run() -> None:
        run = _selected_run((state.snapshot or {}).get("data_source_runs") or [], data_source_run_select.value) or _latest((state.snapshot or {}).get("data_source_runs") or [])
        if not run:
            return
        data_source_api_key.value = ""
        data_source_interface_documentation.value = ""
        if run.get("inference", {}).get("docs_url"):
            data_source_interface_documentation.value = str(run["inference"]["docs_url"])
        update_provider_name.value = str(run.get("provider_name") or "")
        update_provider_family.value = str(run.get("category") or "market_data")
        update_base_url.value = str((run.get("inference") or {}).get("base_url") or "")
        update_api_key_envs.value = ", ".join((run.get("inference") or {}).get("api_key_envs") or [])
        data_source_interface_documentation.update()
        update_provider_name.update()
        update_provider_family.update()
        update_base_url.update()
        update_api_key_envs.update()

    async def refresh_data_source_health() -> None:
        if not state.session_id:
            data_source_note.text = "请先创建或加载会话。"
            return
        try:
            state.data_source_health = await _call_api("GET", api_base, f"/api/sessions/{state.session_id}/data-source/health")
            refresh_all()
        except Exception as exc:  # pragma: no cover
            data_source_note.text = f"数据源健康检查失败: {exc}"
            ui.notify(str(exc), color="negative")

    async def update_data_source_run() -> None:
        if not state.session_id or not data_source_run_select.value:
            data_source_note.text = "请先选择要更新的数据源扩展 run。"
            return
        _set_action_state(data_source_actions, data_source_spinner, True)
        data_source_note.text = "数据源扩展更新中，请稍候..."
        try:
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/data-source/update",
                {
                    "run_id": data_source_run_select.value,
                    "api_key": data_source_api_key.value or None,
                    "interface_documentation": data_source_interface_documentation.value or "",
                    "provider_name": update_provider_name.value or None,
                    "category": update_provider_family.value or None,
                    "base_url": update_base_url.value or None,
                    "api_key_envs": [item.strip() for item in (update_api_key_envs.value or "").split(",") if item.strip()],
                },
            )
            state.snapshot = snapshot
            data_source_note.text = "数据源扩展方案已更新。建议重新执行 smoke test。"
            await refresh_data_source_health()
        except Exception as exc:  # pragma: no cover
            data_source_note.text = f"数据源扩展更新失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(data_source_actions, data_source_spinner, False)

    async def delete_data_source_run() -> None:
        if not state.session_id or not data_source_run_select.value:
            data_source_note.text = "请先选择要删除的数据源扩展 run。"
            return
        _set_action_state(data_source_actions, data_source_spinner, True)
        data_source_note.text = "数据源扩展删除中，请稍候..."
        try:
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/data-source/delete",
                {"run_id": data_source_run_select.value},
            )
            state.snapshot = snapshot
            data_source_note.text = "数据源扩展方案已删除。"
            await refresh_data_source_health()
        except Exception as exc:  # pragma: no cover
            data_source_note.text = f"数据源扩展删除失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(data_source_actions, data_source_spinner, False)

    async def save_configured_data_source_provider() -> None:
        try:
            result = await _call_api(
                "POST",
                api_base,
                "/api/config/data-source/provider",
                {
                    "family": configured_provider_family.value,
                    "provider": configured_provider_name.value,
                    "enabled": bool(configured_provider_enabled.value),
                    "set_as_default": bool(configured_provider_default.value),
                    "base_url": configured_provider_base_url.value or None,
                    "base_path": configured_provider_base_path.value or None,
                    "api_key_envs": [item.strip() for item in (configured_provider_api_key_envs.value or "").split(",") if item.strip()],
                },
            )
            state.config_payload = result.get("payload")
            state.config_validation = result.get("validation")
            data_source_note.text = f"数据源配置已保存：{configured_provider_family.value}/{configured_provider_name.value}"
            await refresh_data_source_health()
        except Exception as exc:  # pragma: no cover
            data_source_note.text = f"数据源配置保存失败: {exc}"
            ui.notify(str(exc), color="negative")

    async def delete_configured_data_source_provider() -> None:
        try:
            result = await _call_api(
                "POST",
                api_base,
                "/api/config/data-source/provider/delete",
                {
                    "family": configured_provider_family.value,
                    "provider": configured_provider_name.value,
                },
            )
            state.config_payload = result.get("payload")
            state.config_validation = result.get("validation")
            data_source_note.text = f"数据源配置已删除：{configured_provider_family.value}/{configured_provider_name.value}"
            await refresh_data_source_health()
        except Exception as exc:  # pragma: no cover
            data_source_note.text = f"数据源配置删除失败: {exc}"
            ui.notify(str(exc), color="negative")

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
                intelligence_note.text = f"批量查询进行中 [{len(completed) + len(failed) + 1}/{len(symbols)}]：{symbol}"
                latest_snapshot = await _call_api(
                    "POST",
                    api_base,
                    f"/api/sessions/{state.session_id}/intelligence/search",
                    {"query": query, "max_documents": int(intelligence_max.value or 5)},
                )
                await refresh_agent_activity()
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
            now = time.monotonic()
            focus_seconds = (
                round(max(0.0, now - state.simulation_focus_started_at), 2)
                if state.simulation_focus_started_at is not None
                else None
            )
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/simulation/events",
                {
                    "scenario_id": "simulation-market",
                    "action": simulation_action.value or "hold",
                    "symbol": active_symbol,
                    "chart_focus_seconds": focus_seconds,
                    "loss_refresh_count": state.simulation_loss_refresh_count,
                    "loss_refresh_drawdown_trigger_pct": state.simulation_loss_refresh_drawdown_trigger_pct,
                },
            )
            state.snapshot = snapshot
            market = snapshot.get("simulation_market") or {}
            append_simulation_log(
                f"{market.get('symbol', active_symbol or 'SIM')} / {simulation_action.value} / {market.get('current_timestamp', 'unknown')} / "
                f"drawdown={market.get('current_drawdown_pct', 'unknown')} / focus={focus_seconds or 0}s / refresh={state.simulation_loss_refresh_count}"
            )
            state.simulation_focus_started_at = now
            state.simulation_loss_refresh_count = 0
            state.simulation_loss_refresh_drawdown_trigger_pct = None
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
            state.simulation_focus_started_at = time.monotonic()
            state.simulation_loss_refresh_count = 0
            state.simulation_loss_refresh_drawdown_trigger_pct = None
            state.simulation_last_advance_at = None
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
            now = time.monotonic()
            current_drawdown = float(market.get("current_drawdown_pct") or 0.0)
            if current_drawdown <= -2.0:
                if state.simulation_loss_refresh_count == 0:
                    state.simulation_loss_refresh_drawdown_trigger_pct = current_drawdown
                recent_gap = None if state.simulation_last_advance_at is None else (now - state.simulation_last_advance_at)
                state.simulation_loss_refresh_count = (
                    state.simulation_loss_refresh_count + 1
                    if recent_gap is None or recent_gap <= 20.0
                    else 1
                )
            else:
                state.simulation_loss_refresh_count = 0
                state.simulation_loss_refresh_drawdown_trigger_pct = None
            state.simulation_last_advance_at = now
            if state.simulation_focus_started_at is None:
                state.simulation_focus_started_at = now
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

    async def retrain_simulation_run() -> None:
        if not state.session_id:
            ui.notify("请先创建或加载会话", color="warning")
            return
        _set_action_state(simulation_actions, simulation_spinner, True)
        simulation_note.text = "正在基于新增行为重新训练模拟，请稍候..."
        try:
            market = ((state.snapshot or {}).get("simulation_market") or {})
            symbols = ((state.snapshot or {}).get("trade_universe") or {}).get("symbols") or []
            symbol = (market.get("symbol") or "").strip().upper() or (symbols[0].strip().upper() if symbols else "") or None
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/simulation/retrain",
                {"symbol": symbol},
            )
            state.snapshot = snapshot
            simulation_note.text = "已基于新增行为完成模拟重训练。"
            append_simulation_log("simulation_retrained / 已根据新增行为重新训练模拟画像")
            refresh_all()
        except Exception as exc:  # pragma: no cover - UI feedback path
            simulation_note.text = f"模拟重训练失败: {exc}"
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
        terminal_note.text = "交易终端技术文档分析与接入方案生成中，请稍候..."
        try:
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/terminal/expand",
                {
                    "interface_documentation": terminal_interface_documentation.value,
                    "api_key": terminal_api_key.value or None,
                    "user_notes": terminal_user_notes.value or None,
                },
            )
            state.snapshot = snapshot
            latest_run = _latest(snapshot.get("terminal_integration_runs") or [])
            readiness = latest_run.get("integration_readiness_summary") or {}
            if readiness.get("missing_required_capabilities"):
                terminal_note.text = (
                    "交易终端接入方案已生成，但缺少自动交易必需能力："
                    + ", ".join(readiness.get("missing_required_capabilities") or [])
                    + "。当前不能执行自动交易，请补充技术文档。"
                )
            elif readiness.get("missing_optional_capabilities"):
                terminal_note.text = (
                    "交易终端接入方案已生成。必需能力已齐备，但仍缺少可选能力："
                    + ", ".join(readiness.get("missing_optional_capabilities") or [])
                    + "。你可以继续补充文档，也可以带警告继续。"
                )
            else:
                terminal_note.text = "交易终端接入方案已生成，自动交易所需必需能力已齐备。"
            refresh_all()
        except Exception as exc:  # pragma: no cover
            terminal_note.text = f"交易终端接入方案生成失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(terminal_actions, terminal_spinner, False)

    async def update_terminal_run() -> None:
        if not state.session_id:
            terminal_note.text = "请先创建或加载会话。"
            ui.notify("请先创建或加载会话", color="warning")
            return
        if not terminal_run_select.value:
            terminal_note.text = "请先选择需要更新的交易终端接入 run。"
            ui.notify("请先选择 run", color="warning")
            return
        _set_action_state(terminal_actions, terminal_spinner, True)
        terminal_note.text = "交易终端接入方案更新中，请稍候..."
        try:
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/terminal/update",
                {
                    "run_id": terminal_run_select.value,
                    "interface_documentation": terminal_interface_documentation.value,
                    "api_key": terminal_api_key.value or None,
                    "user_notes": terminal_user_notes.value or None,
                },
            )
            state.snapshot = snapshot
            latest_run = _selected_run(snapshot.get("terminal_integration_runs") or [], terminal_run_select.value) or _latest(snapshot.get("terminal_integration_runs") or [])
            exchange = latest_run.get("exchange_support_summary") or {}
            terminal_note.text = (
                "交易终端接入方案已更新。当前仍按单交易所接入生成；多交易所能力缺口已保留。"
                if exchange.get("scope") == "single_exchange"
                else "交易终端接入方案已更新。"
            )
            refresh_all()
        except Exception as exc:  # pragma: no cover
            terminal_note.text = f"交易终端接入方案更新失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(terminal_actions, terminal_spinner, False)

    async def delete_terminal_run() -> None:
        if not state.session_id:
            terminal_note.text = "请先创建或加载会话。"
            ui.notify("请先创建或加载会话", color="warning")
            return
        if not terminal_run_select.value:
            terminal_note.text = "请先选择需要删除的交易终端接入 run。"
            ui.notify("请先选择 run", color="warning")
            return
        _set_action_state(terminal_actions, terminal_spinner, True)
        terminal_note.text = "交易终端接入方案删除中，请稍候..."
        try:
            run_id = str(terminal_run_select.value)
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/terminal/delete",
                {"run_id": run_id},
            )
            state.snapshot = snapshot
            terminal_note.text = f"交易终端接入方案 {run_id} 已删除。"
            refresh_all()
        except Exception as exc:  # pragma: no cover
            terminal_note.text = f"交易终端接入方案删除失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(terminal_actions, terminal_spinner, False)

    async def apply_terminal_run() -> None:
        if not state.session_id:
            terminal_note.text = "请先创建或加载会话。"
            ui.notify("请先创建或加载会话", color="warning")
            return
        _set_action_state(terminal_actions, terminal_spinner, True)
        terminal_note.text = "交易终端接入结果写入工作区中，请稍候..."
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
                terminal_note.text = "交易终端接入 dry-run 已完成，当前只生成方案与应用预演，没有写入工作区。"
            else:
                terminal_note.text = f"交易终端接入结果已提交，status={apply_status}。"
            refresh_all()
        except Exception as exc:  # pragma: no cover
            terminal_note.text = f"交易终端接入应用失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(terminal_actions, terminal_spinner, False)

    async def test_terminal_run() -> None:
        if not state.session_id:
            terminal_note.text = "请先创建或加载会话。"
            ui.notify("请先创建或加载会话", color="warning")
            return
        _set_action_state(terminal_actions, terminal_spinner, True)
        terminal_note.text = "交易终端接入测试运行中，请稍候..."
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

    async def select_active_trading_strategy() -> None:
        if not state.session_id:
            strategy_note.text = "请先创建或加载会话。"
            ui.notify("请先创建或加载会话", color="warning")
            return
        if not strategy_trading_select.value:
            strategy_note.text = "请先选择一个策略版本，再将其设为当前交易策略。"
            ui.notify("请先选择策略版本", color="warning")
            return
        _set_action_state(strategy_actions, strategy_spinner, True)
        strategy_note.text = "正在切换当前交易策略，请稍候..."
        try:
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/strategy/active",
                {"strategy_ref": strategy_trading_select.value},
            )
            state.snapshot = snapshot
            active = snapshot.get("active_trading_strategy") or {}
            status_summary = snapshot.get("strategy_status_summary") or {}
            strategy_note.text = (
                f"当前交易策略已切换为 {active.get('version_label', 'unknown')}。"
                f" 健康状态={status_summary.get('health_status', 'unknown')}，当前状态={status_summary.get('current_status', 'unknown')}。"
            )
            refresh_all()
        except Exception as exc:  # pragma: no cover
            strategy_note.text = f"切换当前交易策略失败: {exc}"
            ui.notify(str(exc), color="negative")
        finally:
            _set_action_state(strategy_actions, strategy_spinner, False)

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
                    "open_price": float(operation_market_price.value),
                    "high_price": max(float(operation_market_price.value), float(operation_market_high.value)),
                    "low_price": min(float(operation_market_price.value), float(operation_market_low.value)),
                    "close_price": float(operation_market_price.value),
                    "volume": float(operation_market_volume.value),
                    "source": "manual_ui",
                    "regime_tag": operation_market_regime.value or None,
                },
            )
            state.snapshot = snapshot
            append_operation_log(f"市场快照已写入: {operation_market_symbol.value}")
            operations_note.text = "市场状态已更新。"
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
                            "source": "manual_ui",
                            "title": operation_info_title.value,
                            "body": (operation_info_body.value or operation_info_title.value or "").strip(),
                            "trading_day": operation_info_day.value or None,
                            "author": None,
                            "handle": None,
                            "info_tag": operation_info_tag.value or None,
                            "sentiment_score": float(operation_info_sentiment.value),
                            "metadata": {},
                        }
                    ]
                },
            )
            state.snapshot = snapshot
            append_operation_log(f"信息流事件已写入: {operation_info_title.value}")
            operations_note.text = "重要消息已记录。"
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
            quantity = float(operation_trade_quantity.value)
            price = float(operation_trade_price.value)
            active_strategy = (state.snapshot or {}).get("active_trading_strategy") or {}
            snapshot = await _call_api(
                "POST",
                api_base,
                f"/api/sessions/{state.session_id}/trade-executions",
                {
                    "symbol": operation_trade_symbol.value,
                    "side": operation_trade_side.value,
                    "quantity": quantity,
                    "price": price,
                    "notional": round(quantity * price, 2),
                    "execution_mode": operation_trade_mode.value,
                    "strategy_version": active_strategy.get("version_label") or None,
                    "realized_pnl_pct": 0.0,
                    "user_initiated": True,
                    "note": operation_trade_note.value or None,
                },
            )
            state.snapshot = snapshot
            append_operation_log(f"交易执行记录已写入: {operation_trade_symbol.value} / {operation_trade_side.value}")
            operations_note.text = "交易记录已保存。"
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
        strategy_method.value = pkg.get("strategy_method", strategy_method.value)
        strategy_method.update()
        strategy_description.value = pkg.get("strategy_description", strategy_description.value)
        strategy_description.update()
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
        limits = pkg.get("trade_execution_limits") or {}
        if limits.get("max_trade_allocation_pct") is not None:
            max_trade_allocation_pct.value = limits.get("max_trade_allocation_pct")
            max_trade_allocation_pct.update()
        max_trade_amount.value = limits.get("max_trade_amount") or 0
        max_trade_amount.update()
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
        render_list_card(session_summary_panel, title="当前会话摘要", lines=_session_summary(state.snapshot), empty="默认会话初始化中。")
        session_json_panel.clear()
        render_json_card(session_json_panel, title="会话 JSON", payload=snapshot)

        parameters_status_panel.clear()
        render_list_card(parameters_status_panel, title="当前策略概览", lines=_strategy_status_lines(state.snapshot), empty="当前还没有策略概览。")
        strategy_trading_options = _strategy_trading_entries(state.snapshot)
        populate_select_options(
            strategy_trading_select,
            {item["value"]: item["label"] for item in strategy_trading_options},
            fallback=((snapshot.get("active_trading_strategy") or {}).get("strategy_ref") or ""),
        )
        parameters_validation_panel.clear()
        validation_lines, validation_errors = _strategy_input_validation_lines(
            training_start_value=training_start.value,
            training_end_value=training_end.value,
            target_return_value=target_return.value,
            target_win_rate_value=target_win_rate.value,
            target_drawdown_value=target_drawdown.value,
            target_max_loss_value=target_max_loss.value,
            max_trade_allocation_pct_value=max_trade_allocation_pct.value,
            max_trade_amount_value=max_trade_amount.value,
        )
        render_list_card(
            parameters_validation_panel,
            title="提交前检查",
            lines=validation_lines + ([f"错误 / {item}" for item in validation_errors] if validation_errors else ["状态 / 当前输入可提交训练"]),
            empty="当前还没有训练参数。",
        )
        parameters_manifest_panel.clear()
        render_list_card(parameters_manifest_panel, title="训练输入来源", lines=_input_manifest_lines(state.snapshot), empty="还没有训练输入来源说明。")
        parameters_features_panel.clear()
        render_list_card(parameters_features_panel, title="训练特征摘要", lines=_feature_snapshot_lines(state.snapshot), empty="还没有训练特征摘要。")
        parameters_bundles_panel.clear()
        render_list_card(parameters_bundles_panel, title="输入数据包记录", lines=_data_bundle_lines(state.snapshot), empty="还没有输入数据包记录。")
        parameters_package_panel.clear()
        render_list_card(parameters_package_panel, title="当前策略版本", lines=_package_lines(state.snapshot), empty="还没有策略版本信息。")

        training_checks_panel.clear()
        render_list_card(training_checks_panel, title="风险与质量检查", lines=_strategy_checks_lines(state.snapshot), empty="等待策略检查。")
        training_trend_panel.clear()
        render_list_card(training_trend_panel, title="问题变化趋势", lines=_check_trend_lines(state.snapshot), empty="还没有问题变化趋势。")
        training_repair_panel.clear()
        render_list_card(training_repair_panel, title="下一步修复建议", lines=_repair_route_lines(state.snapshot), empty="还没有下一步修复建议。")
        training_research_panel.clear()
        render_list_card(training_research_panel, title="当前研究结论", lines=_research_summary_lines(state.snapshot), empty="还没有研究结论。")
        training_loop_panel.clear()
        render_list_card(training_loop_panel, title="研究与修复联动", lines=_research_code_loop_lines(state.snapshot), empty="还没有研究与修复联动记录。")
        training_logs_panel.clear()
        render_list_card(training_logs_panel, title="训练过程记录", lines=_training_log_lines(state), empty="还没有训练过程记录。")

        results_models_panel.clear()
        models = _model_result_specs(state.snapshot)
        if not models:
            render_list_card(results_models_panel, title="策略模型表现", lines=[], empty="完成一轮策略训练后，这里会显示每个策略模型的总计和按年表现。")
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
        render_list_card(results_compare_panel, title="方案对比", lines=_variant_compare_lines(state.snapshot), empty="还没有方案对比。")
        results_backtest_panel.clear()
        render_list_card(results_backtest_panel, title="回测摘要", lines=_backtest_lines(state.snapshot), empty="还没有回测结果。")
        results_walkforward_panel.clear()
        walk_rows = _walk_forward_rows(state.snapshot)
        if walk_rows:
            with results_walkforward_panel:
                with ui.card().classes("w-full"):
                    ui.label("滚动检验结果").classes("text-h6")
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
            render_list_card(results_walkforward_panel, title="滚动检验结果", lines=[], empty="还没有滚动检验结果。")
        results_research_trend_panel.clear()
        render_list_card(results_research_trend_panel, title="研究趋势", lines=_research_trend_lines(state.snapshot), empty="还没有研究趋势。")
        results_research_health_panel.clear()
        render_list_card(results_research_health_panel, title="结果健康结论", lines=_research_health_lines(state.snapshot), empty="还没有结果健康结论。")

        history_iterations_panel.clear()
        render_list_card(history_iterations_panel, title="版本时间线", lines=_history_lines(state.snapshot), empty="还没有版本时间线。")
        history_archive_panel.clear()
        render_list_card(history_archive_panel, title="历史归档", lines=_archive_lines(state.snapshot), empty="还没有历史归档。")
        archive_entries = _strategy_archive_entries(state.snapshot)
        archive_options = {item["version"]: item["version"] for item in archive_entries}
        populate_select_options(restore_version_select, archive_options)
        populate_select_options(compare_version_a, archive_options)
        populate_select_options(compare_version_b, archive_options)
        history_compare_panel.clear()
        render_list_card(
            history_compare_panel,
            title="差异对比",
            lines=_version_compare_lines(state.snapshot, compare_version_a.value or "", compare_version_b.value or ""),
            empty="还没有版本对比结果。",
        )
        history_restore_preview_panel.clear()
        render_list_card(
            history_restore_preview_panel,
            title="恢复前预览",
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
        render_list_card(history_research_compare_panel, title="研究对比", lines=compare_lines, empty="还没有研究对比结果。")
        history_research_detail_panel.clear()
        detail_lines, detail_export = _research_detail_lines(state.snapshot, research_detail_select.value or "")
        render_list_card(history_research_detail_panel, title="研究详情", lines=detail_lines, empty="还没有研究详情。")
        history_research_detail_json_panel.clear()
        render_json_card(history_research_detail_json_panel, title="研究原始数据", payload=detail_export)
        history_failure_panel.clear()
        render_list_card(history_failure_panel, title="失败原因变化", lines=_failure_evolution_lines(state.snapshot), empty="当前还没有失败原因变化记录。")

        artifacts_release_panel.clear()
        render_list_card(artifacts_release_panel, title="发布结论", lines=_release_snapshot_lines(state.snapshot), empty="还没有发布结论。")
        artifacts_analysis_panel.clear()
        render_list_card(artifacts_analysis_panel, title="关键分析", lines=_analysis_lines(state.snapshot), empty="还没有关键分析。")
        artifacts_code_panel.clear()
        render_code_card(artifacts_code_panel, title="当前推荐代码", code=_strategy_code(state.snapshot))
        artifacts_model_panel.clear()
        render_list_card(artifacts_model_panel, title="模型选择与路由", lines=_model_routing_lines(state.snapshot), empty="还没有模型选择信息。")
        artifacts_token_panel.clear()
        render_list_card(artifacts_token_panel, title="本轮 LLM 资源消耗", lines=_token_usage_lines(state.snapshot), empty="还没有 LLM 资源消耗信息。")
        artifacts_programmer_runs_panel.clear()
        render_list_card(artifacts_programmer_runs_panel, title="Programmer Agent 执行记录", lines=_programmer_runs_lines(state.snapshot), empty="还没有 Programmer Agent 执行记录。")
        artifacts_programmer_stats_panel.clear()
        render_list_card(artifacts_programmer_stats_panel, title="失败类型统计", lines=_programmer_stats_lines(state.snapshot), empty="还没有失败类型统计。")
        artifacts_programmer_trend_panel.clear()
        render_list_card(
            artifacts_programmer_trend_panel,
            title="失败趋势变化",
            lines=_programmer_trend_lines(state.snapshot, programmer_trend_filter.value or "all"),
            empty="还没有 Programmer Agent 趋势时间线。",
        )
        artifacts_programmer_diff_panel.clear()
        render_code_card(artifacts_programmer_diff_panel, title="代码差异与失败摘要", code=_programmer_diff(state.snapshot))

        history_entries = _intelligence_history_entries(state.snapshot)
        history_options = {item["value"]: item["label"] for item in history_entries}
        populate_select_options(intelligence_history_select, history_options)
        symbol_options, source_options = _intelligence_history_filter_options(state.snapshot)
        populate_select_options(intelligence_history_symbol_filter, symbol_options)
        populate_select_options(intelligence_history_source_filter, source_options)
        intelligence_overview_panel.clear()
        render_list_card(intelligence_overview_panel, title="当前情报概览", lines=_intelligence_overview_lines(state.snapshot), empty="当前还没有情报概览。")
        intelligence_watchlist_panel.clear()
        render_list_card(intelligence_watchlist_panel, title="股票情报总览", lines=_intelligence_watchlist_summary_lines(state.snapshot), empty="当前还没有按股票汇总的情报结果。")
        intelligence_briefing_panel.clear()
        render_list_card(intelligence_briefing_panel, title="情报简报", lines=_intelligence_briefing_lines(state.snapshot), empty="当前还没有情报简报。")
        intelligence_history_analysis_panel.clear()
        render_list_card(intelligence_history_analysis_panel, title="历史情报行为分析", lines=_intelligence_history_analysis_lines(state.snapshot), empty="当前还没有足够的历史情报查询记录。")
        intelligence_documents_panel.clear()
        render_list_card(intelligence_documents_panel, title="来源与文档", lines=_intelligence_source_lines(state.snapshot), empty="当前还没有情报来源。")
        intelligence_history_panel.clear()
        filtered_history_cards = _filter_intelligence_history_cards(
            _intelligence_history_run_cards(state.snapshot),
            symbol_filter=intelligence_history_symbol_filter.value or "all",
            source_filter=intelligence_history_source_filter.value or "all",
            translated_only=bool(intelligence_history_translated_only.value),
        )
        render_intelligence_history_cards(
            intelligence_history_panel,
            title="查询历史时间线",
            cards=filtered_history_cards,
            empty="当前还没有查询历史。",
        )
        intelligence_history_groups_panel.clear()
        render_intelligence_topic_groups(
            intelligence_history_groups_panel,
            title="历史情报主题组",
            groups=_group_intelligence_history_cards(filtered_history_cards),
            empty="当前还没有可聚合的历史情报主题。",
        )
        intelligence_history_detail_panel.clear()
        detail_lines, detail_payload = _intelligence_history_detail_lines(state.snapshot, intelligence_history_select.value or "")
        detail_lines = detail_lines + _intelligence_history_document_lines(detail_payload)
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
        agent_activity_panel.clear()
        render_list_card(agent_activity_panel, title="Agent 原子日志", lines=_agent_activity_lines(state.agent_activity_feed or snapshot.get("agent_activity") or []), empty="当前还没有 agent 原子日志。")

        simulation_market_panel.clear()
        render_list_card(simulation_market_panel, title="模拟市场状态", lines=_simulation_market_lines(state.snapshot), empty="先加载模拟市场数据，建立日线与 5 分钟线回放。")
        simulation_training_state_panel.clear()
        render_list_card(simulation_training_state_panel, title="模拟训练状态", lines=_simulation_training_state_lines(state.snapshot), empty="先完成一轮模拟测试，建立行为基线。")
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

        habit_goal_current_panel.clear()
        render_list_card(habit_goal_current_panel, title="当前习惯与目标结论", lines=_habit_goal_current_lines(state.snapshot), empty="当前还没有习惯与目标综合分析。")
        habit_goal_risk_panel.clear()
        render_list_card(habit_goal_risk_panel, title="风险、冲突与下一步", lines=_habit_goal_risk_lines(state.snapshot), empty="当前还没有额外风险或动作建议。")
        habit_goal_shift_panel.clear()
        render_list_card(habit_goal_shift_panel, title="最近变化", lines=_habit_goal_shift_lines(state.snapshot), empty="当前还没有习惯与目标变化摘要。")
        habit_goal_history_panel.clear()
        render_list_card(habit_goal_history_panel, title="演化时间线", lines=_habit_goal_history_lines(state.snapshot), empty="当前还没有演化时间线。")
        habit_goal_payload_panel.clear()
        render_json_card(habit_goal_payload_panel, title="习惯与目标演化 JSON", payload=snapshot.get("habit_goal_evolution") or {})

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
        load_selected_data_source_run()
        data_source_health_panel.clear()
        render_list_card(data_source_health_panel, title="数据源健康摘要", lines=_data_source_health_lines(state.data_source_health), empty="当前还没有数据源健康检查结果。")
        data_source_health_action_panel.clear()
        render_list_card(data_source_health_action_panel, title="当前风险与下一步动作", lines=_data_source_health_action_lines(state.data_source_health), empty="当前没有额外风险或修复动作。")
        data_source_provider_health_panel.clear()
        render_table_card(
            data_source_provider_health_panel,
            title="已配置数据源管理",
            columns=[
                {"name": "family", "label": "类型", "field": "family"},
                {"name": "provider", "label": "Provider", "field": "provider"},
                {"name": "status", "label": "状态", "field": "status"},
                {"name": "enabled", "label": "启用", "field": "enabled"},
                {"name": "api_key", "label": "API KEY", "field": "api_key"},
                {"name": "base_url", "label": "Base URL", "field": "base_url"},
                {"name": "detail", "label": "说明", "field": "detail"},
            ],
            rows=_configured_provider_health_rows(state.data_source_health),
            empty="当前还没有已配置数据源结果。",
            row_key="provider",
        )
        data_source_run_health_panel.clear()
        render_list_card(data_source_run_health_panel, title="扩展数据源健康", lines=_expanded_run_health_lines(state.data_source_health), empty="当前还没有扩展数据源健康结果。")
        data_source_panel.clear()
        render_list_card(data_source_panel, title="数据源扩展记录", lines=_data_source_lines(state.snapshot), empty="当前还没有数据源扩展记录。")
        data_source_detail_panel.clear()
        render_json_card(data_source_detail_panel, title="选中数据源扩展详情", payload=_selected_run(snapshot.get("data_source_runs") or [], data_source_run_select.value))
        data_bundle_panel.clear()
        render_list_card(data_bundle_panel, title="输入数据包记录", lines=_data_bundle_lines(state.snapshot), empty="当前还没有输入数据包记录。")
        operations_control_panel.clear()
        render_list_card(operations_control_panel, title="当前运行状态", lines=_operation_overview_lines(state.snapshot), empty="当前还没有运行状态摘要。")
        operations_panel.clear()
        render_list_card(operations_panel, title="最近页面操作", lines=_operation_local_log_lines(state.local_operation_logs), empty="当前还没有页面操作记录。")
        operations_monitor_panel.clear()
        render_list_card(operations_monitor_panel, title="最近运行记录与提醒", lines=_history_event_lines(state.snapshot) + _monitor_lines(state.snapshot), empty="当前还没有运行记录或提醒。")
        terminal_options = _run_options(snapshot.get("terminal_integration_runs") or [], ["terminal_name", "terminal_type", "timestamp"])
        populate_select_options(terminal_run_select, terminal_options)
        terminal_panel.clear()
        render_list_card(terminal_panel, title="交易终端接入记录", lines=_terminal_lines(state.snapshot), empty="当前还没有交易终端接入记录。")
        terminal_detail_panel.clear()
        render_json_card(terminal_detail_panel, title="选中交易终端接入详情", payload=_selected_run(snapshot.get("terminal_integration_runs") or [], terminal_run_select.value))

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
                "当前入口已经切到 NiceGUI。页面结构已覆盖 `会话 / 配置 / 策略 / 模拟 / 习惯与目标 / 偏好 / 报告 / 数据源扩展 / 交易运行 / 交易终端接入 / 情报 / 健康`，并继续直接调用现有 FastAPI API。"
            )

        with ui.tabs().classes("w-full") as root_tabs:
            session_tab = ui.tab("会话")
            configuration_tab = ui.tab("配置")
            strategy_tab = ui.tab("策略")
            simulation_tab = ui.tab("模拟")
            habit_goal_tab = ui.tab("习惯与目标")
            preferences_tab = ui.tab("偏好")
            report_tab = ui.tab("报告")
            data_source_tab = ui.tab("数据源扩展")
            operations_tab = ui.tab("交易运行")
            terminal_tab = ui.tab("交易终端接入")
            intelligence_tab = ui.tab("情报")
            health_tab = ui.tab("健康")

        with ui.tab_panels(root_tabs, value=session_tab).classes("w-full"):
            with ui.tab_panel(session_tab):
                with ui.grid(columns=2).classes("w-full gap-4"):
                    with ui.card().classes("w-full"):
                        ui.label("会话入口").classes("text-h6")
                        user_name = ui.input("用户名", value="nicegui-user").classes("w-full")
                        starting_capital = ui.number("初始资金", value=100000, min=1).classes("w-full")
                        session_id_input = ui.input("切换到已有 session_id", value="").classes("w-full")
                        with ui.row().classes("gap-3"):
                            session_actions.append(ui.button("新建默认会话", on_click=create_session))
                            session_actions.append(ui.button("切换到已有会话", on_click=load_session, color="secondary"))
                            session_spinner = ui.spinner(size="sm")
                            session_spinner.visible = False
                        session_note = ui.label("页面打开后会自动创建并加载默认会话，同时补齐交易标的、行为画像和交易偏好。").classes("text-sm text-slate-600")
                        ui.markdown(f"API Base: `{api_base}`")
                    session_summary_panel = ui.column().classes("w-full gap-4")
                session_json_panel = ui.column().classes("w-full gap-4")

            with ui.tab_panel(configuration_tab):
                with ui.card().classes("w-full"):
                    ui.label("系统配置工作台").classes("text-h6")
                    ui.label("这里可以加载、编辑、保存并测试当前系统配置。默认大模型会被未单独指定的 Agent 自动继承；如果某个 Agent 单独指定了模型，就优先使用它自己的配置。").classes("text-sm text-slate-600")
                    ui.label("LLM 默认模型配置").classes("text-subtitle1")
                    with ui.grid(columns=2).classes("w-full gap-4"):
                        default_provider_input = ui.input("默认大模型 Provider", value="google").classes("w-full")
                        default_models_input = ui.input("默认大模型列表", value="gemini-2.5-flash, gemini-2.5-pro").classes("w-full")
                        default_temperature_input = ui.number("默认 Temperature", value=0.2).classes("w-full")
                        default_max_tokens_input = ui.number("默认 Max Tokens", value=1200).classes("w-full")
                    ui.label("Agent 专用模型配置").classes("text-subtitle1")
                    with ui.grid(columns=2).classes("w-full gap-4"):
                        agent_model_agent_select = ui.select(
                            {
                                "intent_aligner": "intent_aligner",
                                "noise_agent": "noise_agent",
                                "behavioral_profiler": "behavioral_profiler",
                                "intelligence_agent": "intelligence_agent",
                                "strategy_evolver": "strategy_evolver",
                                "intent_monitor": "intent_monitor",
                                "strategy_integrity_checker": "strategy_integrity_checker",
                                "strategy_stress_checker": "strategy_stress_checker",
                                "programmer_agent": "programmer_agent",
                            },
                            value="strategy_evolver",
                            label="选择 Agent",
                            on_change=lambda _: sync_llm_config_inputs(state.config_payload or {}),
                        ).classes("w-full")
                        agent_model_provider_input = ui.input("Agent Provider", value="google").classes("w-full")
                        agent_model_models_input = ui.input("Agent 模型列表", value="gemini-2.5-pro, gemini-2.5-flash").classes("w-full")
                        agent_model_temperature_input = ui.number("Agent Temperature", value=0.15).classes("w-full")
                        agent_model_max_tokens_input = ui.number("Agent Max Tokens", value=1800).classes("w-full")
                    with ui.row().classes("gap-3 mt-3"):
                        config_actions.append(ui.button("应用模型设置到配置 JSON", on_click=lambda: apply_llm_forms_to_editor(), color="secondary"))
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
                    config_note = ui.label("配置会保存到当前 settings.toml，并先自动生成备份。未单独配置模型的 Agent 会继续继承默认模型。").classes("text-sm text-slate-600")
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

                with ui.tab_panels(strategy_tabs, value=strategy_parameters_tab).classes("w-full"):
                    with ui.tab_panel(strategy_parameters_tab):
                        with ui.card().classes("w-full"):
                            ui.label("策略参数与目标").classes("text-h5")
                            ui.label("这里集中设置股票池、训练区间、目标函数和约束。只有这个子页面会显示策略公共配置。").classes("text-sm text-slate-600")
                        with ui.card().classes("w-full"):
                            ui.label("策略公共配置").classes("text-h6")
                            with ui.grid(columns=2).classes("w-full gap-4"):
                                universe_type = ui.select({"stocks": "股票", "etfs": "ETF", "sector": "板块"}, value="stocks", label="标的类型").classes("w-full")
                                universe_symbols = ui.input("标的列表", value="TSLA,NVDA,QQQ").classes("w-full")
                                training_start = ui.input("训练开始", value="2021-01-01", placeholder="YYYY-MM-DD").classes("w-full")
                                training_end = ui.input("训练结束", value="2025-12-31", placeholder="YYYY-MM-DD").classes("w-full")
                                strategy_type = ui.select(
                                    {
                                        "rule_based_aligned": "Rule-Based Aligned",
                                        "trend_following_aligned": "Trend Following Aligned",
                                        "mean_reversion_aligned": "Mean Reversion Aligned",
                                    },
                                    value="rule_based_aligned",
                                    label="策略类型",
                                ).classes("w-full")
                                strategy_method = ui.input("用户策略方式", value="趋势跟随 + 事件过滤").classes("w-full")
                                strategy_description = ui.textarea("用户策略说明", value="如果你已经有自己的策略思路，在这里写清楚关键规则、信号、过滤条件和风险控制。").props("autogrow").classes("w-full")
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
                                max_trade_allocation_pct = ui.number("单笔交易资金占比上限 %", value=10, min=0.1, max=100).classes("w-full")
                                max_trade_amount = ui.number("单笔交易金额上限（填 0 表示不额外限制）", value=0, min=0).classes("w-full")
                            with ui.row().classes("gap-3 mt-4"):
                                strategy_actions.append(ui.button("提交交易标的", on_click=submit_universe, color="secondary"))
                                strategy_actions.append(ui.button("生成下一版策略", on_click=run_strategy_iteration))
                                strategy_actions.append(ui.button("确认当前策略", on_click=approve_strategy, color="secondary"))
                                strategy_spinner = ui.spinner(size="sm")
                                strategy_spinner.visible = False
                            strategy_note = ui.label("每个策略版本都会自动经过 Integrity 与 Stress/Overfit 检查。").classes("text-sm text-slate-600")
                        with ui.card().classes("w-full"):
                            ui.label("交易策略启用").classes("text-h6")
                            ui.label("你可以在这里选择当前用于交易的策略版本。当前只允许单策略启用，后续会保留多策略/多交易所扩展缺口。").classes("text-sm text-slate-600")
                            with ui.row().classes("gap-3 mt-3 items-center"):
                                strategy_trading_select = ui.select({}, label="选择用于交易的策略版本").classes("w-80")
                                strategy_actions.append(ui.button("设为当前交易策略", on_click=select_active_trading_strategy, color="secondary"))
                        parameters_status_panel = ui.column().classes("w-full gap-4")
                        with ui.grid(columns=2).classes("w-full gap-4"):
                            parameters_validation_panel = ui.column().classes("w-full gap-4")
                            parameters_manifest_panel = ui.column().classes("w-full gap-4")
                            parameters_features_panel = ui.column().classes("w-full gap-4")
                            parameters_bundles_panel = ui.column().classes("w-full gap-4")
                            parameters_package_panel = ui.column().classes("w-full gap-4")

                    with ui.tab_panel(strategy_training_tab):
                        with ui.card().classes("w-full"):
                            ui.label("训练页面").classes("text-h5")
                            ui.label("这里负责推进训练循环、查看当前检查结果，并在需要时人工介入。").classes("text-sm text-slate-600")
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
                        with ui.card().classes("w-full"):
                            ui.label("结果页面").classes("text-h5")
                            ui.label("这里专门查看训练结果，包括总计指标、按年指标、对比、回测和滚动窗口。").classes("text-sm text-slate-600")
                        results_models_panel = ui.column().classes("w-full gap-4")
                        with ui.grid(columns=2).classes("w-full gap-4"):
                            results_compare_panel = ui.column().classes("w-full gap-4")
                            results_backtest_panel = ui.column().classes("w-full gap-4")
                            results_walkforward_panel = ui.column().classes("w-full gap-4")
                            results_research_trend_panel = ui.column().classes("w-full gap-4")
                            results_research_health_panel = ui.column().classes("w-full gap-4")

                    with ui.tab_panel(strategy_history_tab):
                        with ui.card().classes("w-full"):
                            ui.label("历史页面").classes("text-h5")
                            ui.label("这里查看历史策略版本、恢复预览、版本对比和研究归档，不混入当前训练控制。").classes("text-sm text-slate-600")
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
                        with ui.card().classes("w-full"):
                            ui.label("成果页面").classes("text-h5")
                            ui.label("这里聚合发布摘要、推荐代码、模型路由、LLM 资源消耗和 Programmer Agent 结果。").classes("text-sm text-slate-600")
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
                    ui.label("系统会自动使用当前会话股票池的第一个标的建立日线与 5 分钟线回放。你只需要推进市场，并在每个市场时点选择买入、卖出或不交易。系统会自动捕获盯盘时长、亏损下频繁刷新，以及手动干预自动化的信号。完成一轮模拟后，行为结果会先作为策略训练输入；后续继续收集到的新行为会决定是否需要重新训练模拟。").classes("text-sm text-slate-600")
                    simulation_action = ui.select({"buy": "buy", "sell": "sell", "hold": "hold"}, value="hold", label="最近动作").classes("hidden")
                    with ui.row().classes("gap-3 mt-3"):
                        simulation_actions.append(ui.button("加载模拟市场", on_click=initialize_simulation_market_run, color="secondary"))
                        simulation_actions.append(ui.button("推进模拟时钟", on_click=advance_simulation_market_run, color="secondary"))
                        simulation_actions.append(ui.button("买入", on_click=lambda: record_simulation_action("buy"), color="positive"))
                        simulation_actions.append(ui.button("卖出", on_click=lambda: record_simulation_action("sell"), color="negative"))
                        simulation_actions.append(ui.button("不交易", on_click=lambda: record_simulation_action("hold"), color="secondary"))
                        simulation_actions.append(ui.button("完成模拟并生成画像", on_click=complete_simulation_run))
                        simulation_actions.append(ui.button("基于新增行为重新训练模拟", on_click=retrain_simulation_run, color="secondary"))
                        simulation_spinner = ui.spinner(size="sm")
                        simulation_spinner.visible = False
                    simulation_note = ui.label("先加载模拟市场，再按固定 5 分钟节奏推进时钟，然后只通过买入、卖出、不交易三个动作记录你的行为。系统会自动记录犹豫时长、焦虑刷新和信任衰减。").classes("text-sm text-slate-600")
                with ui.grid(columns=2).classes("w-full gap-4"):
                    simulation_market_panel = ui.column().classes("w-full gap-4")
                    simulation_training_state_panel = ui.column().classes("w-full gap-4")
                    simulation_daily_chart_panel = ui.column().classes("w-full gap-4")
                    simulation_intraday_chart_panel = ui.column().classes("w-full gap-4")
                    simulation_summary_panel = ui.column().classes("w-full gap-4")
                    simulation_user_panel = ui.column().classes("w-full gap-4")
                    simulation_system_panel = ui.column().classes("w-full gap-4")
                    simulation_trade_panel = ui.column().classes("w-full gap-4")
                    simulation_scenario_panel = ui.column().classes("w-full gap-4")

            with ui.tab_panel(habit_goal_tab):
                with ui.card().classes("w-full"):
                    ui.label("交易习惯与目标演化").classes("text-h6")
                    ui.label("这里统一汇总模拟测试结果、手动偏好、训练反馈、真实交易行为和当前策略状态，并通过 Agent 做综合分析，告诉你当前习惯、目标和策略是否一致。").classes("text-sm text-slate-600")
                with ui.grid(columns=2).classes("w-full gap-4"):
                    habit_goal_current_panel = ui.column().classes("w-full gap-4")
                    habit_goal_risk_panel = ui.column().classes("w-full gap-4")
                    habit_goal_shift_panel = ui.column().classes("w-full gap-4")
                    habit_goal_history_panel = ui.column().classes("w-full gap-4")
                habit_goal_payload_panel = ui.column().classes("w-full gap-4")

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
                        data_source_run_select = ui.select({}, label="应用已有 run", on_change=lambda _: load_selected_data_source_run()).classes("w-72")
                        data_source_test_symbol = ui.input("测试股票", value="AAPL").classes("w-40")
                        data_source_actions.append(ui.button("检查数据源健康", on_click=refresh_data_source_health, color="secondary"))
                        data_source_actions.append(ui.button("测试数据源扩展", on_click=test_data_source_run, color="secondary"))
                        data_source_actions.append(ui.button("更新数据源扩展", on_click=update_data_source_run, color="secondary"))
                        data_source_actions.append(ui.button("删除数据源扩展", on_click=delete_data_source_run, color="negative"))
                        data_source_commit = ui.switch("提交改动", value=True)
                        data_source_actions.append(ui.button("应用数据源扩展", on_click=apply_data_source_run, color="secondary"))
                        data_source_spinner = ui.spinner(size="sm")
                        data_source_spinner.visible = False
                    data_source_note = ui.label("这里会基于最小输入完成 LLM 文档分析、结构化 spec 生成、代码与测试草案生成。生成后请执行“测试数据源扩展”，确认 smoke test 结果；如果提供 API KEY，还会尝试 live fetch。策略训练发现真实股票历史数据缺失时，会自动优先复用这里已经测试通过或可用的 market-data 数据源补数并落到本地。").classes("text-sm text-slate-600")
                with ui.card().classes("w-full"):
                    ui.label("数据源管理").classes("text-subtitle1")
                    with ui.grid(columns=2).classes("w-full gap-4"):
                        update_provider_name = ui.input("扩展数据源名称").classes("w-full")
                        update_provider_family = ui.select({"market_data": "market_data", "fundamentals": "fundamentals", "dark_pool": "dark_pool", "options": "options"}, value="market_data", label="扩展数据源类型").classes("w-full")
                        update_base_url = ui.input("扩展数据源 Base URL").classes("w-full")
                        update_api_key_envs = ui.input("扩展数据源 API KEY ENV 列表", placeholder="ENV_A, ENV_B").classes("w-full")
                with ui.card().classes("w-full"):
                    ui.label("已配置数据源管理").classes("text-subtitle1")
                    with ui.grid(columns=3).classes("w-full gap-4"):
                        configured_provider_family = ui.select({"market_data": "market_data", "fundamentals": "fundamentals", "dark_pool": "dark_pool", "options_data": "options_data"}, value="market_data", label="配置类型").classes("w-full")
                        configured_provider_name = ui.input("Provider 名称", value="local_file").classes("w-full")
                        configured_provider_enabled = ui.switch("启用", value=True)
                        configured_provider_default = ui.switch("设为默认", value=False)
                        configured_provider_base_url = ui.input("Base URL").classes("w-full")
                        configured_provider_base_path = ui.input("Base Path").classes("w-full")
                        configured_provider_api_key_envs = ui.input("API KEY ENV 列表", placeholder="ENV_A, ENV_B").classes("w-full")
                    with ui.row().classes("gap-3 mt-3"):
                        data_source_actions.append(ui.button("保存数据源配置", on_click=save_configured_data_source_provider, color="secondary"))
                        data_source_actions.append(ui.button("删除数据源配置", on_click=delete_configured_data_source_provider, color="negative"))
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
                    data_source_health_panel = ui.column().classes("w-full gap-4")
                    data_source_health_action_panel = ui.column().classes("w-full gap-4")
                    data_source_provider_health_panel = ui.column().classes("w-full gap-4")
                    data_source_run_health_panel = ui.column().classes("w-full gap-4")
                    data_source_panel = ui.column().classes("w-full gap-4")
                    data_source_detail_panel = ui.column().classes("w-full gap-4")
                    data_bundle_panel = ui.column().classes("w-full gap-4")

            with ui.tab_panel(operations_tab):
                with ui.card().classes("w-full"):
                    ui.label("交易运行与记录").classes("text-h6")
                    ui.label("这里用于准备当天交易环境、记录一条重要消息、补一笔人工交易，并查看最近运行记录。页面会尽量自动带入默认值，不要求你理解底层接口字段。").classes("text-sm text-slate-600")
                    with ui.grid(columns=2).classes("w-full gap-4"):
                        with ui.card().classes("w-full"):
                            ui.label("今日交易设置").classes("text-h6")
                            operation_deployment_mode = ui.select({"advice_only": "仅建议，不自动下单", "autonomous": "自动执行"}, value="advice_only", label="当前执行方式").classes("w-full")
                            with ui.row().classes("gap-3 mt-3"):
                                operations_actions.append(ui.button("准备今日交易场景", on_click=generate_operation_scenarios))
                                operations_actions.append(ui.button("保存当前执行方式", on_click=set_operation_deployment, color="secondary"))
                        with ui.card().classes("w-full"):
                            ui.label("记录当前市场状态").classes("text-h6")
                            ui.label("适合手动补一笔当前价格和成交量，让系统知道你正在观察哪只股票。").classes("text-sm text-slate-600")
                            with ui.grid(columns=2).classes("w-full gap-4"):
                                operation_market_symbol = ui.input("股票代码", value="TSLA").classes("w-full")
                                operation_market_timeframe = ui.select({"1d": "日线", "1h": "小时线", "15m": "15 分钟", "5m": "5 分钟"}, value="1d", label="记录周期").classes("w-full")
                                operation_market_price = ui.number("当前价格", value=100).classes("w-full")
                                operation_market_volume = ui.number("成交量", value=1000000).classes("w-full")
                                operation_market_high = ui.number("当期最高价", value=104).classes("w-full")
                                operation_market_low = ui.number("当期最低价", value=98).classes("w-full")
                                operation_market_regime = ui.select({"risk_on": "偏强", "neutral": "中性", "risk_off": "偏弱"}, value="risk_on", label="当前市场氛围").classes("w-full")
                            operations_actions.append(ui.button("保存市场状态", on_click=append_operation_market_snapshot, color="secondary"))
                        with ui.card().classes("w-full"):
                            ui.label("记录一条重要消息").classes("text-h6")
                            ui.label("适合补一条会影响交易判断的新闻、公告或盘中消息。").classes("text-sm text-slate-600")
                            with ui.grid(columns=2).classes("w-full gap-4"):
                                operation_info_channel = ui.select({"news": "新闻", "focus": "重点关注", "chat": "聊天消息", "discussion": "讨论帖"}, value="news", label="消息类型").classes("w-full")
                                operation_info_day = ui.input("交易日期（可选）", value="").classes("w-full")
                                operation_info_title = ui.input("消息标题", value="盘中重要消息").classes("w-full")
                                operation_info_tag = ui.input("消息标签（可选）", value="macro").classes("w-full")
                                operation_info_sentiment = ui.select({"-0.5": "偏空", "0": "中性", "0.5": "偏多"}, value="0", label="影响倾向").classes("w-full")
                                operation_info_body = ui.textarea("消息内容（可选）", value="").props("autogrow").classes("w-full")
                            operations_actions.append(ui.button("保存消息记录", on_click=append_operation_information_event, color="secondary"))
                        with ui.card().classes("w-full"):
                            ui.label("补一笔人工交易").classes("text-h6")
                            ui.label("适合记录你已经执行过的一笔买入或卖出，系统会自动计算成交金额并带入当前交易策略。").classes("text-sm text-slate-600")
                            with ui.grid(columns=2).classes("w-full gap-4"):
                                operation_trade_symbol = ui.input("股票代码", value="TSLA").classes("w-full")
                                operation_trade_side = ui.select({"buy": "买入", "sell": "卖出"}, value="buy", label="交易方向").classes("w-full")
                                operation_trade_quantity = ui.number("成交数量", value=10).classes("w-full")
                                operation_trade_price = ui.number("成交价格", value=100).classes("w-full")
                                operation_trade_mode = ui.select({"manual": "人工记录", "advice_only": "建议执行", "autonomous": "自动执行"}, value="manual", label="交易来源").classes("w-full")
                                operation_trade_note = ui.input("备注（可选）", value="").classes("w-full")
                            operations_actions.append(ui.button("保存交易记录", on_click=append_operation_trade_execution, color="secondary"))
                    with ui.row().classes("gap-3 mt-3"):
                        operations_spinner = ui.spinner(size="sm")
                        operations_spinner.visible = False
                    operations_note = ui.label("你可以先准备今日交易场景，再按需补市场状态、消息和交易记录。最近结果会显示在下面。").classes("text-sm text-slate-600")
                with ui.grid(columns=2).classes("w-full gap-4"):
                    operations_control_panel = ui.column().classes("w-full gap-4")
                    operations_panel = ui.column().classes("w-full gap-4")
                    operations_monitor_panel = ui.column().classes("w-full gap-4")

            with ui.tab_panel(terminal_tab):
                with ui.card().classes("w-full"):
                    ui.label("交易终端接入工作台").classes("text-h6")
                    ui.label("这里只需要提供 API KEY 和技术文档。系统会先用 LLM 分析文档，再自动生成接入代码、测试，以及必需/可选能力缺口判断。").classes("text-sm text-slate-600")
                    with ui.grid(columns=2).classes("w-full gap-4"):
                        terminal_api_key = ui.input("API KEY", password=True, password_toggle_button=True).classes("w-full")
                        terminal_user_notes = ui.input("补充说明（可选）", value="").classes("w-full")
                        terminal_interface_documentation = ui.textarea(
                            "技术文档",
                            value=(
                                "https://docs.example.com/trading\n"
                                "Base URL: https://api.example.com\n"
                                "Authentication: Bearer token\n"
                                "POST /orders place order\n"
                                "GET /orders/{id} query order status\n"
                                "GET /positions account positions\n"
                                "GET /balances account balances\n"
                                "GET /fills trade records\n"
                            ),
                        ).props("autogrow").classes("w-full col-span-2")
                    with ui.row().classes("gap-3 mt-3"):
                        terminal_actions.append(ui.button("生成交易终端接入方案", on_click=expand_terminal_run))
                        terminal_run_select = ui.select({}, label="选择 run").classes("w-72")
                        terminal_actions.append(ui.button("更新交易终端接入", on_click=update_terminal_run, color="secondary"))
                        terminal_actions.append(ui.button("删除交易终端接入", on_click=delete_terminal_run, color="negative"))
                        terminal_commit = ui.switch("提交改动", value=True)
                        terminal_actions.append(ui.button("应用交易终端接入", on_click=apply_terminal_run, color="secondary"))
                        terminal_actions.append(ui.button("测试交易终端接入", on_click=test_terminal_run, color="secondary"))
                        terminal_spinner = ui.spinner(size="sm")
                        terminal_spinner.visible = False
                    terminal_note = ui.label("系统会自动判断哪些能力是自动交易必需的，哪些只是可选增强；缺少必需能力时会明确阻止自动交易。当前默认只生成单交易所接入，但会保留多交易所扩展缺口。").classes("text-sm text-slate-600")
                with ui.grid(columns=2).classes("w-full gap-4"):
                    terminal_panel = ui.column().classes("w-full gap-4")
                    terminal_detail_panel = ui.column().classes("w-full gap-4")

            with ui.tab_panel(intelligence_tab):
                with ui.grid(columns=3).classes("w-full gap-4"):
                    with ui.column().classes("w-full gap-4"):
                        with ui.card().classes("w-full"):
                            ui.label("情报中心").classes("text-h6")
                            ui.label("这里应该先看到情报结论与历史，再决定是否继续细查来源、财报、暗池和期权。系统也会根据历史查询记录判断你是否在频繁、重复或焦虑式搜索情报。").classes("text-sm text-slate-600")
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
                        intelligence_history_analysis_panel = ui.column().classes("w-full gap-4")
                        with ui.card().classes("w-full"):
                            ui.label("历史情报查看").classes("text-h6")
                            intelligence_history_select = ui.select({}, label="选择一条历史查询", on_change=lambda _: refresh_all()).classes("w-full")
                            with ui.grid(columns=3).classes("w-full gap-4"):
                                intelligence_history_symbol_filter = ui.select({"all": "全部股票"}, value="all", label="按股票筛选", on_change=lambda _: refresh_all()).classes("w-full")
                                intelligence_history_source_filter = ui.select({"all": "全部来源"}, value="all", label="按来源筛选", on_change=lambda _: refresh_all()).classes("w-full")
                                intelligence_history_translated_only = ui.switch("只看含翻译结果", value=False, on_change=lambda _: refresh_all())
                        with ui.grid(columns=2).classes("w-full gap-4"):
                            intelligence_documents_panel = ui.column().classes("w-full gap-4")
                            intelligence_history_panel = ui.column().classes("w-full gap-4")
                            intelligence_history_groups_panel = ui.column().classes("w-full gap-4")
                            intelligence_history_detail_panel = ui.column().classes("w-full gap-4")
                            intelligence_history_payload_panel = ui.column().classes("w-full gap-4")
                            intelligence_financials_panel = ui.column().classes("w-full gap-4")
                            intelligence_dark_pool_panel = ui.column().classes("w-full gap-4")
                            intelligence_options_panel = ui.column().classes("w-full gap-4")
                            agent_activity_panel = ui.column().classes("w-full gap-4")
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
    ui.timer(0.05, lambda: asyncio.create_task(ensure_default_session()), once=True)
    ui.timer(0.1, lambda: asyncio.create_task(refresh_health(False)), once=True)
    ui.timer(0.2, lambda: asyncio.create_task(load_config_state(False)), once=True)
    ui.timer(2.0, lambda: asyncio.create_task(refresh_agent_activity()))
    ui.run(
        title="Sentinel-Alpha NiceGUI",
        host=settings.frontend_host,
        port=settings.frontend_port,
        reload=os.getenv("SENTINEL_UI_RELOAD", "0").lower() in {"1", "true", "yes", "on"},
        show=False,
    )


if __name__ in {"__main__", "__mp_main__"}:
    run()
