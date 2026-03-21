from fastapi.testclient import TestClient

from sentinel_alpha.api.app import create_app
from sentinel_alpha.api.workflow_service import WorkflowService
from sentinel_alpha.domain.models import IntelligenceDocument
from sentinel_alpha.infra.free_market_data import FreeMarketDataService


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
    assert isinstance(payload["libraries"], list)
    assert isinstance(payload["agents"], list)
    assert "recent_errors" in payload
    assert "token_usage" in payload
    assert any(item["name"] == "behavioral_profiler" for item in payload["modules"])
    assert any(item["name"] == "strategy_registry" for item in payload["modules"])
    assert any(item["name"] == "llm_runtime" for item in payload["modules"])
    assert any(item["name"] == "fastapi" for item in payload["libraries"])
    assert any(item["name"] == "uvicorn" for item in payload["libraries"])
    assert all("recommendation" in item for item in payload["modules"])


def test_llm_config_endpoint_exposes_agent_and_task_models() -> None:
    response = client.get("/api/llm-config")
    assert response.status_code == 200
    payload = response.json()
    assert "agents" in payload
    assert "tasks" in payload
    assert "strategy_evolver" in payload["agents"]
    assert "strategy_codegen" in payload["tasks"]


def test_config_endpoints_load_and_validate_payload() -> None:
    loaded = client.get("/api/config")
    assert loaded.status_code == 200
    body = loaded.json()
    assert "payload" in body
    assert "validation" in body
    assert body["validation"]["status"] in {"ok", "warning", "error"}

    tested = client.post("/api/config/test", json={"payload": body["payload"]})
    assert tested.status_code == 200
    assert tested.json()["validation"]["status"] in {"ok", "warning", "error"}

    single = client.post(
        "/api/config/test-item",
        json={"payload": body["payload"], "family": "fundamentals", "provider": "sec"},
    )
    assert single.status_code == 200
    assert single.json()["validation"]["family"] == "fundamentals"
    assert single.json()["validation"]["provider"] == "sec"
    assert len(single.json()["validation"]["checks"]) >= 1


def test_market_data_provider_endpoint_exposes_free_provider_matrix() -> None:
    response = client.get("/api/market-data/providers")
    assert response.status_code == 200
    payload = response.json()
    provider_names = {item["provider"] for item in payload["providers"]}
    assert payload["default_provider"] in provider_names
    assert {"yahoo", "alphavantage", "finnhub", "akshare", "local_file"}.issubset(provider_names)
    fundamentals_provider_names = {item["provider"] for item in payload["fundamentals_providers"]}
    dark_pool_provider_names = {item["provider"] for item in payload["dark_pool_providers"]}
    options_provider_names = {item["provider"] for item in payload["options_providers"]}
    assert {"sec", "alphavantage", "finnhub", "local_file"}.issubset(fundamentals_provider_names)
    assert {"finra", "local_file"}.issubset(dark_pool_provider_names)
    assert {"yahoo_options", "finnhub", "local_file"}.issubset(options_provider_names)


def test_market_data_quote_and_history_endpoints_use_provider_service(monkeypatch) -> None:
    monkeypatch.setattr(
        FreeMarketDataService,
        "fetch_quote",
        lambda self, symbol, provider=None: {"provider": provider or "yahoo", "symbol": symbol, "price": 123.45},
    )
    monkeypatch.setattr(
        FreeMarketDataService,
        "fetch_history",
        lambda self, symbol, interval="1d", lookback="6mo", provider=None: {
            "provider": provider or "yahoo",
            "symbol": symbol,
            "interval": interval,
            "lookback": lookback,
            "bars": [{"timestamp": 1, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 100}],
        },
    )

    quote = client.get("/api/market-data/quote", params={"symbol": "AAPL", "provider": "yahoo"})
    history = client.get("/api/market-data/history", params={"symbol": "AAPL", "interval": "1d", "lookback": "1mo", "provider": "yahoo"})

    assert quote.status_code == 200
    assert quote.json()["symbol"] == "AAPL"
    assert history.status_code == 200
    assert history.json()["bars"][0]["close"] == 1.5


