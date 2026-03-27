from __future__ import annotations

from sentinel_alpha.agents.data_source_expansion_agent import (
    DataSourceExpansionAgent,
    DataSourceExpansionRequest,
)


def test_data_source_expansion_agent_generates_valid_code_and_test() -> None:
    agent = DataSourceExpansionAgent()
    result = agent.build_integration_package(
        DataSourceExpansionRequest(
            interface_documentation="https://docs.example.com/market-data\nBase URL: https://api.example.com\nJSON API that accepts symbol and interval parameters. apikey= query parameter.",
            provider_name="Example Data",
            category="market_data",
            base_url="https://api.example.com",
            api_key_envs=["EXAMPLE_API_KEY"],
            docs_url="https://docs.example.com/market-data",
            sample_endpoint="quote",
            auth_style="query",
            response_format="json",
        )
    )

    assert result["provider_slug"] == "example_data"
    assert result["validation"]["module_syntax_ok"] is True
    assert result["validation"]["test_syntax_ok"] is True
    assert "EXAMPLE_API_KEY" in result["config_fragment"]
    assert 'docs_url = "https://docs.example.com/market-data"' in result["config_fragment"]
    assert "class ExampleDataSource" in result["generated_module_code"]
    assert "https://docs.example.com/market-data" in result["generated_module_code"]


def test_data_source_expansion_agent_accepts_docs_url_without_summary() -> None:
    agent = DataSourceExpansionAgent()
    result = agent.build_integration_package(
        DataSourceExpansionRequest(
            interface_documentation="https://docs.docs-only.example/reference",
            provider_name="Docs Only Feed",
            category="market_data",
            base_url="https://api.docs-only.example",
            api_key_envs=[],
            docs_summary=None,
            docs_url="https://docs.docs-only.example/reference",
        )
    )

    assert result["validation"]["ready_for_programmer_agent"] is True
    assert result["config_candidate"]["docs_url"] == "https://docs.docs-only.example/reference"
    assert "See provider docs at https://docs.docs-only.example/reference" in result["generated_module_code"]


def test_data_source_expansion_agent_generates_category_specific_methods() -> None:
    agent = DataSourceExpansionAgent()

    fundamentals = agent.build_integration_package(
        DataSourceExpansionRequest(
            interface_documentation="Financial statements and filing metadata.",
            provider_name="Sec Mirror",
            category="fundamentals",
            base_url="https://example.com/sec",
            api_key_envs=[],
            docs_summary="Financial statements and filing metadata.",
        )
    )
    options = agent.build_integration_package(
        DataSourceExpansionRequest(
            interface_documentation="Option chain endpoint.",
            provider_name="Options Feed",
            category="options",
            base_url="https://example.com/options",
            api_key_envs=["OPTIONS_KEY"],
            docs_summary="Option chain endpoint.",
        )
    )
    dark_pool = agent.build_integration_package(
        DataSourceExpansionRequest(
            interface_documentation="Dark pool volume endpoint.",
            provider_name="DarkPool Feed",
            category="dark_pool",
            base_url="https://example.com/darkpool",
            api_key_envs=["DARKPOOL_KEY"],
            docs_summary="Dark pool volume endpoint.",
        )
    )

    assert "def fetch_financials" in fundamentals["generated_module_code"]
    assert "def fetch_options" in options["generated_module_code"]
    assert "def fetch_dark_pool" in dark_pool["generated_module_code"]
    assert fundamentals["validation"]["ready_for_programmer_agent"] is True
    assert options["validation"]["ready_for_programmer_agent"] is True
    assert dark_pool["validation"]["ready_for_programmer_agent"] is True


def test_data_source_expansion_agent_can_infer_fields_from_minimal_input() -> None:
    agent = DataSourceExpansionAgent()
    result = agent.build_integration_package(
        DataSourceExpansionRequest(
            interface_documentation=(
                "https://docs.alphafeed.example/reference\n"
                "Base URL: https://api.alphafeed.example\n"
                "REST JSON quote and history API. Authorization header uses bearer token. "
                "Option chain endpoint available at /v1/options."
            ),
            api_key="sk_test_1234567890",
        )
    )

    assert result["provider_slug"] == "alphafeed_example"
    assert result["category"] == "options"
    assert result["inference"]["base_url"] == "https://api.alphafeed.example"
    assert result["inference"]["auth_style"] == "bearer"
    assert result["inference"]["response_format"] == "json"
    assert result["inference"]["api_key_supplied"] is True
    assert result["inference"]["api_key_preview"].startswith("sk_")
    assert "provider_name" in result["inference"]["inferred_fields"]
    assert result["validation"]["ready_for_programmer_agent"] is True


def test_data_source_expansion_agent_uses_structured_spec_to_generate_provider_specific_code() -> None:
    agent = DataSourceExpansionAgent()
    result = agent.build_integration_package(
        DataSourceExpansionRequest(
            interface_documentation="Provider doc excerpt",
            api_key="provider_key_123456",
            integration_spec={
                "provider_name": "Polygon Market Feed",
                "category": "market_data",
                "base_url": "https://api.polygon.example",
                "docs_url": "https://polygon.example/docs",
                "auth_style": "header",
                "auth_header_name": "X-API-Key",
                "auth_query_param": "",
                "response_format": "json",
                "sample_endpoint": "v3/reference/tickers",
                "quote_endpoint": "v2/last/trade/{symbol}",
                "history_endpoint": "v2/aggs/ticker/{symbol}/range/{interval}/{lookback}",
                "symbol_param": "ticker",
                "interval_param": "timespan",
                "lookback_param": "multiplier",
                "response_root_path": "results",
                "default_headers": {"Accept": "application/json"},
                "default_query_params": {"adjusted": "true"},
                "pagination_style": "cursor",
                "error_field_path": "error.message",
                "notes": ["Use ticker instead of symbol."],
                "analysis_generation_mode": "live_llm",
                "analysis_status": "live_llm_completed",
                "fallback_reason": None,
            },
        )
    )

    assert result["analysis"]["generation_mode"] == "live_llm"
    assert result["inference"]["quote_endpoint"] == "v2/last/trade/{symbol}"
    assert result["inference"]["symbol_param"] == "ticker"
    assert "X-API-Key" in result["generated_module_code"]
    assert "v2/last/trade/{symbol}" in result["generated_test_code"]
    assert result["config_candidate"]["structured_integration_spec"]["pagination_style"] == "cursor"
    assert result["validation"]["ready_for_programmer_agent"] is True
