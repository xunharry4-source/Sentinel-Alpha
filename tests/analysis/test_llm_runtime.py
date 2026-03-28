from __future__ import annotations

import json
from dataclasses import replace

from sentinel_alpha.config import get_settings
from sentinel_alpha.infra.llm_runtime import LLMRuntime


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


def test_task_profile_supports_multiple_api_key_envs(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY_A", "key-a")
    settings = replace(
        get_settings(),
        llm_enabled=True,
        llm_provider_envs={
            **get_settings().llm_provider_envs,
            "google": {
                "api_key_envs": ["GOOGLE_API_KEY_A", "GOOGLE_API_KEY_B"],
                "base_url_env": "GOOGLE_API_BASE",
            },
        },
    )
    runtime = LLMRuntime(settings)

    profile = runtime.task_profile("market_summarization", fallback_agent="intelligence_agent")

    assert profile.provider == "google"
    assert profile.api_key_present is True
    assert profile.api_key_envs == ["GOOGLE_API_KEY_A", "GOOGLE_API_KEY_B"]
    assert profile.models
    assert profile.active_api_key_env == "GOOGLE_API_KEY_A"
    assert profile.credential_count == 1


def test_invoke_text_task_rotates_credentials_on_rate_limit(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY_A", "key-a")
    monkeypatch.setenv("GOOGLE_API_KEY_B", "key-b")
    monkeypatch.setenv("GOOGLE_API_BASE", "https://example.test/openai")
    settings = replace(
        get_settings(),
        llm_enabled=True,
        performance_enabled=False,
        llm_provider_envs={
            **get_settings().llm_provider_envs,
            "google": {
                "api_key_envs": ["GOOGLE_API_KEY_A", "GOOGLE_API_KEY_B"],
                "base_url_env": "GOOGLE_API_BASE",
            },
        },
        llm_task_configs={
            **get_settings().llm_task_configs,
            "market_summarization": {
                "provider": "google",
                "models": ["gemini-2.5-flash", "gemini-2.5-pro"],
                "temperature": 0.2,
                "max_tokens": 1200,
            },
        },
    )
    runtime = LLMRuntime(settings)

    calls: list[str] = []

    def fake_urlopen(req, timeout=60):
        auth = req.headers.get("Authorization", "")
        calls.append(auth)
        if auth.endswith("key-a"):
            from urllib.error import HTTPError
            import io

            raise HTTPError(
                req.full_url,
                429,
                "Too Many Requests",
                hdrs=None,
                fp=io.BytesIO(b'{"error":"rate limit"}'),
            )
        return _FakeHTTPResponse(
            200,
            {
                "choices": [{"message": {"content": "live result"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 7},
            },
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = runtime.invoke_text_task(
        "market_summarization",
        "Summarize this",
        fallback_agent="intelligence_agent",
        fallback_text="fallback result",
        system_prompt="Summarize.",
    )

    assert result["text"] == "live result"
    assert result["profile"].generation_mode == "live_llm"
    assert result["invocation"]["actual_generation_mode"] == "live_llm"
    assert result["invocation"]["rotated_credentials"] is True
    assert result["invocation"]["attempted_models"] == ["gemini-2.5-flash"]
    assert result["invocation"]["attempted_api_key_envs"] == ["GOOGLE_API_KEY_A", "GOOGLE_API_KEY_B"]
    assert calls == ["Bearer key-a", "Bearer key-b"]


def test_task_profile_rejects_inline_api_keys_and_masks_them():
    settings = replace(
        get_settings(),
        llm_enabled=True,
        llm_provider_envs={
            **get_settings().llm_provider_envs,
            "google": {
                "api_key_envs": [
                    "AIzaSyAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                    "AIzaSyBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
                ],
                "base_url_env": "GOOGLE_API_BASE",
            },
        },
    )
    runtime = LLMRuntime(settings)

    profile = runtime.task_profile("market_summarization", fallback_agent="intelligence_agent")
    described = runtime.describe()
    provider_runtime = runtime.provider_runtime_summary()["google"]

    assert profile.api_key_present is False
    assert profile.api_key_envs == ["google#invalid_1", "google#invalid_2"]
    assert profile.active_api_key_env is None
    assert profile.credential_count == 0
    assert described["providers"]["google"]["api_key_envs"] == ["google#invalid_1", "google#invalid_2"]
    assert provider_runtime["configured_api_key_envs"] == ["google#invalid_1", "google#invalid_2"]
    assert provider_runtime["available_api_key_envs"] == []
    assert provider_runtime["active_api_key_env"] is None


def test_summarize_intelligence_returns_translated_documents(monkeypatch):
    runtime = LLMRuntime(replace(get_settings(), llm_enabled=False, performance_enabled=False))

    monkeypatch.setattr(
        runtime,
        "invoke_text_task",
        lambda task, prompt_text, **kwargs: {
            "text": json.dumps(
                {
                    "localized_summary": "英伟达需求维持强劲，市场情绪偏积极。",
                    "translated_documents": [
                        {
                            "document_id": "doc-1",
                            "translated_title": "英伟达需求依旧强劲",
                            "translated_summary": "报道称 AI 服务器需求保持强劲，利润率稳定。",
                            "brief_summary_cn": "AI 服务器需求强劲，利润率稳定。",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            "profile": runtime.task_profile(task, fallback_agent="intelligence_agent"),
            "invocation": {"actual_generation_mode": "template_fallback", "fallback_reason": None},
        },
    )

    result = runtime.summarize_intelligence(
        "NVDA AI demand",
        [
            {
                "document_id": "doc-1",
                "title": "NVDA demand stays strong",
                "summary": "AI server demand remains strong.",
                "content": "AI server demand remains strong and margins are holding.",
                "url": "https://example.com/nvda",
                "source": "example.com",
                "sentiment_hint": 0.4,
            }
        ],
    )

    assert result["summary"] == "英伟达需求维持强劲，市场情绪偏积极。"
    assert result["translated_documents"][0]["translated_title"] == "英伟达需求依旧强劲"
    assert result["translated_documents"][0]["brief_summary_cn"] == "AI 服务器需求强劲，利润率稳定。"