def test_market_data_financials_dark_pool_and_options_endpoints(monkeypatch) -> None:
    monkeypatch.setattr(
        FreeMarketDataService,
        "fetch_financials",
        lambda self, symbol, provider=None: {
            "provider": provider or "sec",
            "symbol": symbol,
            "entity_name": "Apple Inc.",
            "normalized": {
                "entity_name": "Apple Inc.",
                "report_period": "2025-12-31",
                "statements": [{"period_end": "2025-12-31", "revenue": 100.0, "weighted": {"final_weight": 0.95}}],
                "dedupe_summary": {"input_count": 2, "output_count": 1},
                "overall_weight": 0.95,
            },
        },
    )
    monkeypatch.setattr(
        FreeMarketDataService,
        "fetch_dark_pool",
        lambda self, symbol, provider=None: {
            "provider": provider or "finra",
            "symbol": symbol,
            "items": [{"issueSymbol": symbol}],
            "normalized": {
                "records": [{"trade_date": "2026-03-21", "shares": 120000, "weighted": {"final_weight": 0.88}}],
                "dedupe_summary": {"input_count": 3, "output_count": 1},
                "overall_weight": 0.88,
            },
        },
    )
    monkeypatch.setattr(
        FreeMarketDataService,
        "fetch_options",
        lambda self, symbol, provider=None, expiration=None: {
            "provider": provider or "yahoo_options",
            "symbol": symbol,
            "options": [{"strike": 200}],
            "normalized": {
                "contracts": [{"strike": 200, "open_interest": 1000, "weighted": {"final_weight": 0.91}}],
                "dedupe_summary": {"input_count": 4, "output_count": 2},
                "overall_weight": 0.91,
            },
        },
    )

    financials = client.get("/api/market-data/financials", params={"symbol": "AAPL", "provider": "sec"})
    dark_pool = client.get("/api/market-data/dark-pool", params={"symbol": "AAPL", "provider": "finra"})
    options = client.get("/api/market-data/options", params={"symbol": "AAPL", "provider": "yahoo_options"})

    assert financials.status_code == 200
    assert financials.json()["entity_name"] == "Apple Inc."
    assert financials.json()["normalized"]["dedupe_summary"]["output_count"] == 1
    assert dark_pool.status_code == 200
    assert dark_pool.json()["items"][0]["issueSymbol"] == "AAPL"
    assert dark_pool.json()["normalized"]["overall_weight"] == 0.88
    assert options.status_code == 200
    assert options.json()["options"][0]["strike"] == 200
    assert options.json()["normalized"]["contracts"][0]["weighted"]["final_weight"] == 0.91


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
    assert len(completed.json()["report_history"]) >= 1
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
        json={
            "feedback": "Reduce concentration",
            "strategy_type": "trend_following_aligned",
            "iteration_mode": "guided",
            "auto_iterations": 2,
            "objective_metric": "return",
            "target_return_pct": 20,
            "target_win_rate_pct": 58,
            "target_drawdown_pct": 12,
            "target_max_loss_pct": 6,
        },
    )
    assert strategy.status_code == 200
    assert strategy.json()["strategy_package"] is not None
    assert len(strategy.json()["strategy_checks"]) == 2
    assert strategy.json()["strategy_package"]["candidate"]["strategy_type"] == "trend_following_aligned"
    assert strategy.json()["strategy_package"]["trading_preferences"]["trading_frequency"] == "high"
    assert strategy.json()["strategy_package"]["feature_snapshot_version"]
    assert strategy.json()["strategy_package"]["data_bundle_id"]
    assert strategy.json()["strategy_package"]["input_manifest"]["data_bundle_id"]
    assert strategy.json()["strategy_package"]["input_manifest"]["dataset_protocol"] == "time_series_split_with_walk_forward"
    assert len(strategy.json()["data_bundles"]) >= 1
    assert strategy.json()["data_bundles"][-1]["data_bundle_id"] == strategy.json()["strategy_package"]["data_bundle_id"]
    assert "conflict_warning" in strategy.json()["trading_preferences"]
    assert "score" in strategy.json()["strategy_checks"][0]
    assert "required_fix_actions" in strategy.json()["strategy_checks"][0]
    assert "metrics" in strategy.json()["strategy_checks"][0]
    assert strategy.json()["profile_evolution"] is not None
    assert len(strategy.json()["strategy_feedback_log"]) == 1
    assert len(strategy.json()["strategy_training_log"]) >= 1
    assert strategy.json()["strategy_training_log"][-1]["data_bundle_id"]
    assert strategy.json()["strategy_training_log"][-1]["input_manifest"]["data_bundle_id"]
    assert len(strategy.json()["report_history"]) >= 2


