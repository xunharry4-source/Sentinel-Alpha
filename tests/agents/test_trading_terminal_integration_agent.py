from __future__ import annotations

from sentinel_alpha.agents.trading_terminal_integration_agent import (
    TradingTerminalIntegrationAgent,
    TradingTerminalIntegrationRequest,
)


def test_trading_terminal_integration_agent_generates_valid_code_and_test() -> None:
    agent = TradingTerminalIntegrationAgent()
    agent._fetch_text = lambda url: {"ok": True, "error": None, "content": "place order cancel order positions api"}  # type: ignore[method-assign]
    result = agent.build_terminal_package(
        TradingTerminalIntegrationRequest(
            terminal_name="Example Broker",
            terminal_type="broker_api",
            official_docs_url="https://example.com/docs",
            docs_search_url="https://example.com/search?q=orders",
            api_base_url="https://api.example.com",
            api_key_env="EXAMPLE_BROKER_KEY",
            auth_style="bearer",
            order_endpoint="orders/place",
            cancel_endpoint="orders/cancel",
            order_status_endpoint="orders/status",
            positions_endpoint="portfolio/positions",
            balances_endpoint="account/balances",
            docs_summary="REST trading API with limit-order support.",
            user_notes="Need place, cancel, positions.",
            response_field_map={"positions_root": "holdings", "balances_root": "account_info"},
        )
    )

    assert result["terminal_slug"] == "example_broker"
    assert result["validation"]["module_syntax_ok"] is True
    assert result["validation"]["test_syntax_ok"] is True
    assert result["validation"]["docs_fetch_ok"] is True
    assert result["integration_readiness_summary"]["status"] in {"ready", "caution", "blocked"}
    assert result["integration_readiness_summary"]["endpoint_count"] == 5
    assert result["config_candidate"]["provider_config"]["response_field_map"]["positions_root"] == "holdings"
    assert result["config_candidate"]["provider_config"]["response_field_map"]["balances_root"] == "account_info"
    assert "class ExampleBrokerTerminalAdapter" in result["generated_module_code"]
    assert "def place_order" in result["generated_module_code"]
    assert result["target_module"].startswith("src/sentinel_alpha/infra/generated_terminals/")


def test_trading_terminal_integration_agent_preserves_docs_context_in_package() -> None:
    agent = TradingTerminalIntegrationAgent()
    agent._fetch_text = lambda url: {"ok": True, "error": None, "content": f"doc for {url} order cancel position auth"}  # type: ignore[method-assign]
    result = agent.build_terminal_package(
        TradingTerminalIntegrationRequest(
            terminal_name="Fix Bridge",
            terminal_type="fix_gateway",
            official_docs_url="https://broker.example/docs",
            docs_search_url="https://broker.example/search?q=fix+order",
            api_base_url="https://gateway.example",
            api_key_env=None,
            auth_style="header",
            order_endpoint="fix/order",
            cancel_endpoint="fix/cancel",
            order_status_endpoint="fix/order-status",
            positions_endpoint="fix/positions",
            balances_endpoint="fix/balances",
            docs_summary="FIX gateway wrapper.",
            user_notes=None,
        )
    )

    assert result["docs_context"]["docs_fetch_ok"] is True
    assert "broker.example/docs" in result["docs_context"]["docs_excerpt"]
    assert result["config_candidate"]["terminal_name"] == "fix_bridge"
    assert result["integration_readiness_summary"]["status"] in {"ready", "caution"}
    assert result["config_candidate"]["provider_config"]["response_field_map"]["positions_root"] == "positions"
    assert result["config_candidate"]["provider_config"]["response_field_map"]["order_status_state"] == "status"


def test_trading_terminal_integration_agent_runs_smoke_test() -> None:
    agent = TradingTerminalIntegrationAgent()
    package = agent.build_terminal_package(
        TradingTerminalIntegrationRequest(
            terminal_name="Smoke Broker",
            terminal_type="broker_api",
            official_docs_url="https://example.com/docs",
            docs_search_url=None,
            api_base_url="https://api.example.com",
            api_key_env="SMOKE_KEY",
            auth_style="header",
            order_endpoint="orders/place",
            cancel_endpoint="orders/cancel",
            order_status_endpoint="orders/status",
            positions_endpoint="portfolio/positions",
            balances_endpoint="account/balances",
            docs_summary="REST trading API.",
            user_notes=None,
            response_field_map={
                "positions_root": "holdings",
                "position_symbol": "ticker",
                "position_quantity": "shares",
                "balances_root": "account_info",
                "balance_cash": "cash_balance",
                "balance_buying_power": "bp",
                "order_status_root": "status_payload",
                "order_status_id": "id",
                "order_status_state": "state",
            },
        )
    )
    result = agent.run_smoke_test(package)
    assert result["status"] in {"ok", "warning"}
    assert len(result["checks"]) == 9
    assert any(item["name"] == "ping" for item in result["checks"])
    assert any(item["name"] == "order_contract" for item in result["checks"])
    assert any(item["name"] == "order_status_contract" for item in result["checks"])
    assert any(item["name"] == "balances_contract" for item in result["checks"])
    assert any(item["name"] == "positions_shape" for item in result["checks"])
    assert any(item["name"] == "balances_shape" for item in result["checks"])
    assert any(item["name"] == "order_status_shape" for item in result["checks"])
    assert all(item["status"] == "pass" for item in result["checks"] if item["name"] in {"positions_shape", "balances_shape", "order_status_shape"})
    assert len(result["calls"]) == 5
    assert result["repair_summary"]["status"] in {"clear", "needs_repair"}
    assert "primary_route" in result["repair_summary"]


def test_trading_terminal_integration_agent_shape_checks_fail_on_invalid_types() -> None:
    agent = TradingTerminalIntegrationAgent()
    assert agent._is_valid_positions_shape([{"ticker": "AAPL", "shares": "100"}], "ticker", "shares") is False
    assert agent._is_valid_balances_shape({"cash_balance": "100000", "bp": 180000.0}, "cash_balance", "bp") is False
    assert agent._is_valid_order_status_shape({"id": "ORD-1", "state": 1}, "id", "state", "ORD-1") is False
