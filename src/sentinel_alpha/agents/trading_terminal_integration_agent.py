from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from types import MethodType
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


@dataclass(slots=True)
class TradingTerminalIntegrationRequest:
    interface_documentation: str
    api_key: str | None = None
    terminal_name: str | None = None
    terminal_type: str | None = None
    official_docs_url: str | None = None
    docs_search_url: str | None = None
    api_base_url: str | None = None
    api_key_envs: list[str] | None = None
    auth_style: str | None = None
    order_endpoint: str | None = None
    cancel_endpoint: str | None = None
    order_status_endpoint: str | None = None
    positions_endpoint: str | None = None
    balances_endpoint: str | None = None
    trade_records_endpoint: str | None = None
    docs_summary: str | None = None
    user_notes: str | None = None
    response_field_map: dict[str, str] | None = None
    integration_spec: dict | None = None


class TradingTerminalIntegrationAgent:
    """Generates trading-terminal adapter code, tests, and readiness summaries."""

    REQUIRED_CAPABILITIES = ("place_order", "order_status", "positions", "balances")
    OPTIONAL_CAPABILITIES = ("cancel_order", "trade_records")

    def _normalized_api_key_envs(self, envs: list[str] | None) -> list[str]:
        return [str(item).strip() for item in (envs or []) if str(item).strip()]

    def analyze_request(self, request: TradingTerminalIntegrationRequest) -> dict:
        return self._resolve_request(request)

    def build_terminal_package(self, request: TradingTerminalIntegrationRequest) -> dict:
        resolved = self._resolve_request(request)
        slug = resolved["terminal_slug"]
        class_name = "".join(part.capitalize() for part in slug.split("_")) + "TerminalAdapter"
        target_module = f"src/sentinel_alpha/infra/generated_terminals/{slug}.py"
        target_test = f"tests/generated/test_terminal_{slug}.py"
        module_code = self._build_module_code(resolved, slug, class_name)
        test_code = self._build_test_code(resolved, slug, class_name)
        config_candidate = self._build_config_candidate(resolved, slug, target_module, target_test)
        readiness = self._build_integration_readiness_summary(resolved)
        module_validation = self._validate_python(module_code)
        test_validation = self._validate_python(test_code)
        module_smoke = self._smoke_test_generated_module(module_code, class_name)
        return {
            "terminal_name": resolved["terminal_name"],
            "terminal_slug": slug,
            "class_name": class_name,
            "terminal_type": resolved["terminal_type"],
            "official_docs_url": resolved["official_docs_url"],
            "docs_search_url": resolved["docs_search_url"],
            "docs_context": resolved["docs_context"],
            "target_module": target_module,
            "target_test": target_test,
            "generated_module_code": module_code,
            "generated_test_code": test_code,
            "config_candidate": config_candidate,
            "integration_readiness_summary": readiness,
            "exchange_support_summary": self._build_exchange_support_summary(resolved),
            "analysis": {
                "generation_mode": resolved["analysis_generation_mode"],
                "analysis_status": resolved["analysis_status"],
                "fallback_reason": resolved["fallback_reason"],
                "structured_integration_spec": resolved["structured_integration_spec"],
            },
            "inference": {
                "terminal_name": resolved["terminal_name"],
                "terminal_type": resolved["terminal_type"],
                "api_base_url": resolved["api_base_url"],
                "auth_style": resolved["auth_style"],
                "docs_summary": resolved["docs_summary"],
                "official_docs_url": resolved["official_docs_url"],
                "api_key_envs": resolved["api_key_envs"],
                "api_key_supplied": resolved["api_key_supplied"],
                "api_key_preview": resolved["api_key_preview"],
                "capabilities": resolved["capabilities"],
                "response_field_map": resolved["response_field_map"],
            },
            "validation": {
                "module_syntax_ok": module_validation["ok"],
                "test_syntax_ok": test_validation["ok"],
                "module_smoke_ok": module_smoke["ok"],
                "docs_fetch_ok": resolved["docs_context"]["docs_fetch_ok"],
                "module_error": module_validation["error"],
                "test_error": test_validation["error"],
                "module_smoke_error": module_smoke["error"],
                "ready_for_programmer_agent": module_validation["ok"] and test_validation["ok"] and module_smoke["ok"],
            },
        }

    def run_smoke_test(self, package: dict) -> dict:
        module_code = package.get("generated_module_code") or ""
        class_name = package.get("class_name") or ""
        if not module_code or not class_name:
            return {"status": "error", "summary": "Missing generated module code or class name.", "checks": [], "calls": []}
        namespace: dict[str, object] = {}
        exec(compile(module_code, f"<generated_terminal:{package.get('terminal_slug', 'unknown')}>", "exec"), namespace)
        adapter_cls = namespace.get(class_name)
        if adapter_cls is None:
            return {"status": "error", "summary": f"Generated class {class_name} not found.", "checks": [], "calls": []}

        provider_config = (package.get("config_candidate") or {}).get("provider_config") or {}
        capabilities = provider_config.get("capabilities") or {}
        response_field_map = self._merged_response_field_map(provider_config.get("response_field_map"))
        adapter = adapter_cls(base_url=provider_config.get("base_url"))  # type: ignore[misc]
        calls: list[dict] = []

        def fake_request_json(self_obj, method: str, path: str, params: dict | None = None, payload: dict | None = None) -> dict:
            calls.append({"method": method, "path": path, "params": dict(params or {}), "payload": dict(payload or {})})
            response = {"ok": True, "path": path, "method": method, "params": dict(params or {}), "payload": dict(payload or {})}
            if path == (capabilities.get("positions") or {}).get("endpoint"):
                response[response_field_map["positions_root"]] = [
                    {
                        response_field_map["position_symbol"]: "AAPL",
                        response_field_map["position_quantity"]: 100,
                    }
                ]
            elif path == (capabilities.get("balances") or {}).get("endpoint"):
                response[response_field_map["balances_root"]] = {
                    response_field_map["balance_cash"]: 100000.0,
                    response_field_map["balance_buying_power"]: 180000.0,
                }
            elif path == (capabilities.get("order_status") or {}).get("endpoint"):
                response[response_field_map["order_status_root"]] = {
                    response_field_map["order_status_id"]: (params or {}).get("order_id", "ORD-1"),
                    response_field_map["order_status_state"]: "accepted",
                }
            elif path == (capabilities.get("trade_records") or {}).get("endpoint"):
                response[response_field_map["trade_records_root"]] = [
                    {
                        response_field_map["trade_record_id"]: "TR-1",
                        response_field_map["trade_record_symbol"]: "AAPL",
                        response_field_map["trade_record_side"]: "buy",
                        response_field_map["trade_record_quantity"]: 100,
                    }
                ]
            return response

        adapter._request_json = MethodType(fake_request_json, adapter)  # type: ignore[attr-defined]

        checks: list[dict] = []
        ping_result = adapter.ping()
        checks.append(
            {
                "name": "ping",
                "status": "pass" if ping_result.get("ok") and ping_result.get("terminal") else "fail",
                "required": False,
                "detail": f"ping terminal={ping_result.get('terminal')}",
            }
        )

        order_result = self._safe_smoke_call(adapter.place_order, "AAPL", "buy", 100, order_type="limit", limit_price=195.5)
        checks.append(self._capability_check("place_order", capabilities, order_result, required=True))

        status_result = self._safe_smoke_call(adapter.fetch_order_status, "ORD-1")
        checks.append(self._capability_check("order_status", capabilities, status_result, required=True))
        if status_result["status"] == "pass":
            payload = status_result.get("result", {}).get(response_field_map["order_status_root"])
            checks.append(
                {
                    "name": "order_status_shape",
                    "status": "pass" if self._is_valid_order_status_shape(payload, response_field_map["order_status_id"], response_field_map["order_status_state"], "ORD-1") else "fail",
                    "required": True,
                    "detail": f"order_status={payload}",
                }
            )

        positions_result = self._safe_smoke_call(adapter.fetch_positions)
        checks.append(self._capability_check("positions", capabilities, positions_result, required=True))
        if positions_result["status"] == "pass":
            payload = positions_result.get("result", {}).get(response_field_map["positions_root"])
            checks.append(
                {
                    "name": "positions_shape",
                    "status": "pass" if self._is_valid_positions_shape(payload, response_field_map["position_symbol"], response_field_map["position_quantity"]) else "fail",
                    "required": True,
                    "detail": f"positions={payload}",
                }
            )

        balances_result = self._safe_smoke_call(adapter.fetch_balances)
        checks.append(self._capability_check("balances", capabilities, balances_result, required=True))
        if balances_result["status"] == "pass":
            payload = balances_result.get("result", {}).get(response_field_map["balances_root"])
            checks.append(
                {
                    "name": "balances_shape",
                    "status": "pass" if self._is_valid_balances_shape(payload, response_field_map["balance_cash"], response_field_map["balance_buying_power"]) else "fail",
                    "required": True,
                    "detail": f"balances={payload}",
                }
            )

        cancel_result = self._safe_smoke_call(adapter.cancel_order, "ORD-1")
        checks.append(self._capability_check("cancel_order", capabilities, cancel_result, required=False))

        trade_result = self._safe_smoke_call(adapter.fetch_trade_records, "AAPL")
        checks.append(self._capability_check("trade_records", capabilities, trade_result, required=False))
        if trade_result["status"] == "pass":
            payload = trade_result.get("result", {}).get(response_field_map["trade_records_root"])
            checks.append(
                {
                    "name": "trade_records_shape",
                    "status": "pass" if self._is_valid_trade_records_shape(payload, response_field_map["trade_record_id"], response_field_map["trade_record_symbol"], response_field_map["trade_record_quantity"]) else "warning",
                    "required": False,
                    "detail": f"trade_records={payload}",
                }
            )

        failed_required = [item for item in checks if item.get("required") and item.get("status") == "fail"]
        warnings = [item for item in checks if item.get("status") == "warning"]
        return {
            "status": "error" if failed_required else ("warning" if warnings else "ok"),
            "summary": (
                "Trading-terminal smoke test passed."
                if not failed_required and not warnings
                else (
                    "Trading-terminal smoke test passed for required capabilities, but optional capabilities still have gaps."
                    if not failed_required
                    else "Trading-terminal smoke test found required capability gaps that block automatic trading."
                )
            ),
            "checks": checks,
            "calls": calls,
            "repair_summary": self._build_repair_summary(checks),
        }

    def _safe_smoke_call(self, func, *args, **kwargs) -> dict:
        try:
            return {"status": "pass", "result": func(*args, **kwargs)}
        except RuntimeError as exc:
            text = str(exc)
            return {"status": "warning" if "not configured" in text else "fail", "error": text}
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            return {"status": "fail", "error": f"{exc.__class__.__name__}: {exc}"}

    def _capability_check(self, capability: str, capabilities: dict, smoke_result: dict, *, required: bool) -> dict:
        meta = capabilities.get(capability) or {}
        endpoint = meta.get("endpoint") or ""
        if not endpoint:
            return {
                "name": f"{capability}_capability",
                "status": "fail" if required else "warning",
                "required": required,
                "detail": f"{capability} endpoint is not available in the current documentation/spec.",
            }
        if smoke_result["status"] == "pass":
            path = (smoke_result.get("result") or {}).get("path") or endpoint
            return {
                "name": f"{capability}_capability",
                "status": "pass",
                "required": required,
                "detail": f"{capability} routed to {path}.",
            }
        return {
            "name": f"{capability}_capability",
            "status": "fail" if required else "warning",
            "required": required,
            "detail": smoke_result.get("error") or f"{capability} call failed.",
        }

    def _build_module_code(self, request: dict, slug: str, class_name: str) -> str:
        envs = self._normalized_api_key_envs(request["api_key_envs"])
        auth_block = self._auth_injection(request["auth_style"], request["auth_header_name"], request["auth_query_param"])
        provider_config = {
            "place_order": request["capabilities"]["place_order"]["endpoint"],
            "cancel_order": request["capabilities"]["cancel_order"]["endpoint"],
            "order_status": request["capabilities"]["order_status"]["endpoint"],
            "positions": request["capabilities"]["positions"]["endpoint"],
            "balances": request["capabilities"]["balances"]["endpoint"],
            "trade_records": request["capabilities"]["trade_records"]["endpoint"],
        }
        docs_note = str(request["docs_summary"]).replace('"""', "'''")
        docs_excerpt = request["docs_context"].get("docs_excerpt") or "No docs excerpt available."
        return (
            "from __future__ import annotations\n\n"
            "import json\n"
            "import os\n"
            "from urllib.parse import urlencode\n"
            "from urllib.request import Request, urlopen\n\n\n"
            f"class {class_name}:\n"
            f'    """Generated trading-terminal adapter for {request["terminal_name"]}.\\n\\n'
            f"    Terminal type: {request['terminal_type']}\\n"
            f"    Docs summary: {docs_note}\\n"
            f"    Docs excerpt: {docs_excerpt}\\n"
            '    """\n\n'
            "    def __init__(self, base_url: str | None = None, timeout_seconds: int = 10) -> None:\n"
            f'        self.base_url = (base_url or "{request["api_base_url"]}").rstrip("/")\n'
            f"        self.api_keys = [os.getenv(name, \"\") for name in {envs!r}]\n"
            "        self.api_key = next((value for value in self.api_keys if value), \"\")\n"
            "        self.timeout_seconds = timeout_seconds\n\n"
            "    def _request_json(self, method: str, path: str, params: dict[str, str] | None = None, payload: dict | None = None) -> dict:\n"
            "        params = dict(params or {})\n"
            "        headers = {\"User-Agent\": \"Sentinel-Alpha/0.1\", \"Content-Type\": \"application/json\"}\n"
            f"{auth_block}"
            '        url = f"{self.base_url}/{path.lstrip(\'/\')}"\n'
            "        if params:\n"
            '            url = f"{url}?{urlencode(params)}"\n'
            "        body = None if payload is None else json.dumps(payload).encode('utf-8')\n"
            "        request = Request(url, data=body, headers=headers, method=method.upper())\n"
            "        with urlopen(request, timeout=self.timeout_seconds) as response:\n"
            "            content = response.read().decode('utf-8')\n"
            "        return json.loads(content)\n\n"
            "    def _require_endpoint(self, path: str, capability: str) -> str:\n"
            "        if not path:\n"
            "            raise RuntimeError(f'{capability} capability is not configured from the provided documentation.')\n"
            "        return path\n\n"
            "    def ping(self) -> dict:\n"
            "        return {\"ok\": True, \"terminal\": self.base_url}\n\n"
            "    def place_order(self, symbol: str, side: str, quantity: float, order_type: str = 'limit', limit_price: float | None = None) -> dict:\n"
            f"        path = self._require_endpoint({provider_config['place_order']!r}, 'place_order')\n"
            "        payload = {'symbol': symbol, 'side': side, 'quantity': quantity, 'order_type': order_type, 'limit_price': limit_price}\n"
            "        return self._request_json('POST', path, payload=payload)\n\n"
            "    def cancel_order(self, order_id: str) -> dict:\n"
            f"        path = self._require_endpoint({provider_config['cancel_order']!r}, 'cancel_order')\n"
            "        return self._request_json('POST', path, payload={'order_id': order_id})\n\n"
            "    def fetch_order_status(self, order_id: str) -> dict:\n"
            f"        path = self._require_endpoint({provider_config['order_status']!r}, 'order_status')\n"
            "        return self._request_json('GET', path, params={'order_id': order_id})\n\n"
            "    def fetch_positions(self) -> dict:\n"
            f"        path = self._require_endpoint({provider_config['positions']!r}, 'positions')\n"
            "        return self._request_json('GET', path)\n\n"
            "    def fetch_balances(self) -> dict:\n"
            f"        path = self._require_endpoint({provider_config['balances']!r}, 'balances')\n"
            "        return self._request_json('GET', path)\n\n"
            "    def fetch_trade_records(self, symbol: str | None = None) -> dict:\n"
            f"        path = self._require_endpoint({provider_config['trade_records']!r}, 'trade_records')\n"
            "        params = {'symbol': symbol} if symbol else None\n"
            "        return self._request_json('GET', path, params=params)\n"
        )

    def _build_test_code(self, request: dict, slug: str, class_name: str) -> str:
        return (
            "from __future__ import annotations\n\n"
            f"from sentinel_alpha.infra.generated_terminals.{slug} import {class_name}\n\n\n"
            f"def test_terminal_{slug}_adapter_exposes_core_trading_methods() -> None:\n"
            f"    adapter = {class_name}(base_url={request['api_base_url']!r})\n"
            "    assert hasattr(adapter, 'place_order')\n"
            "    assert hasattr(adapter, 'fetch_order_status')\n"
            "    assert hasattr(adapter, 'fetch_positions')\n"
            "    assert hasattr(adapter, 'fetch_balances')\n"
            "    assert hasattr(adapter, 'fetch_trade_records')\n"
        )

    def _build_config_candidate(self, request: dict, slug: str, target_module: str, target_test: str) -> dict:
        provider_config = {
            "enabled": True,
            "terminal_type": request["terminal_type"],
            "base_url": request["api_base_url"],
            "api_key_envs": self._normalized_api_key_envs(request["api_key_envs"]),
            "auth_style": request["auth_style"],
            "official_docs_url": request["official_docs_url"] or "",
            "docs_search_url": request["docs_search_url"] or "",
            "capabilities": request["capabilities"],
            "response_field_map": self._merged_response_field_map(request["response_field_map"]),
        }
        return {
            "terminal_name": slug,
            "display_name": request["terminal_name"],
            "provider_config": provider_config,
            "target_module": target_module,
            "target_test": target_test,
            "structured_integration_spec": request["structured_integration_spec"],
            "generated_terminals": {
                "providers": {
                    slug: {
                        **provider_config,
                        "target_module": target_module,
                        "target_test": target_test,
                    }
                }
            },
        }

    def _resolve_request(self, request: TradingTerminalIntegrationRequest) -> dict:
        docs_text = (request.interface_documentation or request.docs_summary or request.official_docs_url or "").strip()
        docs_url = request.official_docs_url or self._extract_first_url(docs_text)
        docs_context = self._fetch_documentation_context(docs_url=docs_url, docs_search_url=request.docs_search_url, docs_text=docs_text)
        spec = self._normalize_spec(request.integration_spec or {})
        terminal_name = request.terminal_name or str(spec.get("terminal_name") or "") or self._infer_terminal_name(docs_url, docs_text)
        terminal_type = str(request.terminal_type or spec.get("terminal_type") or self._infer_terminal_type(docs_text)).strip() or "broker_api"
        api_base_url = request.api_base_url or str(spec.get("api_base_url") or "") or self._infer_base_url(docs_text, docs_url)
        auth_style = str(request.auth_style or spec.get("auth_style") or self._infer_auth_style(docs_text)).strip() or "header"
        capabilities = self._resolve_capabilities(spec, request, docs_text)
        docs_summary = self._build_docs_summary(request, docs_text, docs_url)
        api_key_envs = self._normalized_api_key_envs(request.api_key_envs) or [self._default_api_key_env(terminal_name)]
        response_field_map = self._normalize_response_field_map(spec.get("response_field_map") or request.response_field_map)
        structured_integration_spec = {
            "terminal_name": terminal_name,
            "terminal_type": terminal_type,
            "api_base_url": api_base_url,
            "official_docs_url": docs_url,
            "docs_search_url": request.docs_search_url or "",
            "auth_style": auth_style,
            "auth_header_name": str(spec.get("auth_header_name") or "Authorization").strip() or "Authorization",
            "auth_query_param": str(spec.get("auth_query_param") or "apikey").strip() or "apikey",
            "capabilities": capabilities,
            "response_field_map": response_field_map,
            "notes": self._normalize_string_list(spec.get("notes")),
        }
        return {
            "terminal_name": terminal_name,
            "terminal_slug": self._slugify(terminal_name),
            "terminal_type": terminal_type,
            "official_docs_url": docs_url,
            "docs_search_url": request.docs_search_url,
            "docs_context": docs_context,
            "api_base_url": api_base_url,
            "auth_style": auth_style,
            "auth_header_name": structured_integration_spec["auth_header_name"],
            "auth_query_param": structured_integration_spec["auth_query_param"],
            "api_key_envs": api_key_envs,
            "api_key_supplied": bool(request.api_key),
            "api_key_preview": self._mask_secret(request.api_key),
            "docs_summary": docs_summary,
            "capabilities": capabilities,
            "response_field_map": response_field_map,
            "structured_integration_spec": structured_integration_spec,
            "analysis_generation_mode": str(spec.get("analysis_generation_mode") or "rule_based"),
            "analysis_status": str(spec.get("analysis_status") or "heuristic_completed"),
            "fallback_reason": spec.get("fallback_reason"),
        }

    def _build_integration_readiness_summary(self, request: dict) -> dict:
        capabilities = request["capabilities"]
        required_missing = [name for name in self.REQUIRED_CAPABILITIES if not (capabilities.get(name) or {}).get("endpoint")]
        optional_missing = [name for name in self.OPTIONAL_CAPABILITIES if not (capabilities.get(name) or {}).get("endpoint")]
        base_url_ok = str(request["api_base_url"] or "").startswith(("http://", "https://"))
        auth_ok = request["auth_style"] in {"header", "query", "bearer"}
        docs_ok = bool((request.get("docs_context") or {}).get("docs_fetch_ok")) or bool(request.get("official_docs_url")) or bool(request.get("docs_summary"))
        automatic_trading_ready = base_url_ok and auth_ok and not required_missing
        if not automatic_trading_ready:
            status = "blocked"
        elif optional_missing or not docs_ok:
            status = "caution"
        else:
            status = "ready"
        actions: list[str] = []
        if not base_url_ok:
            actions.append("技术文档没有提供可用的 API Base URL，当前无法执行自动交易。请补充官方技术文档。")
        if required_missing:
            actions.append(f"缺少自动交易必需能力：{', '.join(required_missing)}。当前无法执行自动交易，请重新提供更完整的技术文档。")
        if optional_missing:
            actions.append(f"缺少可选能力：{', '.join(optional_missing)}。系统会给出警告，你可以继续提供补充文档，或暂时忽略。")
        if not actions:
            actions.append("交易终端接入的必需能力已经齐备，可以继续测试并准备自动交易。")
        return {
            "status": status,
            "automatic_trading_ready": automatic_trading_ready,
            "base_url_ok": base_url_ok,
            "auth_ready": auth_ok,
            "docs_fetch_ok": docs_ok,
            "required_capabilities": list(self.REQUIRED_CAPABILITIES),
            "optional_capabilities": list(self.OPTIONAL_CAPABILITIES),
            "missing_required_capabilities": required_missing,
            "missing_optional_capabilities": optional_missing,
            "actions": actions,
        }

    def _build_exchange_support_summary(self, request: dict) -> dict:
        notes = list((request.get("structured_integration_spec") or {}).get("notes") or [])
        gaps = [
            "当前只覆盖单交易所/单账户路由。",
            "后续如需支持多交易所，需要补充跨交易所路由、账户聚合和冲突处理策略。",
            "后续如需支持多交易所，需要补充交易所选择、优先级和失败回退逻辑。",
        ]
        return {
            "scope": "single_exchange",
            "exchange_count_supported": 1,
            "multi_exchange_ready": False,
            "future_extension_gaps": gaps,
            "notes": notes,
        }

    def _resolve_capabilities(self, spec: dict, request: TradingTerminalIntegrationRequest, docs_text: str) -> dict:
        endpoint_overrides = {
            "place_order": request.order_endpoint,
            "cancel_order": request.cancel_endpoint,
            "order_status": request.order_status_endpoint,
            "positions": request.positions_endpoint,
            "balances": request.balances_endpoint,
            "trade_records": request.trade_records_endpoint,
        }
        inferred = {
            "place_order": self._infer_endpoint(docs_text, [r"(place|create|submit)[^.\n]{0,30}(order|trade)", r"POST\s+/[^\s]*(orders|trade)"]),
            "cancel_order": self._infer_endpoint(docs_text, [r"cancel[^.\n]{0,20}(order|trade)", r"POST\s+/[^\s]*cancel"]),
            "order_status": self._infer_endpoint(docs_text, [r"(order|trade)[^.\n]{0,20}(status|detail)", r"GET\s+/[^\s]*(orders|trade)[^\s]*(status|detail)"]),
            "positions": self._infer_endpoint(docs_text, [r"positions?", r"holdings?"]),
            "balances": self._infer_endpoint(docs_text, [r"balances?", r"account[^.\n]{0,20}(cash|equity|funds)"]),
            "trade_records": self._infer_endpoint(docs_text, [r"(trade|fill|execution)[^.\n]{0,20}(records?|history|list)", r"GET\s+/[^\s]*(fills|executions|trades|history)"]),
        }
        labels = {
            "place_order": "生成交易",
            "cancel_order": "撤单",
            "order_status": "查询订单状态",
            "positions": "账户股票信息",
            "balances": "账户资金信息",
            "trade_records": "查询交易记录",
        }
        capabilities: dict[str, dict[str, object]] = {}
        for name in (*self.REQUIRED_CAPABILITIES, *self.OPTIONAL_CAPABILITIES):
            endpoint = str(endpoint_overrides.get(name) or ((spec.get("capabilities") or {}).get(name, {}) or {}).get("endpoint") or inferred.get(name) or "").strip().strip("/")
            capabilities[name] = {
                "label": labels[name],
                "required": name in self.REQUIRED_CAPABILITIES,
                "endpoint": endpoint,
                "available": bool(endpoint),
            }
        return capabilities

    def _infer_endpoint(self, docs_text: str, patterns: list[str]) -> str:
        lines = [line.strip() for line in str(docs_text or "").splitlines() if line.strip()]
        for line in lines:
            lowered = line.lower()
            for pattern in patterns:
                if re.search(pattern, lowered):
                    for candidate in re.findall(r"(?:GET|POST|PUT|DELETE|PATCH)?\s*(/[A-Za-z0-9_./{}-]+)", line, flags=re.IGNORECASE):
                        return candidate.strip().strip("/")
                    for candidate in re.findall(r"([A-Za-z0-9_./{}-]+/[A-Za-z0-9_./{}-]+)", line):
                        if "/" in candidate:
                            return candidate.strip().strip("/")
        return ""

    def _build_docs_summary(self, request: TradingTerminalIntegrationRequest, docs_text: str, docs_url: str | None) -> str:
        explicit = str(request.docs_summary or "").strip()
        if explicit:
            return explicit
        text = re.sub(r"\s+", " ", docs_text).strip()
        if docs_url and docs_url not in text:
            text = f"{docs_url} {text}".strip()
        return text[:600]

    def _fetch_documentation_context(self, *, docs_url: str | None, docs_search_url: str | None, docs_text: str) -> dict:
        docs = self._fetch_text(docs_url) if docs_url else {"ok": False, "error": "missing url", "content": docs_text}
        search = self._fetch_text(docs_search_url) if docs_search_url else {"ok": False, "error": "missing url", "content": ""}
        return {
            "docs_fetch_ok": bool(docs.get("ok")) or bool(docs_text.strip()),
            "docs_error": docs.get("error"),
            "docs_excerpt": self._compact_text(docs.get("content") or docs_text),
            "search_fetch_ok": bool(search.get("ok")),
            "search_error": search.get("error"),
            "search_excerpt": self._compact_text(search.get("content")),
        }

    def _fetch_text(self, url: str | None) -> dict[str, object]:
        if not url:
            return {"ok": False, "error": "missing url", "content": ""}
        try:
            request = Request(url, headers={"User-Agent": "Sentinel-Alpha/0.1"})
            with urlopen(request, timeout=8) as response:
                content = response.read().decode("utf-8", errors="replace")
            return {"ok": True, "error": None, "content": content[:8000]}
        except (URLError, ValueError, TimeoutError) as exc:
            return {"ok": False, "error": str(exc), "content": ""}

    def _compact_text(self, content: object) -> str:
        return re.sub(r"\s+", " ", str(content or "")).strip()[:600]

    def _infer_terminal_name(self, docs_url: str | None, docs_text: str) -> str:
        if docs_url:
            host = (urlparse(docs_url).hostname or "").split(".")[0]
            if host:
                return host.replace("-", " ").title()
        first_line = next((line.strip() for line in docs_text.splitlines() if line.strip()), "")
        cleaned = re.sub(r"https?://\S+", "", first_line).strip()
        return cleaned[:40] or "Custom Trading Terminal"

    def _infer_terminal_type(self, docs_text: str) -> str:
        lowered = docs_text.lower()
        if "fix" in lowered:
            return "fix_gateway"
        if "desktop" in lowered:
            return "desktop_terminal"
        if "sdk" in lowered:
            return "local_sdk"
        if "gateway" in lowered:
            return "rest_gateway"
        return "broker_api"

    def _infer_base_url(self, docs_text: str, docs_url: str | None) -> str:
        text = docs_text or ""
        match = re.search(r"https?://[A-Za-z0-9./:_-]+", text)
        if match:
            return match.group(0).rstrip("/").replace("/docs", "")
        if docs_url:
            parsed = urlparse(docs_url)
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}"
        return ""

    def _infer_auth_style(self, docs_text: str) -> str:
        lowered = docs_text.lower()
        if "bearer" in lowered:
            return "bearer"
        if "apikey" in lowered or "api key" in lowered or "query param" in lowered:
            return "query"
        return "header"

    def _extract_first_url(self, text: str) -> str | None:
        match = re.search(r"https?://[A-Za-z0-9./:_-]+", str(text or ""))
        return match.group(0) if match else None

    def _default_api_key_env(self, terminal_name: str) -> str:
        slug = self._slugify(terminal_name).upper()
        return f"{slug}_API_KEY"

    def _slugify(self, value: str) -> str:
        lowered = value.strip().lower()
        lowered = re.sub(r"[^a-z0-9]+", "_", lowered)
        return lowered.strip("_") or "custom_terminal"

    def _auth_injection(self, auth_style: str, auth_header_name: str, auth_query_param: str) -> str:
        normalized = auth_style.lower().strip()
        if normalized == "query":
            return (
                "        if self.api_key:\n"
                f"            params[{auth_query_param!r}] = self.api_key\n"
            )
        if normalized == "bearer":
            return (
                "        if self.api_key:\n"
                "            headers['Authorization'] = f'Bearer {self.api_key}'\n"
            )
        return (
            "        if self.api_key:\n"
            f"            headers[{auth_header_name!r}] = self.api_key\n"
        )

    def _normalize_spec(self, spec: dict) -> dict:
        return dict(spec or {})

    def _normalize_string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _default_response_field_map(self) -> dict[str, str]:
        return {
            "positions_root": "positions",
            "position_symbol": "symbol",
            "position_quantity": "quantity",
            "balances_root": "balances",
            "balance_cash": "cash",
            "balance_buying_power": "buying_power",
            "order_status_root": "order",
            "order_status_id": "order_id",
            "order_status_state": "status",
            "trade_records_root": "records",
            "trade_record_id": "trade_id",
            "trade_record_symbol": "symbol",
            "trade_record_side": "side",
            "trade_record_quantity": "quantity",
        }

    def _merged_response_field_map(self, overrides: dict[str, str] | None) -> dict[str, str]:
        merged = dict(self._default_response_field_map())
        for key, value in (overrides or {}).items():
            if value:
                merged[key] = str(value)
        return merged

    def _normalize_response_field_map(self, overrides: dict[str, str] | None) -> dict[str, str]:
        return self._merged_response_field_map(overrides)

    def _mask_secret(self, value: str | None) -> str | None:
        if not value:
            return None
        if len(value) <= 6:
            return "*" * len(value)
        return f"{value[:3]}***{value[-2:]}"

    def _validate_python(self, source: str) -> dict[str, str | bool | None]:
        try:
            ast.parse(source)
            return {"ok": True, "error": None}
        except SyntaxError as exc:
            return {"ok": False, "error": f"{exc.msg} at line {exc.lineno}"}

    def _smoke_test_generated_module(self, source: str, class_name: str) -> dict[str, object]:
        try:
            namespace: dict[str, object] = {}
            exec(compile(source, "<generated_terminal_smoke>", "exec"), namespace)
            if class_name not in namespace:
                return {"ok": False, "error": f"Missing class {class_name}"}
            return {"ok": True, "error": None}
        except Exception as exc:  # pragma: no cover - defensive compile/runtime guard
            return {"ok": False, "error": f"{exc.__class__.__name__}: {exc}"}

    def _is_valid_positions_shape(self, payload: object, symbol_key: str, quantity_key: str) -> bool:
        if not isinstance(payload, list) or not payload:
            return False
        first = payload[0]
        if not isinstance(first, dict):
            return False
        return isinstance(first.get(symbol_key), str) and isinstance(first.get(quantity_key), (int, float))

    def _is_valid_balances_shape(self, payload: object, cash_key: str, buying_power_key: str) -> bool:
        if not isinstance(payload, dict):
            return False
        return isinstance(payload.get(cash_key), (int, float)) and isinstance(payload.get(buying_power_key), (int, float))

    def _is_valid_order_status_shape(self, payload: object, order_id_key: str, status_key: str, expected_order_id: str) -> bool:
        if not isinstance(payload, dict):
            return False
        return payload.get(order_id_key) == expected_order_id and isinstance(payload.get(status_key), str)

    def _is_valid_trade_records_shape(self, payload: object, record_id_key: str, symbol_key: str, quantity_key: str) -> bool:
        if not isinstance(payload, list) or not payload:
            return False
        first = payload[0]
        if not isinstance(first, dict):
            return False
        return isinstance(first.get(record_id_key), str) and isinstance(first.get(symbol_key), str) and isinstance(first.get(quantity_key), (int, float))

    def _build_repair_summary(self, checks: list[dict]) -> dict:
        failed_required = [item for item in checks if item.get("required") and item.get("status") == "fail"]
        warnings = [item for item in checks if item.get("status") == "warning"]
        actions: list[str] = []
        if failed_required:
            actions.append("当前缺少自动交易必需能力，无法执行自动交易。请重新提供更完整的技术文档。")
        if warnings:
            actions.append("存在可选能力缺口或字段映射不完整。你可以继续补充文档，或接受警告后继续。")
        if not actions:
            actions.append("交易终端接入已通过当前 smoke test。")
        primary_route = "terminal_required_capability_repair" if failed_required else ("terminal_optional_capability_review" if warnings else "none")
        return {
            "status": "needs_repair" if (failed_required or warnings) else "clear",
            "primary_route": primary_route,
            "priority": "P0" if failed_required else ("P1" if warnings else "none"),
            "actions": actions,
            "routes": checks,
        }