def test_intelligence_information_events_are_recorded(monkeypatch) -> None:
    monkeypatch.setattr(
        "sentinel_alpha.agents.intelligence_agent.IntelligenceAgent.search",
        lambda self, query, max_documents=None: [
            IntelligenceDocument(
                document_id="doc-1",
                query=query,
                source="Reuters",
                title="AAPL wins new order",
                url="https://example.com/aapl-order",
                published_at="2026-03-21T08:00:00Z",
                summary="Apple secures a large enterprise order.",
                content="Apple secures a large enterprise order.",
                sentiment_hint=0.4,
            )
        ],
    )
    monkeypatch.setattr(
        FreeMarketDataService,
        "fetch_financials",
        lambda self, symbol, provider=None: {
            "provider": provider or "sec",
            "symbol": symbol,
            "normalized": {
                "entity_name": "Apple Inc.",
                "report_period": "2025-12-31",
                "statements": [{"period_end": "2025-12-31", "revenue": 100.0}],
                "dedupe_summary": {"input_count": 1, "output_count": 1},
                "overall_weight": 0.9,
            },
        },
    )

    created = client.post("/api/sessions", json={"user_name": "Intel", "starting_capital": 100000})
    session_id = created.json()["session_id"]

    searched = client.post(f"/api/sessions/{session_id}/intelligence/search", json={"query": "AAPL", "max_documents": 3})
    assert searched.status_code == 200
    financials = client.post(f"/api/sessions/{session_id}/intelligence/financials", json={"symbol": "AAPL", "provider": "sec"})
    assert financials.status_code == 200

    payload = financials.json()
    assert len(payload["information_events"]) >= 2
    assert any(item["anchor"] == "AAPL" and item["category"] == "financials" for item in payload["information_events"])


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
        json={
            "feedback": "Need faster rebounds",
            "strategy_type": "mean_reversion_aligned",
            "iteration_mode": "free",
            "auto_iterations": 2,
            "objective_metric": "win_rate",
            "target_win_rate_pct": 63,
        },
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
    assert len(body["intelligence_runs"]) == 1
    assert body["intelligence_runs"][0]["report"]["query"] == "NVDA AI demand"
    assert "factors" in body["intelligence_runs"][0]["report"]
    assert len(body["report_history"]) >= 1


def test_financials_dark_pool_and_options_are_archived_on_session() -> None:
    service = WorkflowService()
    service.market_data.fetch_financials = lambda symbol, provider=None: {  # type: ignore[method-assign]
        "provider": provider or "sec",
        "symbol": symbol,
        "entity_name": "Apple Inc.",
    }
    service.market_data.fetch_dark_pool = lambda symbol, provider=None: {  # type: ignore[method-assign]
        "provider": provider or "finra",
        "symbol": symbol,
        "items": [{"issueSymbol": symbol}],
    }
    service.market_data.fetch_options = lambda symbol, provider=None, expiration=None: {  # type: ignore[method-assign]
        "provider": provider or "yahoo_options",
        "symbol": symbol,
        "options": [{"strike": 200}],
    }
    local_client = TestClient(create_app(service))
    created = local_client.post("/api/sessions", json={"user_name": "Intel+", "starting_capital": 300000})
    session_id = created.json()["session_id"]

    fin = local_client.post(
        f"/api/sessions/{session_id}/intelligence/financials",
        json={"symbol": "AAPL", "provider": "sec"},
    )
    dp = local_client.post(
        f"/api/sessions/{session_id}/intelligence/dark-pool",
        json={"symbol": "AAPL", "provider": "finra"},
    )
    opt = local_client.post(
        f"/api/sessions/{session_id}/intelligence/options",
        json={"symbol": "AAPL", "provider": "yahoo_options", "expiration": "2026-04-17"},
    )

    assert fin.status_code == 200
    assert len(fin.json()["financials_runs"]) == 1
    assert "factors" in fin.json()["financials_runs"][0]
    assert dp.status_code == 200
    assert len(dp.json()["dark_pool_runs"]) == 1
    assert "factors" in dp.json()["dark_pool_runs"][0]
    assert opt.status_code == 200
    body = opt.json()
    assert len(body["options_runs"]) == 1
    assert "factors" in body["options_runs"][0]
    event_types = {item["event_type"] for item in body["history_events"]}
    report_types = {item["report_type"] for item in body["report_history"]}
    assert "financials_data_fetched" in event_types
    assert "dark_pool_data_fetched" in event_types
    assert "options_data_fetched" in event_types
    assert "financials_summary" in report_types
    assert "dark_pool_summary" in report_types
    assert "options_summary" in report_types


