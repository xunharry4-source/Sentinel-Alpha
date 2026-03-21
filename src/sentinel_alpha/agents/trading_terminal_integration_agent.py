from __future__ import annotations

import ast
import re
from types import MethodType
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request, urlopen


@dataclass(slots=True)
class TradingTerminalIntegrationRequest:
    terminal_name: str
    terminal_type: str
    official_docs_url: str
    docs_search_url: str | None
    api_base_url: str
    api_key_env: str | None
    auth_style: str
    order_endpoint: str
    cancel_endpoint: str
    order_status_endpoint: str
    positions_endpoint: str
    balances_endpoint: str
    docs_summary: str
    user_notes: str | None = None


class TradingTerminalIntegrationAgent:
    """Generates terminal adapter code, tests, config, and documentation context."""

    def build_terminal_package(self, request: TradingTerminalIntegrationRequest) -> dict:
        slug = self._slugify(request.terminal_name)
        class_name = "".join(part.capitalize() for part in slug.split("_")) + "TerminalAdapter"
        target_module = f"src/sentinel_alpha/infra/generated_terminals/{slug}.py"
        target_test = f"tests/generated/test_terminal_{slug}.py"
        docs_context = self._fetch_documentation_context(request)
        module_code = self._build_module_code(request, slug, class_name, docs_context)
        test_code = self._build_test_code(request, slug, class_name)
        config_candidate = self._build_config_candidate(request, slug, target_module, target_test)
        module_validation = self._validate_python(module_code)
        test_validation = self._validate_python(test_code)
        return {
            "terminal_name": request.terminal_name,
            "terminal_slug": slug,
            "class_name": class_name,
            "terminal_type": request.terminal_type,
            "official_docs_url": request.official_docs_url,
            "docs_search_url": request.docs_search_url,
            "docs_context": docs_context,
            "target_module": target_module,
            "target_test": target_test,
            "generated_module_code": module_code,
            "generated_test_code": test_code,
            "config_candidate": config_candidate,
            "validation": {
                "module_syntax_ok": module_validation["ok"],
                "test_syntax_ok": test_validation["ok"],
                "module_error": module_validation["error"],
                "test_error": test_validation["error"],
                "docs_fetch_ok": docs_context["docs_fetch_ok"],
                "ready_for_programmer_agent": module_validation["ok"] and test_validation["ok"],
            },
        }

    def run_smoke_test(self, package: dict) -> dict:
        module_code = package.get("generated_module_code") or ""
        class_name = package.get("class_name") or ""
        if not module_code or not class_name:
            return {
                "status": "error",
                "summary": "Missing generated module code or class name.",
                "checks": [],
            }
        namespace: dict[str, object] = {}
        exec(compile(module_code, f"<generated_terminal:{package.get('terminal_slug', 'unknown')}>", "exec"), namespace)
        adapter_cls = namespace.get(class_name)
        if adapter_cls is None:
            return {
                "status": "error",
                "summary": f"Generated class {class_name} not found.",
                "checks": [],
            }
        adapter = adapter_cls(base_url=package.get("config_candidate", {}).get("provider_config", {}).get("base_url"))  # type: ignore[misc]
        calls: list[dict] = []

        def fake_request_json(self_obj, method: str, path: str, params: dict | None = None, payload: dict | None = None) -> dict:
            calls.append(
                {
                    "method": method,
                    "path": path,
                    "params": dict(params or {}),
                    "payload": dict(payload or {}),
                }
            )
            return {"ok": True, "method": method, "path": path, "payload": dict(payload or {})}

        adapter._request_json = MethodType(fake_request_json, adapter)  # type: ignore[attr-defined]

        ping_result = adapter.ping()
        positions_result = adapter.fetch_positions()
        balances_result = adapter.fetch_balances()
        order_result = adapter.place_order("AAPL", "buy", 100, order_type="limit", limit_price=195.5)
        status_result = adapter.fetch_order_status("ORD-1")
        cancel_result = adapter.cancel_order("ORD-1")

        provider = package.get("config_candidate", {}).get("provider_config", {})
        checks = [
            {
                "name": "ping",
                "status": "pass" if ping_result.get("ok") and ping_result.get("terminal") else "fail",
                "detail": f"ping terminal={ping_result.get('terminal')}",
            },
            {
                "name": "positions_contract",
                "status": "pass" if positions_result.get("path") == provider.get("positions_endpoint") else "fail",
                "detail": f"GET {positions_result.get('path')}",
            },
            {
                "name": "balances_contract",
                "status": "pass" if balances_result.get("path") == provider.get("balances_endpoint") else "fail",
                "detail": f"GET {balances_result.get('path')}",
            },
            {
                "name": "order_contract",
                "status": "pass" if order_result.get("path") == provider.get("order_endpoint") and order_result.get("payload", {}).get("symbol") == "AAPL" else "fail",
                "detail": f"POST {order_result.get('path')} symbol={order_result.get('payload', {}).get('symbol')}",
            },
            {
                "name": "order_status_contract",
                "status": "pass" if status_result.get("path") == provider.get("order_status_endpoint") and status_result.get("params", {}).get("order_id") == "ORD-1" else "fail",
                "detail": f"GET {status_result.get('path')} order_id={status_result.get('params', {}).get('order_id')}",
            },
            {
                "name": "cancel_contract",
                "status": "pass" if cancel_result.get("path") == provider.get("cancel_endpoint") and cancel_result.get("payload", {}).get("order_id") == "ORD-1" else "fail",
                "detail": f"POST {cancel_result.get('path')} order_id={cancel_result.get('payload', {}).get('order_id')}",
            },
        ]
        failed = [item for item in checks if item["status"] != "pass"]
        return {
            "status": "ok" if not failed else "warning",
            "summary": "Terminal adapter smoke test passed." if not failed else "Terminal adapter smoke test has contract mismatches.",
            "checks": checks,
            "calls": calls,
        }

    def _fetch_documentation_context(self, request: TradingTerminalIntegrationRequest) -> dict:
        docs = self._fetch_text(request.official_docs_url)
        search = self._fetch_text(request.docs_search_url) if request.docs_search_url else {"ok": False, "error": "no search url", "content": ""}
        return {
            "docs_fetch_ok": docs["ok"],
            "docs_error": docs["error"],
            "docs_excerpt": self._compact_text(docs["content"]),
            "search_fetch_ok": search["ok"],
            "search_error": search["error"],
            "search_excerpt": self._compact_text(search["content"]),
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
        text = str(content or "")
        text = re.sub(r"\s+", " ", text).strip()
        return text[:600]

    def _build_module_code(
        self,
        request: TradingTerminalIntegrationRequest,
        slug: str,
        class_name: str,
        docs_context: dict,
    ) -> str:
        api_key_line = (
            f'        self.api_key = os.getenv("{request.api_key_env}", "")\n'
            if request.api_key_env
            else '        self.api_key = ""\n'
        )
        auth_block = self._auth_injection(request.auth_style)
        docs_note = self._compact_text(request.docs_summary) or "No docs summary provided."
        docs_excerpt = docs_context.get("docs_excerpt") or "Documentation fetch unavailable."
        search_excerpt = docs_context.get("search_excerpt") or "Search fetch unavailable."
        return (
            "from __future__ import annotations\n\n"
            "import json\n"
            "import os\n"
            "from urllib.parse import urlencode\n"
            "from urllib.request import Request, urlopen\n\n\n"
            f"class {class_name}:\n"
            f'    """Generated adapter for {request.terminal_name}.\\n\\n'
            f"    Terminal type: {request.terminal_type}\\n"
            f"    Docs summary: {docs_note}\\n"
            f"    Docs excerpt: {docs_excerpt}\\n"
            f"    Search excerpt: {search_excerpt}\\n"
            '    """\n\n'
            "    def __init__(self, base_url: str | None = None, timeout_seconds: int = 10) -> None:\n"
            f'        self.base_url = (base_url or "{request.api_base_url}").rstrip("/")\n'
            f"{api_key_line}"
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
            "    def ping(self) -> dict:\n"
            "        return {\"ok\": True, \"terminal\": self.base_url}\n\n"
            "    def place_order(self, symbol: str, side: str, quantity: float, order_type: str = \"limit\", limit_price: float | None = None) -> dict:\n"
            "        payload = {\n"
            "            \"symbol\": symbol,\n"
            "            \"side\": side,\n"
            "            \"quantity\": quantity,\n"
            "            \"order_type\": order_type,\n"
            "            \"limit_price\": limit_price,\n"
            "        }\n"
            f'        return self._request_json("POST", "{request.order_endpoint}", payload=payload)\n\n'
            "    def cancel_order(self, order_id: str) -> dict:\n"
            f'        return self._request_json("POST", "{request.cancel_endpoint}", payload={{"order_id": order_id}})\n\n'
            "    def fetch_order_status(self, order_id: str) -> dict:\n"
            f'        return self._request_json("GET", "{request.order_status_endpoint}", params={{"order_id": order_id}})\n\n'
            "    def fetch_positions(self) -> dict:\n"
            f'        return self._request_json("GET", "{request.positions_endpoint}")\n\n'
            "    def fetch_balances(self) -> dict:\n"
            f'        return self._request_json("GET", "{request.balances_endpoint}")\n'
        )

    def _build_test_code(self, request: TradingTerminalIntegrationRequest, slug: str, class_name: str) -> str:
        return (
            "from __future__ import annotations\n\n"
            f"from sentinel_alpha.infra.generated_terminals.{slug} import {class_name}\n\n\n"
            f"def test_terminal_{slug}_adapter_routes_order_and_position_calls() -> None:\n"
            f"    adapter = {class_name}(base_url=\"{request.api_base_url}\")\n"
            "    calls = []\n\n"
            "    def fake_request(method: str, path: str, params: dict[str, str] | None = None, payload: dict | None = None) -> dict:\n"
            "        calls.append((method, path, params or {}, payload or {}))\n"
            "        return {\"ok\": True, \"method\": method, \"path\": path, \"payload\": payload or {}}\n\n"
            "    adapter._request_json = fake_request  # type: ignore[method-assign]\n"
            "    adapter.place_order(\"AAPL\", \"buy\", 100, order_type=\"limit\", limit_price=195.5)\n"
            "    adapter.fetch_order_status(\"ORD-1\")\n"
            "    adapter.cancel_order(\"ORD-1\")\n"
            "    adapter.fetch_positions()\n"
            "    adapter.fetch_balances()\n\n"
            "    assert len(calls) == 5\n"
            "    assert calls[0][0] == \"POST\"\n"
            "    assert calls[0][3][\"symbol\"] == \"AAPL\"\n"
            "    assert calls[1][2][\"order_id\"] == \"ORD-1\"\n"
            "    assert calls[2][3][\"order_id\"] == \"ORD-1\"\n"
            "    assert calls[3][0] == \"GET\"\n"
            "    assert calls[4][0] == \"GET\"\n"
        )

    def _build_config_candidate(
        self,
        request: TradingTerminalIntegrationRequest,
        slug: str,
        target_module: str,
        target_test: str,
    ) -> dict:
        terminal_config = {
            "enabled": True,
            "terminal_type": request.terminal_type,
            "base_url": request.api_base_url,
            "api_key_env": request.api_key_env or "",
            "auth_style": request.auth_style,
            "official_docs_url": request.official_docs_url,
            "docs_search_url": request.docs_search_url or "",
            "order_endpoint": request.order_endpoint,
            "cancel_endpoint": request.cancel_endpoint,
            "order_status_endpoint": request.order_status_endpoint,
            "positions_endpoint": request.positions_endpoint,
            "balances_endpoint": request.balances_endpoint,
        }
        return {
            "terminal_name": slug,
            "display_name": request.terminal_name,
            "provider_config": terminal_config,
            "target_module": target_module,
            "target_test": target_test,
            "generated_terminals": {
                "providers": {
                    slug: {
                        **terminal_config,
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
        return lowered.strip("_") or "custom_terminal"

    def _auth_injection(self, auth_style: str) -> str:
        normalized = auth_style.lower().strip()
        if normalized == "query":
            return (
                "        if self.api_key:\n"
                "            params[\"apikey\"] = self.api_key\n"
            )
        if normalized == "bearer":
            return (
                "        if self.api_key:\n"
                "            headers[\"Authorization\"] = f\"Bearer {self.api_key}\"\n"
            )
        return (
            "        if self.api_key:\n"
            "            headers[\"X-API-Key\"] = self.api_key\n"
        )
