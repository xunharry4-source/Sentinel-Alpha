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

