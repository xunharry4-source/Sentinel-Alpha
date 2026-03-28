from __future__ import annotations

from sentinel_alpha.agents.trading_terminal_integration_agent import (
    TradingTerminalIntegrationAgent,
    TradingTerminalIntegrationRequest,
)


def test_trading_terminal_integration_agent_generates_package_from_minimal_input() -> None:
    agent = TradingTerminalIntegrationAgent()
    result = agent.build_terminal_package(
        TradingTerminalIntegrationRequest(
            interface_documentation=(
                "https://broker.example/docs\n"
                "Base URL: https://api.broker.example\n"
                "Authentication: Bearer token\n"
                "POST /orders place order\n"
                "GET /orders/{id} query order status\n"
                "GET /positions account positions\n"
                "GET /balances account balances\n"
                "GET /fills trade records\n"
            ),
            api_key="secret-key",
        )
    )

    assert result["terminal_slug"] == "broker"
    assert result["validation"]["module_syntax_ok"] is True
    assert result["validation"]["test_syntax_ok"] is True
    assert result["validation"]["module_smoke_ok"] is True
    assert result["integration_readiness_summary"]["automatic_trading_ready"] is True
    assert result["integration_readiness_summary"]["missing_required_capabilities"] == []
    assert "trade_records" not in result["integration_readiness_summary"]["missing_optional_capabilities"]
    assert result["exchange_support_summary"]["scope"] == "single_exchange"
    assert result["exchange_support_summary"]["multi_exchange_ready"] is False
    assert result["config_candidate"]["provider_config"]["capabilities"]["place_order"]["endpoint"] == "orders"
    assert result["config_candidate"]["provider_config"]["capabilities"]["trade_records"]["endpoint"] == "fills"
    assert "def fetch_trade_records" in result["generated_module_code"]


def test_trading_terminal_integration_agent_blocks_auto_trading_when_required_capabilities_are_missing() -> None:
    agent = TradingTerminalIntegrationAgent()
    result = agent.build_terminal_package(
        TradingTerminalIntegrationRequest(
            interface_documentation=(
                "https://broker.example/docs\n"
                "Base URL: https://api.broker.example\n"
                "Authentication: Header X-API-Key\n"
                "POST /orders place order\n"
                "GET /positions account positions\n"
            ),
            api_key="secret-key",
        )
    )

    readiness = result["integration_readiness_summary"]
    assert readiness["automatic_trading_ready"] is False
    assert "order_status" in readiness["missing_required_capabilities"]
    assert "balances" in readiness["missing_required_capabilities"]
    assert readiness["status"] == "blocked"


def test_trading_terminal_integration_agent_warns_for_optional_capabilities() -> None:
    agent = TradingTerminalIntegrationAgent()
    result = agent.build_terminal_package(
        TradingTerminalIntegrationRequest(
            interface_documentation=(
                "https://broker.example/docs\n"
                "Base URL: https://api.broker.example\n"
                "Authentication: Bearer token\n"
                "POST /orders place order\n"
                "GET /orders/{id} query order status\n"
                "GET /positions account positions\n"
                "GET /balances account balances\n"
            ),
            api_key="secret-key",
        )
    )

    readiness = result["integration_readiness_summary"]
    assert readiness["automatic_trading_ready"] is True
    assert "trade_records" in readiness["missing_optional_capabilities"]
    assert readiness["status"] == "caution"


def test_trading_terminal_integration_agent_runs_smoke_test_with_capability_classification() -> None:
    agent = TradingTerminalIntegrationAgent()
    package = agent.build_terminal_package(
        TradingTerminalIntegrationRequest(
            interface_documentation=(
                "https://broker.example/docs\n"
                "Base URL: https://api.broker.example\n"
                "Authentication: Bearer token\n"
                "POST /orders place order\n"
                "POST /orders/cancel cancel order\n"
                "GET /orders/{id} query order status\n"
                "GET /positions account positions\n"
                "GET /balances account balances\n"
                "GET /fills trade records\n"
            ),
            api_key="secret-key",
            response_field_map={
                "positions_root": "positions",
                "balances_root": "balances",
                "order_status_root": "order",
                "trade_records_root": "records",
            },
        )
    )

    result = agent.run_smoke_test(package)
    assert result["status"] == "ok"
    assert any(item["name"] == "place_order_capability" and item["status"] == "pass" for item in result["checks"])
    assert any(item["name"] == "trade_records_capability" and item["status"] == "pass" for item in result["checks"])
    assert any(item["name"] == "trade_records_shape" and item["status"] == "pass" for item in result["checks"])
    assert len(result["calls"]) >= 5
    assert result["repair_summary"]["status"] == "clear"
