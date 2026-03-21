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
        )
    )

    assert result["terminal_slug"] == "example_broker"
    assert result["validation"]["module_syntax_ok"] is True
    assert result["validation"]["test_syntax_ok"] is True
    assert result["validation"]["docs_fetch_ok"] is True
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
        )
    )
    result = agent.run_smoke_test(package)
    assert result["status"] in {"ok", "warning"}
    assert len(result["checks"]) == 6
    assert any(item["name"] == "ping" for item in result["checks"])
    assert any(item["name"] == "order_contract" for item in result["checks"])
    assert any(item["name"] == "order_status_contract" for item in result["checks"])
    assert any(item["name"] == "balances_contract" for item in result["checks"])
    assert len(result["calls"]) == 5
