"""
End-to-end workflow test against a running Sentinel-Alpha API.

This script is intentionally "no-cheat":
- It refuses to claim success if live LLM is not active.
- It records HTTP status, error details, and key provenance fields.

Usage:
  python scripts/e2e_full_flow_live_llm.py

Env:
  SENTINEL_API_BASE=http://127.0.0.1:8001
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from urllib.error import HTTPError
from urllib.request import Request, urlopen


API_BASE = os.getenv("SENTINEL_API_BASE", "http://127.0.0.1:8001").rstrip("/")


@dataclass
class StepResult:
    name: str
    ok: bool
    status: int | None = None
    detail: str | None = None
    extra: dict | None = None


def _json_request(method: str, path: str, payload: dict | None = None, timeout: int = 60) -> tuple[int, dict]:
    url = f"{API_BASE}{path}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            body = json.loads(raw) if raw else {}
        except Exception:
            body = {"raw": raw}
        return exc.code, body


def _require_live_llm() -> StepResult:
    status, cfg = _json_request("GET", "/api/llm-config", None, timeout=15)
    if status != 200:
        return StepResult("llm_config", False, status, f"GET /api/llm-config failed: {cfg!r}")
    prof = (cfg.get("agents") or {}).get("behavioral_profiler") or {}
    mode = prof.get("generation_mode")
    creds = prof.get("credential_count")
    if mode != "live_llm" or not creds:
        return StepResult(
            "llm_live_required",
            False,
            200,
            "Live LLM is not active. Set GOOGLE_API_KEY_1.. (and GOOGLE_API_BASE if needed) in the API container environment.",
            extra={"behavioral_profiler.generation_mode": mode, "behavioral_profiler.credential_count": creds},
        )
    return StepResult("llm_live_required", True, 200, "live_llm is active", extra={"credential_count": creds})


def main() -> int:
    results: list[StepResult] = []

    # Health
    st, payload = _json_request("GET", "/api/health", None, timeout=15)
    results.append(StepResult("health", st == 200, st, payload.get("database", {}).get("detail") or str(payload)[:200]))
    st, sys_health = _json_request("GET", "/api/system-health", None, timeout=30)
    results.append(StepResult("system_health", st == 200, st, sys_health.get("status") if isinstance(sys_health, dict) else str(sys_health)[:80]))

    # LLM must be live
    live = _require_live_llm()
    results.append(live)
    if not live.ok:
        _print(results)
        return 2

    # Create session
    st, snap = _json_request("POST", "/api/sessions", {"user_name": "E2E_LIVE", "starting_capital": 500000}, timeout=30)
    session_id = (snap or {}).get("session_id")
    results.append(StepResult("create_session", st == 200 and bool(session_id), st, f"session_id={session_id}"))
    if not session_id:
        _print(results)
        return 2

    # Generate scenarios
    st, snap = _json_request("POST", f"/api/sessions/{session_id}/generate-scenarios", None, timeout=30)
    results.append(StepResult("generate_scenarios", st == 200, st, f"scenarios={len((snap or {}).get('scenarios') or [])}"))

    # Intelligence (live LLM path for summarization; also exercises external fetch)
    st, snap = _json_request(
        "POST",
        f"/api/sessions/{session_id}/intelligence/search",
        {"query": "NVDA AI demand", "max_documents": 3},
        timeout=90,
    )
    docs = (snap or {}).get("intelligence_documents") or []
    runs = (snap or {}).get("intelligence_runs") or []
    results.append(StepResult("intelligence_search", st == 200 and (len(docs) > 0 or len(runs) > 0), st, f"docs={len(docs)} runs={len(runs)}"))

    # Fundamentals / dark pool / options lookups (external providers, no API key expected for defaults)
    st, snap = _json_request("POST", f"/api/sessions/{session_id}/intelligence/financials", {"symbol": "AAPL", "provider": "sec"}, timeout=60)
    results.append(StepResult("financials_lookup", st == 200, st, f"runs={len((snap or {}).get('financials_runs') or [])}"))

    st, snap = _json_request("POST", f"/api/sessions/{session_id}/intelligence/dark-pool", {"symbol": "AAPL", "provider": "finra"}, timeout=60)
    results.append(StepResult("dark_pool_lookup", st == 200, st, f"runs={len((snap or {}).get('dark_pool_runs') or [])}"))

    st, snap = _json_request("POST", f"/api/sessions/{session_id}/intelligence/options", {"symbol": "AAPL", "provider": "yahoo_options"}, timeout=60)
    results.append(StepResult("options_lookup", st == 200, st, f"runs={len((snap or {}).get('options_runs') or [])}"))

    # Preferences
    st, snap = _json_request(
        "POST",
        f"/api/sessions/{session_id}/trading-preferences",
        {"trading_frequency": "high", "preferred_timeframe": "minute", "rationale": "E2E live llm test"},
        timeout=30,
    )
    results.append(StepResult("trading_preferences", st == 200, st, (snap or {}).get("phase")))

    # Events
    for idx, ev in enumerate(
        [
            {"scenario_id": "scenario-fake-reversal", "price_drawdown_pct": -10, "action": "buy", "noise_level": 0.9, "sentiment_pressure": 0.8, "latency_seconds": 40},
            {"scenario_id": "scenario-fake-reversal", "price_drawdown_pct": -15, "action": "sell", "noise_level": 0.8, "sentiment_pressure": -0.7, "latency_seconds": 35},
        ],
        1,
    ):
        st, snap = _json_request("POST", f"/api/sessions/{session_id}/simulation/events", ev, timeout=30)
        results.append(StepResult(f"simulation_event_{idx}", st == 200, st, (snap or {}).get("phase")))

    # Complete simulation -> must produce live_llm reports
    st, snap = _json_request("POST", f"/api/sessions/{session_id}/simulation/complete", {"symbol": "QQQ"}, timeout=90)
    ok = st == 200
    gen_mode = ((snap or {}).get("behavioral_user_report") or {}).get("report_generation_mode")
    if ok and gen_mode != "live_llm":
        ok = False
    results.append(
        StepResult(
            "complete_simulation",
            ok,
            st,
            f"report_generation_mode={gen_mode}",
            extra={"behavioral_system_report.analysis_warning": ((snap or {}).get("behavioral_system_report") or {}).get("analysis_warning")},
        )
    )

    # Trade universe
    st, snap = _json_request(
        "POST",
        f"/api/sessions/{session_id}/trade-universe",
        {"input_type": "stocks", "symbols": ["TSLA", "NVDA"], "allow_overfit_override": False},
        timeout=30,
    )
    expanded = (((snap or {}).get("trade_universe") or {}).get("expanded") or [])
    results.append(StepResult("trade_universe", st == 200 and len(expanded) >= 5, st, f"expanded={len(expanded)}"))

    # Strategy iterate
    st, snap = _json_request(
        "POST",
        f"/api/sessions/{session_id}/strategy/iterate",
        {
            "feedback": "Reduce concentration",
            "strategy_type": "trend_following_aligned",
            "iteration_mode": "guided",
            "auto_iterations": 1,
            "objective_metric": "return",
            "target_return_pct": 20,
            "target_win_rate_pct": 58,
            "target_drawdown_pct": 12,
            "target_max_loss_pct": 6,
        },
        timeout=180,
    )
    pkg = (snap or {}).get("strategy_package") or {}
    results.append(StepResult("strategy_iterate", st == 200 and bool(pkg), st, f"version={pkg.get('version_label') or 'unknown'}"))

    # Data source expansion agent (docs_url exercises "allow passing a document address directly")
    st, snap = _json_request(
        "POST",
        f"/api/sessions/{session_id}/data-source/expand",
        {
            "provider_name": "example-provider",
            "category": "market_data",
            "base_url": "https://example.com/api",
            "api_key_envs": ["EXAMPLE_API_KEY"],
            "docs_url": "https://example.com/docs",
            "docs_summary": "Example docs for E2E test",
            "sample_endpoint": "/quote?symbol=SPY",
            "auth_style": "header",
            "response_format": "json",
        },
        timeout=120,
    )
    results.append(StepResult("data_source_expand", st == 200, st, f"runs={len((snap or {}).get('data_source_runs') or [])}"))

    # Terminal integration agent (expand + test only; apply is optional/side-effectful)
    st, snap = _json_request(
        "POST",
        f"/api/sessions/{session_id}/terminal/expand",
        {
            "terminal_name": "ApplyBroker",
            "terminal_type": "broker_api",
            "official_docs_url": "https://example.com/applybroker/docs",
            "docs_search_url": "https://example.com/applybroker/search",
            "api_base_url": "https://example.com/applybroker/api",
            "api_key_envs": ["APPLYBROKER_API_KEY"],
            "auth_style": "header",
            "order_endpoint": "/orders",
            "cancel_endpoint": "/orders/{id}/cancel",
            "order_status_endpoint": "/orders/{id}",
            "positions_endpoint": "/positions",
            "balances_endpoint": "/balances",
            "docs_summary": "E2E docs stub for terminal integration.",
        },
        timeout=180,
    )
    terminal_runs = (snap or {}).get("terminal_integration_runs") or []
    run_id = terminal_runs[-1]["run_id"] if terminal_runs else None
    results.append(StepResult("terminal_expand", st == 200 and bool(run_id), st, f"run_id={run_id}"))

    st, snap = _json_request("POST", f"/api/sessions/{session_id}/terminal/test", {"run_id": run_id}, timeout=60)
    terminal_runs = (snap or {}).get("terminal_integration_runs") or []
    last_status = terminal_runs[-1].get("status") if terminal_runs else None
    results.append(StepResult("terminal_test", st == 200 and last_status == "ok", st, f"status={last_status}"))

    # Token usage snapshot
    st, sys_health = _json_request("GET", "/api/system-health", None, timeout=30)
    usage = (sys_health or {}).get("token_usage", {}).get("aggregate", {}) if isinstance(sys_health, dict) else {}
    results.append(StepResult("token_usage", st == 200, st, f"api_requests={usage.get('api_request_count')} total_tokens={usage.get('total_tokens')} live={usage.get('live_request_count')} fallback={usage.get('fallback_request_count')}"))

    _print(results)
    return 0 if all(r.ok for r in results) else 2


def _print(results: list[StepResult]) -> None:
    width = max(len(r.name) for r in results) if results else 10
    print(f"API_BASE={API_BASE}")
    for r in results:
        status = r.status if r.status is not None else "-"
        flag = "PASS" if r.ok else "FAIL"
        detail = r.detail or ""
        print(f"{r.name.ljust(width)}  {flag}  status={status}  {detail}")
        if r.extra:
            safe = json.dumps(r.extra, ensure_ascii=False)
            print(f"{'':{width}}        extra={safe}")


if __name__ == "__main__":
    raise SystemExit(main())