def test_programmer_agent_run_is_recorded_even_when_disabled() -> None:
    local_client = TestClient(create_app(WorkflowService()))
    created = local_client.post("/api/sessions", json={"user_name": "Coder", "starting_capital": 300000})
    session_id = created.json()["session_id"]

    response = local_client.post(
        f"/api/sessions/{session_id}/programmer/execute",
        json={
            "instruction": "Adjust strategy parameter.",
            "target_files": ["src/sentinel_alpha/strategies/rule_based.py"],
            "context": "Keep current risk controls.",
            "commit_changes": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["programmer_runs"]) == 1
    assert body["programmer_runs"][0]["status"] in {"disabled", "misconfigured", "ok", "error"}


def test_data_source_expansion_agent_run_is_recorded() -> None:
    local_client = TestClient(create_app(WorkflowService()))
    created = local_client.post("/api/sessions", json={"user_name": "Source", "starting_capital": 300000})
    session_id = created.json()["session_id"]

    response = local_client.post(
        f"/api/sessions/{session_id}/data-source/expand",
        json={
            "provider_name": "ExampleSource",
            "category": "market_data",
            "base_url": "https://api.example.com",
            "api_key_env": "EXAMPLE_API_KEY",
            "docs_summary": "REST JSON API with symbol-based quote and history endpoints.",
            "sample_endpoint": "quote",
            "auth_style": "query",
            "response_format": "json",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["data_source_runs"]) == 1
    run = body["data_source_runs"][0]
    assert run["provider_slug"] == "examplesource"
    assert run["validation"]["module_syntax_ok"] is True
    assert run["validation"]["test_syntax_ok"] is True
    assert run["target_module"].startswith("src/sentinel_alpha/infra/generated_sources/")
    assert run["target_test"].startswith("tests/generated/")
    assert len(body["report_history"]) >= 1
    assert any(item["event_type"] == "data_source_expansion_generated" for item in body["history_events"])


def test_data_source_expansion_output_is_handoff_ready_for_programmer_agent() -> None:
    local_client = TestClient(create_app(WorkflowService()))
    created = local_client.post("/api/sessions", json={"user_name": "Bridge", "starting_capital": 300000})
    session_id = created.json()["session_id"]

    response = local_client.post(
        f"/api/sessions/{session_id}/data-source/expand",
        json={
            "provider_name": "Provider Bridge",
            "category": "fundamentals",
            "base_url": "https://api.provider-bridge.example",
            "api_key_env": "BRIDGE_KEY",
            "docs_summary": "Financial data endpoint with JSON responses.",
            "sample_endpoint": "fundamentals",
            "auth_style": "query",
            "response_format": "json",
        },
    )

    assert response.status_code == 200
    run = response.json()["data_source_runs"][-1]
    assert run["validation"]["ready_for_programmer_agent"] is True
    assert run["target_module"].split("/", 3)[0:3] == ["src", "sentinel_alpha", "infra"]
    assert run["config_candidate"]["provider_name"] == "provider_bridge"


def test_data_source_expansion_can_be_applied_by_programmer_agent() -> None:
    local_client = TestClient(create_app(WorkflowService()))
    created = local_client.post("/api/sessions", json={"user_name": "BridgeApply", "starting_capital": 300000})
    session_id = created.json()["session_id"]

    expanded = local_client.post(
        f"/api/sessions/{session_id}/data-source/expand",
        json={
            "provider_name": "Bridge Apply",
            "category": "options",
            "base_url": "https://api.bridge-apply.example",
            "api_key_env": "BRIDGE_APPLY_KEY",
            "docs_summary": "Options chain API with JSON payloads.",
            "sample_endpoint": "options",
            "auth_style": "header",
            "response_format": "json",
        },
    )
    run_id = expanded.json()["data_source_runs"][-1]["run_id"]

    applied = local_client.post(
        f"/api/sessions/{session_id}/data-source/apply",
        json={"run_id": run_id, "commit_changes": False},
    )

    assert applied.status_code == 200
    body = applied.json()
    run = body["data_source_runs"][-1]
    assert run["run_id"] == run_id
    assert run["programmer_apply"]["applied_run_id"] == run_id
    assert run["programmer_apply"]["status"] in {"disabled", "misconfigured", "ok", "error"}
    assert any(
        item["event_type"] in {"data_source_expansion_applied", "data_source_expansion_apply_failed"}
        for item in body["history_events"]
    )


def test_trading_terminal_integration_agent_run_is_recorded() -> None:
    service = WorkflowService()
    service.terminal_integrator._fetch_text = lambda url: {  # type: ignore[method-assign]
        "ok": True,
        "error": None,
        "content": f"terminal docs for {url} place order cancel order positions",
    }
    local_client = TestClient(create_app(service))
    created = local_client.post("/api/sessions", json={"user_name": "Terminal", "starting_capital": 300000})
    session_id = created.json()["session_id"]

    response = local_client.post(
        f"/api/sessions/{session_id}/terminal/expand",
        json={
            "terminal_name": "ExampleBroker",
            "terminal_type": "broker_api",
            "official_docs_url": "https://example.com/docs",
            "docs_search_url": "https://example.com/search?q=orders",
            "api_base_url": "https://api.example.com",
            "api_key_env": "EXAMPLE_BROKER_KEY",
            "auth_style": "bearer",
            "order_endpoint": "orders/place",
            "cancel_endpoint": "orders/cancel",
            "positions_endpoint": "portfolio/positions",
            "docs_summary": "REST trading API.",
            "user_notes": "Need order and cancel support.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["terminal_integration_runs"]) == 1
    run = body["terminal_integration_runs"][0]
    assert run["terminal_slug"] == "examplebroker"
    assert run["validation"]["module_syntax_ok"] is True
    assert run["validation"]["test_syntax_ok"] is True
    assert run["validation"]["docs_fetch_ok"] is True
    assert any(item["event_type"] == "trading_terminal_integration_generated" for item in body["history_events"])


def test_trading_terminal_integration_can_be_applied_by_programmer_agent() -> None:
    service = WorkflowService()
    service.terminal_integrator._fetch_text = lambda url: {  # type: ignore[method-assign]
        "ok": True,
        "error": None,
        "content": f"terminal docs for {url} place order cancel order positions",
    }
    local_client = TestClient(create_app(service))
    created = local_client.post("/api/sessions", json={"user_name": "TerminalApply", "starting_capital": 300000})
    session_id = created.json()["session_id"]

    expanded = local_client.post(
        f"/api/sessions/{session_id}/terminal/expand",
        json={
            "terminal_name": "ApplyBroker",
            "terminal_type": "rest_gateway",
            "official_docs_url": "https://example.com/docs",
            "docs_search_url": "https://example.com/search?q=positions",
            "api_base_url": "https://api.example.com",
            "api_key_env": "APPLY_BROKER_KEY",
            "auth_style": "header",
            "order_endpoint": "orders",
            "cancel_endpoint": "orders/cancel",
            "positions_endpoint": "positions",
            "docs_summary": "REST gateway API.",
            "user_notes": "Need positions and cancel.",
        },
    )
    run_id = expanded.json()["terminal_integration_runs"][-1]["run_id"]

    applied = local_client.post(
        f"/api/sessions/{session_id}/terminal/apply",
        json={"run_id": run_id, "commit_changes": False},
    )

    assert applied.status_code == 200
    body = applied.json()
    run = body["terminal_integration_runs"][-1]
    assert run["run_id"] == run_id
    assert run["programmer_apply"]["applied_run_id"] == run_id
    assert run["programmer_apply"]["status"] in {"disabled", "misconfigured", "ok", "error"}
    assert any(
        item["event_type"] in {"trading_terminal_integration_applied", "trading_terminal_integration_apply_failed"}
        for item in body["history_events"]
    )
