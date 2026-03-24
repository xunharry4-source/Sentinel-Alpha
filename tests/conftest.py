import pytest

from sentinel_alpha.config import get_settings


def _load_repo_dotenv() -> None:
    import os
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    path = root / ".env"
    if not path.exists():
        return
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception:
        return


@pytest.fixture(autouse=True)
def _default_test_env(monkeypatch: pytest.MonkeyPatch):
    """
    Default test mode: REAL live LLM must be enabled (strict mode).

    If provider credentials are missing, tests must fail loudly rather than silently
    falling back to heuristics. This prevents "unit tests pass but real system fails".

    Developers can opt into a networkless stub ONLY via `pytest --stub-llm`.
    """
    monkeypatch.setenv("SENTINEL_LLM_ENABLED", "1")
    monkeypatch.setenv("SENTINEL_LLM_STRICT", "1")
    # Avoid redis connection attempts in unit tests; persistence is verified via docker e2e.
    monkeypatch.setenv("SENTINEL_REDIS_URL", "")

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def pytest_addoption(parser):
    parser.addoption(
        "--stub-llm",
        action="store_true",
        default=False,
        help="Use a local stub transport for LLM HTTP calls (NOT real external provider).",
    )


@pytest.fixture
def stub_llm_enabled(request) -> bool:
    return bool(request.config.getoption("--stub-llm"))


@pytest.fixture(autouse=True)
def _enforce_live_llm_or_stub(monkeypatch: pytest.MonkeyPatch, stub_llm_enabled: bool):
    """
    Enforce that either:
    - real live LLM credentials are present (default), OR
    - developer explicitly opts into `--stub-llm`.
    """
    if stub_llm_enabled:
        import json
        import urllib.request

        class _FakeHTTPResponse:
            def __init__(self, status: int, payload: dict):
                self.status = status
                self._payload = json.dumps(payload).encode("utf-8")

            def read(self) -> bytes:
                return self._payload

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        def _fake_chat_completion_content(payload: dict) -> str:
            system_text = ""
            messages = payload.get("messages") or []
            if isinstance(messages, list) and messages:
                sys_msg = next((m for m in messages if m.get("role") == "system"), None) or {}
                system_text = str(sys_msg.get("content") or "")
            if "Return strict JSON only with keys user_report and system_report" in system_text:
                return json.dumps(
                    {
                        "user_report": {
                            "user_summary": "基于本次行为序列的LLM个性化分析已完成。",
                            "recommended_trading_frequency": "high",
                            "recommended_timeframe": "minute",
                            "recommended_strategy_type": "trend_following_aligned",
                            "recommended_risk_ceiling": 25,
                            "trading_pace_note": "保持节奏一致，避免追涨杀跌。",
                            "execution_quality_note": "执行质量整体稳定，注意高噪音叙事下的冲动下单。",
                            "behavior_tags": ["disciplined"],
                        },
                        "system_report": {
                            "execution_quality_note": "execution stable",
                            "behavior_tags": ["disciplined"],
                            "risk_notes": ["enforce max loss per trade"],
                            "guardrails": ["cooldown after consecutive losses"],
                        },
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            if "Generate deterministic Python strategy configuration code" in system_text:
                return "def build_strategy_config():\n    return {'strategy_type':'rule_based_aligned'}\n"
            return "ok"

        def fake_urlopen(req, timeout=60):
            raw = req.data.decode("utf-8") if getattr(req, "data", None) else "{}"
            try:
                payload = json.loads(raw) if raw else {}
            except Exception:
                payload = {}
            content = _fake_chat_completion_content(payload)
            return _FakeHTTPResponse(
                200,
                {"choices": [{"message": {"content": content}}], "usage": {"prompt_tokens": 12, "completion_tokens": 7}},
            )

        monkeypatch.setenv("GOOGLE_API_KEY_1", "test-key-1")
        monkeypatch.setenv("GOOGLE_API_KEY_2", "test-key-2")
        monkeypatch.setenv("GOOGLE_API_KEY_3", "test-key-3")
        monkeypatch.setenv("GOOGLE_API_KEY_4", "test-key-4")
        monkeypatch.setenv("GOOGLE_API_BASE", "https://example.test/openai")
        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        get_settings.cache_clear()
        return

    import os

    _load_repo_dotenv()

    required = ["GOOGLE_API_KEY_1", "GOOGLE_API_KEY_2"]
    if not any(os.getenv(name) for name in required):
        pytest.exit(
            "Live LLM is required by default. Set GOOGLE_API_KEY_1/2 (and optionally 3/4) in the environment, "
            "or run `pytest --stub-llm` explicitly."
        )
