from __future__ import annotations

from sentinel_alpha.agents.data_source_expansion_agent import (
    DataSourceExpansionAgent,
    DataSourceExpansionRequest,
)


def test_data_source_expansion_agent_generates_valid_code_and_test() -> None:
    agent = DataSourceExpansionAgent()
    result = agent.build_integration_package(
        DataSourceExpansionRequest(
            provider_name="Example Data",
            category="market_data",
            base_url="https://api.example.com",
            api_key_envs=["EXAMPLE_API_KEY"],
            docs_summary="JSON API that accepts symbol and interval parameters.",
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
            provider_name="Sec Mirror",
            category="fundamentals",
            base_url="https://example.com/sec",
            api_key_envs=[],
            docs_summary="Financial statements and filing metadata.",
        )
    )
    options = agent.build_integration_package(
        DataSourceExpansionRequest(
            provider_name="Options Feed",
            category="options",
            base_url="https://example.com/options",
            api_key_envs=["OPTIONS_KEY"],
            docs_summary="Option chain endpoint.",
        )
    )
    dark_pool = agent.build_integration_package(
        DataSourceExpansionRequest(
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
