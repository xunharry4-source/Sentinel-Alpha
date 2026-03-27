from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(slots=True)
class DataSourceExpansionRequest:
    interface_documentation: str
    api_key: str | None = None
    provider_name: str | None = None
    category: str | None = None
    base_url: str | None = None
    api_key_envs: list[str] | None = None
    docs_summary: str | None = None
    docs_url: str | None = None
    sample_endpoint: str | None = None
    auth_style: str | None = None
    response_format: str | None = None
    integration_spec: dict | None = None


class DataSourceExpansionAgent:
    """Generates adapter code, tests, and config fragments for new data sources."""

    def _normalized_api_key_envs(self, envs: list[str] | None) -> list[str]:
        return [str(item).strip() for item in (envs or []) if str(item).strip()]

    def build_integration_package(self, request: DataSourceExpansionRequest) -> dict:
        resolved = self._resolve_request(request)
        slug = resolved["provider_slug"]
        class_name = "".join(part.capitalize() for part in slug.split("_")) + "Source"
        category = resolved["category"]
        target_module = f"src/sentinel_alpha/infra/generated_sources/{slug}.py"
        target_test = f"tests/generated/test_{slug}.py"

        code = self._build_module_code(resolved, slug, class_name)
        test_code = self._build_test_code(resolved, slug, class_name)
        config_fragment = self._build_config_fragment(resolved, slug)

        module_validation = self._validate_python(code)
        test_validation = self._validate_python(test_code)
        module_smoke = self._smoke_test_generated_module(
            code,
            class_name=class_name,
            quote_method=self._category_method(category, "quote"),
            history_method=self._category_method(category, "history"),
        )

        return {
            "provider_name": resolved["provider_name"],
            "provider_slug": slug,
            "category": category,
            "provider": slug,
            "status": "ready" if module_validation["ok"] and test_validation["ok"] else "warning",
            "summary": f"Auto-generated adapter package for {resolved['provider_name']} from minimal docs + API key input.",
            "target_module": target_module,
            "target_test": target_test,
            "config_fragment": config_fragment,
            "config_candidate": self._build_config_candidate(resolved, slug, target_module, target_test),
            "generated_module_code": code,
            "generated_test_code": test_code,
            "interface_documentation_summary": resolved["docs_summary"],
            "analysis": {
                "generation_mode": resolved["analysis_generation_mode"],
                "analysis_status": resolved["analysis_status"],
                "fallback_reason": resolved["fallback_reason"],
                "structured_integration_spec": resolved["structured_integration_spec"],
            },
            "inference": {
                "inferred_fields": resolved["inferred_fields"],
                "docs_url": resolved["docs_url"],
                "base_url": resolved["base_url"],
                "provider_name": resolved["provider_name"],
                "category": resolved["category"],
                "auth_style": resolved["auth_style"],
                "response_format": resolved["response_format"],
                "sample_endpoint": resolved["sample_endpoint"],
                "api_key_envs": resolved["api_key_envs"],
                "api_key_supplied": resolved["api_key_supplied"],
                "api_key_preview": resolved["api_key_preview"],
                "quote_endpoint": resolved["quote_endpoint"],
                "history_endpoint": resolved["history_endpoint"],
                "symbol_param": resolved["symbol_param"],
                "interval_param": resolved["interval_param"],
                "lookback_param": resolved["lookback_param"],
                "response_root_path": resolved["response_root_path"],
                "default_headers": resolved["default_headers"],
                "default_query_params": resolved["default_query_params"],
            },
            "validation": {
                "module_syntax_ok": module_validation["ok"],
                "test_syntax_ok": test_validation["ok"],
                "module_smoke_ok": module_smoke["ok"],
                "module_error": module_validation["error"],
                "test_error": test_validation["error"],
                "module_smoke_error": module_smoke["error"],
                "request_inference_ok": True,
                "ready_for_programmer_agent": module_validation["ok"] and test_validation["ok"] and module_smoke["ok"],
            },
        }

    def _build_module_code(self, request: dict, slug: str, class_name: str) -> str:
        quote_method = self._category_method(request["category"], "quote")
        history_method = self._category_method(request["category"], "history")
        request_notes = str(request["docs_summary"]).replace('"""', "'''")
        docs_url_line = f"    Docs URL: {request['docs_url']}\\n" if request["docs_url"] else ""
        envs = self._normalized_api_key_envs(request["api_key_envs"])
        default_headers = dict(request["default_headers"] or {})
        default_query_params = dict(request["default_query_params"] or {})
        api_key_lines = (
            f"        self.api_keys = [os.getenv(name, \"\") for name in {envs!r}]\n"
            "        self.api_key = next((value for value in self.api_keys if value), \"\")\n"
        )
        auth_injection = self._auth_injection(
            request["auth_style"],
            auth_header_name=request["auth_header_name"],
            auth_query_param=request["auth_query_param"],
        )
        response_root_path = request["response_root_path"] or ""
        error_field_path = request["error_field_path"] or ""
        spec_notes = request["spec_notes"] or []
        return (
            "from __future__ import annotations\n\n"
            "import json\n"
            "import os\n"
            "from urllib.parse import urlencode\n"
            "from urllib.request import Request, urlopen\n\n\n"
            f"class {class_name}:\n"
            f'    """Generated adapter for {request["provider_name"]}.\\n\\n'
            f"    Docs summary: {request_notes}\\n"
            f"{docs_url_line}"
            '    """\n\n'
            "    def __init__(self, base_url: str | None = None, timeout_seconds: int = 10) -> None:\n"
            f'        self.base_url = (base_url or "{request["base_url"]}").rstrip("/")\n'
            f"{api_key_lines}"
            f"        self.default_headers = {default_headers!r}\n"
            f"        self.default_query_params = {default_query_params!r}\n"
            "        self.timeout_seconds = timeout_seconds\n\n"
            "    def _extract_path(self, payload: object, dotted_path: str) -> object:\n"
            "        value = payload\n"
            "        for part in [item for item in dotted_path.split('.') if item]:\n"
            "            if isinstance(value, dict):\n"
            "                value = value.get(part)\n"
            "            else:\n"
            "                return payload\n"
            "        return payload if value is None else value\n\n"
            "    def _request_json(self, path: str, params: dict[str, str] | None = None) -> dict:\n"
            "        params = {**self.default_query_params, **dict(params or {})}\n"
            "        headers = {\"User-Agent\": \"Sentinel-Alpha/0.1\", **self.default_headers}\n"
            f"{auth_injection}"
            '        url = f"{self.base_url}/{path.lstrip(\'/\')}"\n'
            "        if params:\n"
            '            url = f"{url}?{urlencode(params)}"\n'
            "        request = Request(url, headers=headers)\n"
            "        with urlopen(request, timeout=self.timeout_seconds) as response:\n"
            '            payload = response.read().decode("utf-8")\n'
            "        decoded = json.loads(payload)\n"
            f"        if {error_field_path!r}:\n"
            f"            maybe_error = self._extract_path(decoded, {error_field_path!r})\n"
            "            if maybe_error not in (None, '', [], {}):\n"
            "                raise RuntimeError(f'Provider returned error payload: {maybe_error}')\n"
            f"        if {response_root_path!r}:\n"
            f"            extracted = self._extract_path(decoded, {response_root_path!r})\n"
            "            return extracted if isinstance(extracted, dict) else {\"data\": extracted}\n"
            "        return decoded\n\n"
            f"    def {quote_method}(self, symbol: str) -> dict:\n"
            "        return self._request_json(\n"
            f'            "{request["quote_endpoint"] or request["sample_endpoint"] or "quote"}",\n'
            f'            {{"{request["symbol_param"]}": symbol}},\n'
            "        )\n\n"
            f"    def {history_method}(self, symbol: str, interval: str = \"1d\", lookback: str = \"6mo\") -> dict:\n"
            "        return self._request_json(\n"
            f'            "{request["history_endpoint"] or request["sample_endpoint"] or "history"}",\n'
            f'            {{"{request["symbol_param"]}": symbol, "{request["interval_param"]}": interval, "{request["lookback_param"]}": lookback}},\n'
            "        )\n"
            + (
                "\n"
                "SPEC_NOTES = "
                f"{spec_notes!r}\n"
                if spec_notes
                else ""
            )
        )

    def _build_test_code(self, request: dict, slug: str, class_name: str) -> str:
        quote_endpoint = request["quote_endpoint"] or request["sample_endpoint"] or "quote"
        history_endpoint = request["history_endpoint"] or request["sample_endpoint"] or "history"
        return (
            "from __future__ import annotations\n\n"
            f"from sentinel_alpha.infra.generated_sources.{slug} import {class_name}\n\n\n"
            f"def test_{slug}_adapter_builds_query_paths(monkeypatch) -> None:\n"
            f"    adapter = {class_name}(base_url=\"{request['base_url']}\")\n"
            "    calls = []\n\n"
            "    def fake_request(path: str, params: dict[str, str] | None = None) -> dict:\n"
            "        calls.append((path, params or {}))\n"
            "        return {\"ok\": True, \"path\": path, \"params\": params or {}}\n\n"
            "    adapter._request_json = fake_request  # type: ignore[method-assign]\n"
            f"    adapter.{self._category_method(request['category'], 'quote')}(\"AAPL\")\n"
            f"    adapter.{self._category_method(request['category'], 'history')}(\"AAPL\", interval=\"1d\", lookback=\"1mo\")\n\n"
            "    assert len(calls) == 2\n"
            f"    assert calls[0][0] == {quote_endpoint!r}\n"
            f"    assert calls[1][0] == {history_endpoint!r}\n"
            f"    assert calls[0][1][{request['symbol_param']!r}] == \"AAPL\"\n"
            f"    assert calls[1][1][{request['interval_param']!r}] == \"1d\"\n"
        )

    def _build_config_fragment(self, request: dict, slug: str) -> str:
        envs = self._normalized_api_key_envs(request["api_key_envs"])
        api_key_line = f"api_key_envs = {envs!r}\n"
        docs_url_line = f'docs_url = "{request["docs_url"]}"\n' if request["docs_url"] else ""
        return (
            f"[generated_sources.providers.{slug}]\n"
            "enabled = true\n"
            f"{api_key_line}"
            f'base_url = "{request["base_url"]}"\n'
            f"{docs_url_line}"
            f'category = "{request["category"]}"\n'
            f'auth_style = "{request["auth_style"]}"\n'
            f'response_format = "{request["response_format"]}"\n'
        )

    def _build_config_candidate(
        self,
        request: dict,
        slug: str,
        target_module: str,
        target_test: str,
    ) -> dict:
        provider_config = {
            "enabled": True,
            "api_key_envs": self._normalized_api_key_envs(request["api_key_envs"]),
            "base_url": request["base_url"],
            "docs_url": request["docs_url"] or "",
            "auth_style": request["auth_style"],
            "response_format": request["response_format"],
            "quote_endpoint": request["quote_endpoint"],
            "history_endpoint": request["history_endpoint"],
            "symbol_param": request["symbol_param"],
            "interval_param": request["interval_param"],
            "lookback_param": request["lookback_param"],
            "response_root_path": request["response_root_path"],
            "error_field_path": request["error_field_path"],
            "default_headers": request["default_headers"],
            "default_query_params": request["default_query_params"],
        }
        return {
            "category": request["category"],
            "provider_name": slug,
            "display_name": request["provider_name"],
            "docs_summary": request["docs_summary"],
            "docs_url": request["docs_url"],
            "credential_binding": {
                "api_key_envs": self._normalized_api_key_envs(request["api_key_envs"]),
                "api_key_supplied": request["api_key_supplied"],
                "api_key_preview": request["api_key_preview"],
            },
            "structured_integration_spec": request["structured_integration_spec"],
            "provider_config": provider_config,
            "target_module": target_module,
            "target_test": target_test,
            "generated_sources": {
                "providers": {
                    slug: {
                        **provider_config,
                        "category": request["category"],
                        "target_module": target_module,
                        "target_test": target_test,
                    }
                }
            },
        }

    def _resolve_request(self, request: DataSourceExpansionRequest) -> dict:
        docs_text = (request.interface_documentation or request.docs_summary or request.docs_url or "").strip()
        docs_url = request.docs_url or self._extract_first_url(docs_text)
        spec = self._normalize_integration_spec(request.integration_spec or {})
        provider_name = request.provider_name or str(spec.get("provider_name") or "") or self._infer_provider_name(docs_url, request.api_key_envs)
        slug = self._slugify(provider_name)
        category = str(request.category or spec.get("category") or self._infer_category(docs_text)).lower().strip()
        base_url = request.base_url or str(spec.get("base_url") or "") or self._infer_base_url(docs_text, docs_url)
        auth_style = str(request.auth_style or spec.get("auth_style") or self._infer_auth_style(docs_text)).lower().strip()
        response_format = str(request.response_format or spec.get("response_format") or self._infer_response_format(docs_text)).lower().strip()
        sample_endpoint = request.sample_endpoint or str(spec.get("sample_endpoint") or "") or self._infer_sample_endpoint(docs_text, category, docs_url)
        api_key_envs = self._normalized_api_key_envs(request.api_key_envs) or [self._default_api_key_env(slug)]
        docs_summary = self._request_notes(request, docs_text, docs_url)
        quote_endpoint = str(spec.get("quote_endpoint") or sample_endpoint or "quote").strip().strip("/")
        history_endpoint = str(spec.get("history_endpoint") or self._infer_history_endpoint(docs_text, category, sample_endpoint)).strip().strip("/")
        symbol_param = str(spec.get("symbol_param") or "symbol").strip() or "symbol"
        interval_param = str(spec.get("interval_param") or "interval").strip() or "interval"
        lookback_param = str(spec.get("lookback_param") or "lookback").strip() or "lookback"
        response_root_path = str(spec.get("response_root_path") or "").strip()
        error_field_path = str(spec.get("error_field_path") or "").strip()
        default_headers = self._normalize_string_mapping(spec.get("default_headers"))
        default_query_params = self._normalize_string_mapping(spec.get("default_query_params"))
        auth_header_name = str(spec.get("auth_header_name") or "Authorization").strip() or "Authorization"
        auth_query_param = str(spec.get("auth_query_param") or "apikey").strip() or "apikey"
        pagination_style = str(spec.get("pagination_style") or "none").strip() or "none"
        spec_notes = self._normalize_string_list(spec.get("notes"))
        structured_integration_spec = {
            "provider_name": provider_name,
            "category": category,
            "base_url": base_url,
            "docs_url": docs_url,
            "auth_style": auth_style,
            "auth_header_name": auth_header_name,
            "auth_query_param": auth_query_param,
            "response_format": response_format,
            "sample_endpoint": sample_endpoint,
            "quote_endpoint": quote_endpoint,
            "history_endpoint": history_endpoint,
            "symbol_param": symbol_param,
            "interval_param": interval_param,
            "lookback_param": lookback_param,
            "response_root_path": response_root_path,
            "error_field_path": error_field_path,
            "default_headers": default_headers,
            "default_query_params": default_query_params,
            "pagination_style": pagination_style,
            "notes": spec_notes,
        }
        inferred_fields = []
        if request.provider_name is None and not spec.get("provider_name"):
            inferred_fields.append("provider_name")
        if request.category is None and not spec.get("category"):
            inferred_fields.append("category")
        if request.base_url is None and not spec.get("base_url"):
            inferred_fields.append("base_url")
        if request.auth_style is None and not spec.get("auth_style"):
            inferred_fields.append("auth_style")
        if request.response_format is None and not spec.get("response_format"):
            inferred_fields.append("response_format")
        if request.sample_endpoint is None and not spec.get("sample_endpoint"):
            inferred_fields.append("sample_endpoint")
        if not self._normalized_api_key_envs(request.api_key_envs):
            inferred_fields.append("api_key_envs")
        if request.docs_url is None and docs_url:
            inferred_fields.append("docs_url")
        if not spec.get("quote_endpoint"):
            inferred_fields.append("quote_endpoint")
        if not spec.get("history_endpoint"):
            inferred_fields.append("history_endpoint")
        return {
            "provider_name": provider_name,
            "provider_slug": slug,
            "category": category,
            "base_url": base_url,
            "api_key_envs": api_key_envs,
            "docs_summary": docs_summary,
            "docs_url": docs_url,
            "sample_endpoint": sample_endpoint,
            "auth_style": auth_style,
            "response_format": response_format,
            "interface_documentation": docs_text,
            "api_key_supplied": bool((request.api_key or "").strip()),
            "api_key_preview": self._mask_api_key(request.api_key),
            "inferred_fields": inferred_fields,
            "quote_endpoint": quote_endpoint,
            "history_endpoint": history_endpoint,
            "symbol_param": symbol_param,
            "interval_param": interval_param,
            "lookback_param": lookback_param,
            "response_root_path": response_root_path,
            "error_field_path": error_field_path,
            "default_headers": default_headers,
            "default_query_params": default_query_params,
            "auth_header_name": auth_header_name,
            "auth_query_param": auth_query_param,
            "pagination_style": pagination_style,
            "spec_notes": spec_notes,
            "structured_integration_spec": structured_integration_spec,
            "analysis_generation_mode": str(spec.get("analysis_generation_mode") or "rule_based"),
            "analysis_status": str(spec.get("analysis_status") or "heuristic_completed"),
            "fallback_reason": spec.get("fallback_reason"),
        }

    def _validate_python(self, source: str) -> dict[str, str | bool | None]:
        try:
            ast.parse(source)
            return {"ok": True, "error": None}
        except SyntaxError as exc:
            return {"ok": False, "error": f"{exc.msg} at line {exc.lineno}"}

    def _smoke_test_generated_module(self, source: str, *, class_name: str, quote_method: str, history_method: str) -> dict[str, str | bool | None]:
        namespace: dict[str, object] = {}
        try:
            compiled = compile(source, "<generated_data_source>", "exec")
            exec(compiled, namespace, namespace)
            generated_class = namespace.get(class_name)
            if generated_class is None:
                return {"ok": False, "error": f"Missing generated class: {class_name}"}
            if not hasattr(generated_class, quote_method):
                return {"ok": False, "error": f"Missing quote method: {quote_method}"}
            if not hasattr(generated_class, history_method):
                return {"ok": False, "error": f"Missing history method: {history_method}"}
            return {"ok": True, "error": None}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

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

    def _auth_injection(self, auth_style: str, *, auth_header_name: str, auth_query_param: str) -> str:
        normalized = auth_style.lower().strip()
        if normalized == "query":
            return (
                '        if self.api_key:\n'
                f'            params[{auth_query_param!r}] = self.api_key\n'
            )
        if normalized == "bearer":
            return (
                '        if self.api_key:\n'
                f'            headers[{auth_header_name!r}] = f"Bearer {{self.api_key}}"\n'
            )
        return (
            '        if self.api_key:\n'
            f'            headers[{auth_header_name!r}] = self.api_key\n'
        )

    def _request_notes(self, request: DataSourceExpansionRequest, docs_text: str, docs_url: str | None) -> str:
        summary = (request.docs_summary or "").strip()
        if summary:
            return summary
        normalized = " ".join(docs_text.split())
        if normalized and normalized != (docs_url or ""):
            return normalized[:240]
        if docs_url:
            return f"See provider docs at {docs_url}"
        return "No docs summary provided."

    def _extract_first_url(self, docs_text: str) -> str | None:
        match = re.search(r"https?://[^\s)>\"]+", docs_text or "")
        return match.group(0) if match else None

    def _infer_provider_name(self, docs_url: str | None, api_key_envs: list[str] | None) -> str:
        if docs_url:
            host = urlparse(docs_url).netloc.split(":")[0]
            labels = [item for item in host.split(".") if item and item not in {"www", "docs", "api"}]
            if labels:
                return " ".join(part.replace("-", " ").replace("_", " ").title() for part in labels[:2])
        envs = self._normalized_api_key_envs(api_key_envs)
        if envs:
            return envs[0].replace("_API_KEY", "").replace("_KEY", "").replace("_", " ").title()
        return "Custom Source"

    def _infer_category(self, docs_text: str) -> str:
        text = (docs_text or "").lower()
        if "dark pool" in text or "dark_pool" in text or "off-exchange" in text:
            return "dark_pool"
        if "option" in text or "options chain" in text:
            return "options"
        if "fundamental" in text or "financial statement" in text or "balance sheet" in text or "income statement" in text:
            return "fundamentals"
        return "market_data"

    def _infer_base_url(self, docs_text: str, docs_url: str | None) -> str:
        explicit = re.search(r"(?:base\s*url|base_url)\s*[:=]\s*(https?://[^\s]+)", docs_text or "", flags=re.IGNORECASE)
        if explicit:
            return explicit.group(1).rstrip("/")
        if docs_url:
            parsed = urlparse(docs_url)
            return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        return "https://api.example.com"

    def _infer_auth_style(self, docs_text: str) -> str:
        text = (docs_text or "").lower()
        if "bearer" in text or "authorization:" in text or "authorization header" in text:
            return "bearer"
        if "query parameter" in text or "apikey=" in text or "api_key=" in text:
            return "query"
        return "header"

    def _infer_response_format(self, docs_text: str) -> str:
        text = (docs_text or "").lower()
        if "xml" in text:
            return "xml"
        if "csv" in text:
            return "csv"
        return "json"

    def _infer_sample_endpoint(self, docs_text: str, category: str, docs_url: str | None) -> str:
        text = docs_text or ""
        explicit = re.search(r"(/[-a-zA-Z0-9_/{}/]+)", text)
        if explicit:
            return explicit.group(1).strip("/")
        if docs_url:
            path = urlparse(docs_url).path.strip("/")
            if path:
                return path.split("/")[-1]
        if category == "fundamentals":
            return "financials"
        if category == "options":
            return "options"
        if category == "dark_pool":
            return "dark-pool"
        return "quote"

    def _infer_history_endpoint(self, docs_text: str, category: str, sample_endpoint: str) -> str:
        text = docs_text or ""
        explicit = re.search(r"(?:history|ohlcv|candles?|bars?|eod|timeseries|time[- ]series)\s*(?:endpoint)?\s*[:=]?\s*(/[-a-zA-Z0-9_/{}/]+)", text, flags=re.IGNORECASE)
        if explicit:
            return explicit.group(1).strip("/")
        if category == "fundamentals":
            return sample_endpoint or "financials/history"
        if category == "options":
            return "options/history"
        if category == "dark_pool":
            return "dark-pool/history"
        return "history"

    def _default_api_key_env(self, slug: str) -> str:
        return f"{slug.upper()}_API_KEY"

    def _mask_api_key(self, api_key: str | None) -> str | None:
        raw = (api_key or "").strip()
        if not raw:
            return None
        if len(raw) <= 8:
            return "*" * len(raw)
        return f"{raw[:3]}***{raw[-3:]}"

    def _normalize_string_mapping(self, value: object) -> dict[str, str]:
        if not isinstance(value, dict):
            return {}
        result: dict[str, str] = {}
        for key, item in value.items():
            key_text = str(key).strip()
            item_text = str(item).strip()
            if key_text:
                result[key_text] = item_text
        return result

    def _normalize_string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _normalize_integration_spec(self, spec: dict) -> dict:
        normalized = dict(spec or {})
        normalized["default_headers"] = self._normalize_string_mapping(normalized.get("default_headers"))
        normalized["default_query_params"] = self._normalize_string_mapping(normalized.get("default_query_params"))
        normalized["notes"] = self._normalize_string_list(normalized.get("notes"))
        return normalized

    def analyze_request(self, request: DataSourceExpansionRequest) -> dict:
        return self._resolve_request(request)
