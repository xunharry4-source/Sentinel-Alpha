from fastapi.testclient import TestClient

from sentinel_alpha.api.app import create_app
from sentinel_alpha.api.workflow_service import WorkflowService
from sentinel_alpha.domain.models import IntelligenceDocument


client = TestClient(create_app(WorkflowService()))


def test_health_endpoint_exposes_frontend_api_and_database_status() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["frontend"]["status"] == "ok"
    assert payload["api"]["status"] == "ok"
    assert payload["database"]["status"] in {"configured", "not_configured"}


def test_system_health_endpoint_exposes_module_statuses() -> None:
    response = client.get("/api/system-health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "warning", "degraded"}
    assert "service_mode" in payload
    assert isinstance(payload["modules"], list)
    assert any(item["name"] == "behavioral_profiler" for item in payload["modules"])
    assert any(item["name"] == "strategy_registry" for item in payload["modules"])
    assert all("recommendation" in item for item in payload["modules"])


def test_full_workflow_api() -> None:
    created = client.post("/api/sessions", json={"user_name": "Harry", "starting_capital": 500000})
    assert created.status_code == 200
    session = created.json()
    session_id = session["session_id"]

    generated = client.post(f"/api/sessions/{session_id}/generate-scenarios")
    assert generated.status_code == 200
    assert len(generated.json()["scenarios"]) == 6

    preferences = client.post(
        f"/api/sessions/{session_id}/trading-preferences",
        json={
            "trading_frequency": "high",
            "preferred_timeframe": "minute",
            "rationale": "I do not want to stare at the screen all day.",
        },
    )
    assert preferences.status_code == 200
    assert preferences.json()["trading_preferences"]["preferred_timeframe"] == "minute"

    for event in [
        {"scenario_id": "scenario-fake-reversal", "price_drawdown_pct": -10, "action": "buy", "noise_level": 0.9, "sentiment_pressure": 0.8, "latency_seconds": 40},
        {"scenario_id": "scenario-fake-reversal", "price_drawdown_pct": -15, "action": "sell", "noise_level": 0.8, "sentiment_pressure": -0.7, "latency_seconds": 35},
    ]:
        response = client.post(f"/api/sessions/{session_id}/simulation/events", json=event)
        assert response.status_code == 200

    completed = client.post(f"/api/sessions/{session_id}/simulation/complete", json={"symbol": "QQQ"})
    assert completed.status_code == 200
    assert completed.json()["behavioral_report"] is not None
    assert completed.json()["behavioral_report"]["recommended_trading_frequency"] in {"low", "medium", "high"}
    assert completed.json()["behavioral_report"]["recommended_timeframe"] in {"minute", "daily", "weekly"}
    assert completed.json()["behavioral_report"]["recommended_strategy_type"] in {
        "rule_based_aligned",
        "trend_following_aligned",
        "mean_reversion_aligned",
    }

    preferences_after_report = client.post(
        f"/api/sessions/{session_id}/trading-preferences",
        json={
            "trading_frequency": "high",
            "preferred_timeframe": "minute",
            "rationale": "I still want more action.",
        },
    )
    assert preferences_after_report.status_code == 200
    assert "conflict_warning" in preferences_after_report.json()["trading_preferences"]

    universe = client.post(
        f"/api/sessions/{session_id}/trade-universe",
        json={"input_type": "stocks", "symbols": ["TSLA", "NVDA"], "allow_overfit_override": False},
    )
    assert universe.status_code == 200
    assert len(universe.json()["trade_universe"]["expanded"]) >= 5

    strategy = client.post(
        f"/api/sessions/{session_id}/strategy/iterate",
        json={"feedback": "Reduce concentration", "strategy_type": "trend_following_aligned"},
    )
    assert strategy.status_code == 200
    assert strategy.json()["strategy_package"] is not None
    assert len(strategy.json()["strategy_checks"]) == 2
    assert strategy.json()["strategy_package"]["candidate"]["strategy_type"] == "trend_following_aligned"
    assert strategy.json()["strategy_package"]["trading_preferences"]["trading_frequency"] == "high"
    assert "conflict_warning" in strategy.json()["trading_preferences"]
    assert "score" in strategy.json()["strategy_checks"][0]
    assert "required_fix_actions" in strategy.json()["strategy_checks"][0]
    assert "metrics" in strategy.json()["strategy_checks"][0]
    assert strategy.json()["profile_evolution"] is not None
    assert len(strategy.json()["strategy_feedback_log"]) == 1

    market_snapshot = client.post(
        f"/api/sessions/{session_id}/market-snapshots",
        json={
            "symbol": "TSLA",
            "timeframe": "1m",
            "open_price": 200,
            "high_price": 205,
            "low_price": 198,
            "close_price": 203,
            "volume": 120000,
            "source": "test_feed",
            "regime_tag": "bull",
        },
    )
    assert market_snapshot.status_code == 200
    assert len(market_snapshot.json()["market_snapshots"]) == 1

    trade_record = client.post(
        f"/api/sessions/{session_id}/trade-executions",
        json={
            "symbol": "TSLA",
            "side": "buy",
            "quantity": 10,
            "price": 203,
            "notional": 2030,
            "execution_mode": "manual",
            "strategy_version": "v1",
            "realized_pnl_pct": -9.5,
            "user_initiated": True,
            "note": "User overrode system suggestion.",
        },
    )
    assert trade_record.status_code == 200
    assert len(trade_record.json()["trade_records"]) == 1
    assert len(trade_record.json()["profile_evolution"]["events"]) >= 3

    approved = client.post(f"/api/sessions/{session_id}/strategy/approve")
    assert approved.status_code == 200
    assert approved.json()["phase"] == "strategy_approved"

    deployed = client.post(f"/api/sessions/{session_id}/deployment", json={"execution_mode": "advice_only"})
    assert deployed.status_code == 200
    assert deployed.json()["execution_mode"] == "advice_only"

    monitors = client.get(f"/api/sessions/{session_id}/monitors")
    assert monitors.status_code == 200
    assert len(monitors.json()["signals"]) == 3

    profiler_json = client.get(f"/api/sessions/{session_id}/behavioral-report-json")
    assert profiler_json.status_code == 200
    assert profiler_json.json()["behavioral_report"] is not None

    evolution_json = client.get(f"/api/sessions/{session_id}/profile-evolution-json")
    assert evolution_json.status_code == 200
    assert evolution_json.json()["profile_evolution"] is not None


def test_strategy_iteration_requires_rework_when_checks_fail() -> None:
    created = client.post("/api/sessions", json={"user_name": "Stress", "starting_capital": 500000})
    session_id = created.json()["session_id"]

    client.post(f"/api/sessions/{session_id}/generate-scenarios")
    for event in [
        {"scenario_id": "scenario-fake-reversal", "price_drawdown_pct": -12, "action": "buy", "noise_level": 0.95, "sentiment_pressure": 0.9, "latency_seconds": 20},
        {"scenario_id": "scenario-fake-reversal", "price_drawdown_pct": -18, "action": "buy", "noise_level": 0.92, "sentiment_pressure": 0.88, "latency_seconds": 25},
        {"scenario_id": "scenario-fake-reversal", "price_drawdown_pct": -22, "action": "hold", "noise_level": 0.91, "sentiment_pressure": 0.82, "latency_seconds": 10},
    ]:
        client.post(f"/api/sessions/{session_id}/simulation/events", json=event)

    client.post(f"/api/sessions/{session_id}/simulation/complete", json={"symbol": "QQQ"})
    client.post(
        f"/api/sessions/{session_id}/trade-universe",
        json={"input_type": "stocks", "symbols": ["TSLA"], "allow_overfit_override": True},
    )
    strategy = client.post(
        f"/api/sessions/{session_id}/strategy/iterate",
        json={"feedback": "Need faster rebounds", "strategy_type": "mean_reversion_aligned"},
    )

    assert strategy.status_code == 200
    body = strategy.json()
    assert body["phase"] == "strategy_rework_required"
    assert any(item["status"] == "fail" for item in body["strategy_checks"])

    approved = client.post(f"/api/sessions/{session_id}/strategy/approve")
    assert approved.status_code == 400


def test_intelligence_search_attaches_documents_to_session() -> None:
    service = WorkflowService()
    service.intelligence.search = lambda query, max_documents=None: [  # type: ignore[method-assign]
        IntelligenceDocument(
            document_id="doc-1",
            query=query,
            title="NVDA demand stays strong",
            url="https://example.com/nvda",
            source="example.com",
            published_at="2026-03-21",
            summary="AI server demand remains strong.",
            content="AI server demand remains strong and margins are holding.",
            sentiment_hint=0.4,
        )
    ]
    local_client = TestClient(create_app(service))
    created = local_client.post("/api/sessions", json={"user_name": "Intel", "starting_capital": 300000})
    session_id = created.json()["session_id"]

    searched = local_client.post(
        f"/api/sessions/{session_id}/intelligence/search",
        json={"query": "NVDA AI demand", "max_documents": 3},
    )

    assert searched.status_code == 200
    body = searched.json()
    assert len(body["intelligence_documents"]) == 1
    assert body["intelligence_documents"][0]["query"] == "NVDA AI demand"
