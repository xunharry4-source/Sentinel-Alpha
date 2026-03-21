from __future__ import annotations

import ast
import re
from dataclasses import dataclass


@dataclass(slots=True)
class DataSourceExpansionRequest:
    provider_name: str
    category: str
    base_url: str
    api_key_env: str | None
    docs_summary: str | None = None
    docs_url: str | None = None
    sample_endpoint: str | None = None
    auth_style: str = "header"
    response_format: str = "json"


class DataSourceExpansionAgent:
    """Generates adapter code, tests, and config fragments for new data sources."""

    def build_integration_package(self, request: DataSourceExpansionRequest) -> dict:
        slug = self._slugify(request.provider_name)
        class_name = "".join(part.capitalize() for part in slug.split("_")) + "Source"
        category = request.category.lower().strip()
        target_module = f"src/sentinel_alpha/infra/generated_sources/{slug}.py"
        target_test = f"tests/generated/test_{slug}.py"

        code = self._build_module_code(request, slug, class_name)
        test_code = self._build_test_code(request, slug, class_name)
        config_fragment = self._build_config_fragment(request, slug)

        module_validation = self._validate_python(code)
        test_validation = self._validate_python(test_code)

        return {
            "provider_name": request.provider_name,
            "provider_slug": slug,
            "category": category,
            "target_module": target_module,
            "target_test": target_test,
            "config_fragment": config_fragment,
            "config_candidate": self._build_config_candidate(request, slug, target_module, target_test),
            "generated_module_code": code,
            "generated_test_code": test_code,
            "validation": {
                "module_syntax_ok": module_validation["ok"],
                "test_syntax_ok": test_validation["ok"],
                "module_error": module_validation["error"],
                "test_error": test_validation["error"],
                "ready_for_programmer_agent": module_validation["ok"] and test_validation["ok"],
            },
        }

    def _build_module_code(self, request: DataSourceExpansionRequest, slug: str, class_name: str) -> str:
        quote_method = self._category_method(request.category, "quote")
        history_method = self._category_method(request.category, "history")
        request_notes = self._request_notes(request).replace('"""', "'''")
        docs_url_line = f"    Docs URL: {request.docs_url}\\n" if request.docs_url else ""
        api_key_line = (
            f'        self.api_key = os.getenv("{request.api_key_env}", "")\n'
            if request.api_key_env
            else '        self.api_key = ""\n'
        )
        auth_injection = self._auth_injection(request.auth_style)
        return (
            "from __future__ import annotations\n\n"
            "import json\n"
            "import os\n"
            "from urllib.parse import urlencode\n"
            "from urllib.request import Request, urlopen\n\n\n"
            f"class {class_name}:\n"
            f'    """Generated adapter for {request.provider_name}.\\n\\n'
            f"    Docs summary: {request_notes}\\n"
            f"{docs_url_line}"
            '    """\n\n'
            "    def __init__(self, base_url: str | None = None, timeout_seconds: int = 10) -> None:\n"
            f'        self.base_url = (base_url or "{request.base_url}").rstrip("/")\n'
            f"{api_key_line}"
            "        self.timeout_seconds = timeout_seconds\n\n"
            "    def _request_json(self, path: str, params: dict[str, str] | None = None) -> dict:\n"
            "        params = dict(params or {})\n"
            f"{auth_injection}"
            '        url = f"{self.base_url}/{path.lstrip(\'/\')}"\n'
            "        if params:\n"
            '            url = f"{url}?{urlencode(params)}"\n'
            '        request = Request(url, headers={"User-Agent": "Sentinel-Alpha/0.1"})\n'
            "        with urlopen(request, timeout=self.timeout_seconds) as response:\n"
            '            payload = response.read().decode("utf-8")\n'
            "        return json.loads(payload)\n\n"
            f"    def {quote_method}(self, symbol: str) -> dict:\n"
            "        return self._request_json(\n"
            f'            "{request.sample_endpoint or "quote"}",\n'
            '            {"symbol": symbol},\n'
            "        )\n\n"
            f"    def {history_method}(self, symbol: str, interval: str = \"1d\", lookback: str = \"6mo\") -> dict:\n"
            "        return self._request_json(\n"
            f'            "{request.sample_endpoint or "history"}",\n'
            '            {"symbol": symbol, "interval": interval, "lookback": lookback},\n'
            "        )\n"
        )

    def _build_test_code(self, request: DataSourceExpansionRequest, slug: str, class_name: str) -> str:
        return (
            "from __future__ import annotations\n\n"
            f"from sentinel_alpha.infra.generated_sources.{slug} import {class_name}\n\n\n"
            f"def test_{slug}_adapter_builds_query_paths(monkeypatch) -> None:\n"
            f"    adapter = {class_name}(base_url=\"{request.base_url}\")\n"
            "    calls = []\n\n"
            "    def fake_request(path: str, params: dict[str, str] | None = None) -> dict:\n"
            "        calls.append((path, params or {}))\n"
            "        return {\"ok\": True, \"path\": path, \"params\": params or {}}\n\n"
            "    adapter._request_json = fake_request  # type: ignore[method-assign]\n"
            f"    adapter.{self._category_method(request.category, 'quote')}(\"AAPL\")\n"
            f"    adapter.{self._category_method(request.category, 'history')}(\"AAPL\", interval=\"1d\", lookback=\"1mo\")\n\n"
            "    assert len(calls) == 2\n"
            "    assert calls[0][1][\"symbol\"] == \"AAPL\"\n"
            "    assert calls[1][1][\"interval\"] == \"1d\"\n"
        )

    def _build_config_fragment(self, request: DataSourceExpansionRequest, slug: str) -> str:
        api_key_line = f'api_key_env = "{request.api_key_env}"\n' if request.api_key_env else 'api_key_env = ""\n'
        docs_url_line = f'docs_url = "{request.docs_url}"\n' if request.docs_url else ""
        return (
            f"[generated_sources.providers.{slug}]\n"
            "enabled = true\n"
            f"{api_key_line}"
            f'base_url = "{request.base_url}"\n'
            f"{docs_url_line}"
            f'category = "{request.category}"\n'
            f'auth_style = "{request.auth_style}"\n'
            f'response_format = "{request.response_format}"\n'
        )

    def _build_config_candidate(
        self,
        request: DataSourceExpansionRequest,
        slug: str,
        target_module: str,
        target_test: str,
    ) -> dict:
        provider_config = {
            "enabled": True,
            "api_key_env": request.api_key_env or "",
            "base_url": request.base_url,
            "docs_url": request.docs_url or "",
            "auth_style": request.auth_style,
            "response_format": request.response_format,
        }
        return {
            "category": request.category,
            "provider_name": slug,
            "display_name": request.provider_name,
            "docs_summary": self._request_notes(request),
            "docs_url": request.docs_url,
            "provider_config": provider_config,
            "target_module": target_module,
            "target_test": target_test,
            "generated_sources": {
                "providers": {
                    slug: {
                        **provider_config,
                        "category": request.category,
                        "target_module": target_module,
                        "target_test": target_test,
                    }
                }
            },
        }

    def _validate_python(self, source: str) -> dict[str, str | bool | None]:
        try:
            ast.parse(source)
            return {"ok": True, "error": None}
        except SyntaxError as exc:
            return {"ok": False, "error": f"{exc.msg} at line {exc.lineno}"}

    def _slugify(self, value: str) -> str:
        lowered = value.strip().lower()
        lowered = re.sub(r"[^a-z0-9]+", "_", lowered)
        return lowered.strip("_") or "custom_source"

    def _category_method(self, category: str, mode: str) -> str:
        normalized = category.lower().strip()
        if normalized in {"fundamentals", "financials"}:
            return "fetch_financials" if mode == "quote" else "fetch_history"
        if normalized in {"options", "options_data"}:
            return "fetch_options" if mode == "quote" else "fetch_option_history"
        if normalized in {"dark_pool", "darkpool"}:
            return "fetch_dark_pool" if mode == "quote" else "fetch_dark_pool_history"
        return "fetch_quote" if mode == "quote" else "fetch_history"

    def _auth_injection(self, auth_style: str) -> str:
        normalized = auth_style.lower().strip()
        if normalized == "query":
            return (
                '        if self.api_key:\n'
                '            params["apikey"] = self.api_key\n'
            )
        if normalized == "bearer":
            return (
                "        # Replace with bearer-token header injection if the provider requires it.\n"
            )
        return (
            "        # Replace with provider-specific auth/header handling if the docs require it.\n"
        )

    def _request_notes(self, request: DataSourceExpansionRequest) -> str:
        summary = (request.docs_summary or "").strip()
        if summary:
            return summary
        if request.docs_url:
            return f"See provider docs at {request.docs_url}"
        return "No docs summary provided."
