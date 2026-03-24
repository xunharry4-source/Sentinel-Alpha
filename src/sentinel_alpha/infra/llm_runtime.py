from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import json
import re
import urllib.error
import urllib.request

from sentinel_alpha.config import AppSettings, get_settings

try:
    from langfuse import Langfuse
except ImportError:  # pragma: no cover
    Langfuse = None  # type: ignore[assignment]


@dataclass(slots=True)
class AgentLLMProfile:
    agent: str
    provider: str
    models: list[str]
    model: str
    temperature: float
    max_tokens: int
    enabled: bool
    api_key_present: bool
    generation_mode: str
    api_key_envs: list[str]
    active_api_key_env: str | None
    active_api_key_index: int | None
    credential_count: int


class LLMRuntime:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self.usage_totals: dict[str, dict[str, object]] = {}
        self.recent_calls: list[dict[str, object]] = []
        self._result_cache: dict[tuple, dict] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        self._provider_key_cursor: dict[str, int] = {}
        self.langfuse = self._build_langfuse_client()

    def _is_env_style_name(self, value: str) -> bool:
        return bool(re.fullmatch(r"[A-Z_][A-Z0-9_]*", value.strip()))

    def _provider_credentials(self, provider: str) -> list[dict[str, object]]:
        credentials: list[dict[str, object]] = []
        for index, configured in enumerate(self._provider_api_key_envs(provider)):
            value = configured.strip()
            if not value:
                continue
            # New-project rule: credentials must be environment variables, never inline secrets.
            if not self._is_env_style_name(value):
                credentials.append(
                    {
                        "configured": "<invalid>",
                        "label": f"{provider}#invalid_{index + 1}",
                        "value": None,
                        "available": False,
                        "source": "invalid_config",
                    }
                )
                continue
            label = value
            env_value = os.getenv(value)
            credentials.append(
                {
                    "configured": value,
                    "label": label,
                    "value": env_value,
                    "available": bool(env_value),
                    "source": "env" if env_value else "missing",
                }
            )
        return credentials

    def agent_profile(self, agent: str) -> AgentLLMProfile:
        return self._profile_from_config(agent, self.settings.llm_agent_configs.get(agent, {}))

    def task_profile(self, task: str, fallback_agent: str | None = None) -> AgentLLMProfile:
        config = self.settings.llm_task_configs.get(task)
        if config is None and fallback_agent is not None:
            config = self.settings.llm_agent_configs.get(fallback_agent, {})
        return self._profile_from_config(task, config or {})

    def _profile_from_config(self, name: str, config: dict[str, str | float | int]) -> AgentLLMProfile:
        provider = str(config.get("provider", self.settings.llm_default_provider))
        raw_models = config.get("models", self.settings.llm_default_models)
        models = [str(item).strip() for item in raw_models] if isinstance(raw_models, list) else []
        if not models:
            models = list(self.settings.llm_default_models)
        model = models[0]
        temperature = float(config.get("temperature", self.settings.llm_default_temperature))
        max_tokens = int(config.get("max_tokens", self.settings.llm_default_max_tokens))
        configured_entries = self._provider_api_key_envs(provider)
        credentials = self._provider_credentials(provider)
        available_labels = [str(item["label"]) for item in credentials if item["available"]]
        api_key_present = bool(available_labels)
        active_api_key_env, active_api_key_index = self._resolve_active_api_key(provider, available_labels)
        enabled = bool(self.settings.llm_enabled)
        generation_mode = "live_llm" if enabled and api_key_present else "template_fallback"
        return AgentLLMProfile(
            agent=name,
            provider=provider,
            models=models,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            enabled=enabled,
            api_key_present=api_key_present,
            generation_mode=generation_mode,
            api_key_envs=[str(item).strip() if self._is_env_style_name(str(item)) else f"{provider}#invalid_{index + 1}" for index, item in enumerate(configured_entries)],
            active_api_key_env=active_api_key_env,
            active_api_key_index=active_api_key_index,
            credential_count=len(available_labels),
        )

    def agent_matrix(self) -> dict[str, dict[str, str | float | int | bool]]:
        return {
            agent: asdict(self.agent_profile(agent))
            for agent in sorted(self.settings.llm_agent_configs.keys())
        }

    def system_health_modules(self) -> list[dict[str, str]]:
        modules: list[dict[str, str]] = []
        modules.extend(self._observability_modules())
        if not self.settings.llm_enabled:
            modules.append(
                {
                    "name": "llm_runtime",
                    "status": "warning",
                    "detail": "LLM runtime is configured but disabled.",
                    "recommendation": "Set llm.enabled=true or SENTINEL_LLM_ENABLED=1 to activate provider-backed agents.",
                }
            )
            return modules
        modules.append(
            {
                "name": "llm_runtime",
                "status": "ok",
                    "detail": f"LLM runtime is enabled with default provider {self.settings.llm_default_provider} and models {', '.join(self.settings.llm_default_models)}.",
                "recommendation": "No action required.",
            }
        )
        for agent in sorted(self.settings.llm_agent_configs.keys()):
            profile = self.agent_profile(agent)
            status = "ok" if profile.api_key_present else "warning"
            detail = (
                f"{agent} is mapped to {profile.provider}/{profile.model}."
                if profile.api_key_present
                else f"{agent} is mapped to {profile.provider}/{profile.model}, but provider credentials are missing."
            )
            recommendation = (
                "No action required."
                if profile.api_key_present
                else f"Provide valid credentials for {profile.provider} ({', '.join(profile.api_key_envs) or 'provider credential'}) to activate this agent's live LLM path."
            )
            modules.append(
                {
                    "name": f"llm_agent:{agent}",
                    "status": status,
                    "detail": detail,
                    "recommendation": recommendation,
                }
            )
        return modules

    def describe(self) -> dict:
        sanitized_providers = {
            provider: {
                "api_key_envs": [
                    str(item).strip() if self._is_env_style_name(str(item)) else f"{provider}#invalid_{index + 1}"
                    for index, item in enumerate(self._provider_api_key_envs(provider))
                ],
                "base_url_env": provider_config.get("base_url_env"),
            }
            for provider, provider_config in self.settings.llm_provider_envs.items()
        }
        return {
            "enabled": self.settings.llm_enabled,
            "strict": bool(getattr(self.settings, "llm_strict", True)),
            "default": {
                "provider": self.settings.llm_default_provider,
                "models": self.settings.llm_default_models,
                "model": self.settings.llm_default_models[0],
                "temperature": self.settings.llm_default_temperature,
                "max_tokens": self.settings.llm_default_max_tokens,
            },
            "providers": sanitized_providers,
            "agents": self.agent_matrix(),
            "tasks": {
                task: asdict(self.task_profile(task))
                for task in sorted(self.settings.llm_task_configs.keys())
            },
            "usage": self.usage_snapshot(),
        }

    def usage_snapshot(self) -> dict:
        totals = list(self.usage_totals.values())
        recent_calls = self.recent_calls[-20:]
        api_request_count = sum(int(item.get("calls", 0)) for item in totals)
        cache_hits = sum(int(item.get("cache_hits", 0)) for item in totals)
        rotated_credential_count = sum(int(item.get("rotated_credentials", 0)) for item in totals)
        live_request_count = sum(int(item.get("calls", 0)) for item in totals if item.get("generation_mode") == "live_llm")
        fallback_request_count = sum(int(item.get("calls", 0)) for item in totals if item.get("generation_mode") != "live_llm")
        recent_live_count = sum(1 for item in recent_calls if item.get("generation_mode") == "live_llm")
        recent_fallback_count = sum(1 for item in recent_calls if item.get("generation_mode") != "live_llm")
        active_api_key_envs = sorted({str(item.get("active_api_key_env")) for item in totals if item.get("active_api_key_env")})
        aggregate = {
            "api_request_count": api_request_count,
            "input_tokens": sum(int(item.get("input_tokens", 0)) for item in totals),
            "output_tokens": sum(int(item.get("output_tokens", 0)) for item in totals),
            "total_tokens": sum(int(item.get("input_tokens", 0)) + int(item.get("output_tokens", 0)) for item in totals),
            "cache_hits": cache_hits,
            "rotated_credential_count": rotated_credential_count,
            "active_api_key_envs": active_api_key_envs,
            "live_request_count": live_request_count,
            "fallback_request_count": fallback_request_count,
            "fallback_ratio": round(fallback_request_count / max(1, api_request_count), 4),
            "cache_hit_ratio": round(cache_hits / max(1, api_request_count + cache_hits), 4),
            "recent_call_count": len(recent_calls),
            "recent_live_count": recent_live_count,
            "recent_fallback_count": recent_fallback_count,
            "recent_fallback_ratio": round(recent_fallback_count / max(1, len(recent_calls)), 4),
        }
        return {
            "totals": self.usage_totals,
            "aggregate": aggregate,
            "recent_calls": recent_calls,
            "cache": self.cache_stats(),
        }

    def provider_runtime_summary(self) -> dict[str, dict[str, object]]:
        summary: dict[str, dict[str, object]] = {}
        for provider, provider_config in self.settings.llm_provider_envs.items():
            credentials = self._provider_credentials(provider)
            configured_labels = [str(item["label"]) for item in credentials]
            available_labels = [str(item["label"]) for item in credentials if item["available"]]
            active_env, active_index = self._resolve_active_api_key(provider, available_labels)
            rotated_count = sum(
                int(item.get("rotated_credentials", 0))
                for item in self.usage_totals.values()
                if item.get("provider") == provider
            )
            summary[provider] = {
                "configured_api_key_envs": configured_labels,
                "available_api_key_envs": available_labels,
                "credential_count": len(available_labels),
                "active_api_key_env": active_env,
                "active_api_key_index": active_index,
                "rotated_credential_count": rotated_count,
                "base_url_env": provider_config.get("base_url_env"),
            }
        return summary

    def cache_stats(self) -> dict[str, int | bool]:
        return {
            "enabled": self.settings.performance_enabled,
            "entries": len(self._result_cache),
            "max_entries": self.settings.performance_llm_cache_size,
            "hits": self._cache_hits,
            "misses": self._cache_misses,
        }

    def generate_strategy_code(
        self,
        strategy_type: str,
        selected_universe: list[str],
        candidate_payload: dict,
        feedback: str | None = None,
    ) -> dict[str, str | dict[str, str | float | int | bool]]:
        profile = self.agent_profile("strategy_evolver")
        analysis_profile = self.task_profile("strategy_analysis", fallback_agent="strategy_evolver")
        codegen_profile = self.task_profile("strategy_codegen", fallback_agent="strategy_evolver")
        critic_profile = self.task_profile("strategy_critic", fallback_agent="strategy_integrity_checker")
        artifact_cache_key = (
            "strategy_codegen",
            strategy_type,
            tuple(selected_universe),
            repr(candidate_payload),
            feedback or "",
            analysis_profile.provider,
            tuple(analysis_profile.models),
            codegen_profile.provider,
            tuple(codegen_profile.models),
            critic_profile.provider,
            tuple(critic_profile.models),
        )
        cached = self._cache_get(artifact_cache_key)
        if cached is not None:
            self._record_cache_hit("strategy_codegen", codegen_profile)
            return cached
        symbols = ", ".join(selected_universe)
        signals = candidate_payload.get("signals", [])
        parameters = candidate_payload.get("parameters", {})
        rationale = candidate_payload.get("metadata", {})
        code = (
            f"# generated_by={codegen_profile.provider}/{codegen_profile.model}\n"
            f"# generation_mode={codegen_profile.generation_mode}\n"
            f"# analysis_models={analysis_profile.provider}/{','.join(analysis_profile.models)}\n"
            f"# critic_models={critic_profile.provider}/{','.join(critic_profile.models)}\n"
            f"STRATEGY_TYPE = \"{strategy_type}\"\n"
            f"UNIVERSE = {selected_universe!r}\n"
            f"PARAMETERS = {parameters!r}\n"
            f"SIGNALS = {signals!r}\n"
            f"RATIONALE = {rationale!r}\n\n"
            f"def build_strategy_config():\n"
            f"    return {{\n"
            f"        'strategy_type': STRATEGY_TYPE,\n"
            f"        'universe': UNIVERSE,\n"
            f"        'parameters': PARAMETERS,\n"
            f"        'signals': SIGNALS,\n"
            f"        'feedback': {feedback!r},\n"
            f"        'notes': [\n"
            f"            'Configured for symbols: {symbols}',\n"
            f"            'Generated through the multi-model LLM strategy layer.',\n"
            f"        ],\n"
            f"    }}\n"
        )
        prompt_basis = f"{strategy_type}|{selected_universe}|{candidate_payload}|{feedback or ''}"
        self._record_usage("strategy_analysis", analysis_profile, prompt_basis, str(candidate_payload))
        codegen_result = self.invoke_text_task(
            "strategy_codegen",
            prompt_basis,
            fallback_agent="strategy_evolver",
            fallback_text=code,
            system_prompt="Generate deterministic Python strategy configuration code.",
            cache_key=("strategy_codegen_text", *artifact_cache_key[1:]),
        )
        critic_result = self.invoke_text_task(
            "strategy_critic",
            codegen_result["text"],
            fallback_agent="strategy_integrity_checker",
            fallback_text="strategy code reviewed",
            system_prompt="Review the generated strategy code for integrity and determinism.",
        )
        result = {
            "profile": {
                "agent": asdict(profile),
                "analysis": asdict(analysis_profile),
                "codegen": asdict(codegen_result["profile"]),
                "critic": asdict(critic_result["profile"]),
            },
            "code": codegen_result["text"] or code,
            "summary": (
                f"Strategy code prepared through analysis={analysis_profile.provider}/{analysis_profile.model}, "
                f"codegen={codegen_result['profile'].provider}/{codegen_result['profile'].model}, "
                f"critic={critic_result['profile'].provider}/{critic_result['profile'].model}."
            ),
            "invocation": {
                "codegen": codegen_result["invocation"],
                "critic": critic_result["invocation"],
            },
        }
        return self._cache_set(artifact_cache_key, result)

    def summarize_intelligence(self, query: str, documents: list[dict]) -> dict:
        profile = self.task_profile("market_summarization", fallback_agent="intelligence_agent")
        artifact_cache_key = ("market_summarization", query, repr(documents), profile.provider, tuple(profile.models))
        cached = self._cache_get(artifact_cache_key)
        if cached is not None:
            self._record_cache_hit("market_summarization", profile)
            return cached
        source_urls = [item.get("url", "") for item in documents if item.get("url")]
        titles = [item.get("title", "untitled") for item in documents[:5]]
        positive_count = sum(1 for item in documents if float(item.get("sentiment_hint", 0.0)) > 0.15)
        negative_count = sum(1 for item in documents if float(item.get("sentiment_hint", 0.0)) < -0.15)
        dominant_tone = "mixed"
        if positive_count > negative_count:
            dominant_tone = "positive"
        elif negative_count > positive_count:
            dominant_tone = "negative"
        highlights = [
            f"{item.get('source', 'unknown')}: {item.get('title', 'untitled')}"
            for item in documents[:3]
        ]
        risks = [
            item.get("title", "untitled")
            for item in documents
            if float(item.get("sentiment_hint", 0.0)) < -0.05
        ][:3]
        opportunities = [
            item.get("title", "untitled")
            for item in documents
            if float(item.get("sentiment_hint", 0.0)) > 0.05
        ][:3]
        summary_text = (
            f"围绕“{query}”共整理 {len(documents)} 条情报，当前舆情基调偏{dominant_tone}。"
            f" 主要来源聚焦于 {', '.join(sorted({item.get('source', 'unknown') for item in documents[:4]})) or 'unknown'}。"
        )
        invocation_result = self.invoke_text_task(
            "market_summarization",
            f"{query}|{documents}",
            fallback_agent="intelligence_agent",
            fallback_text=summary_text,
            system_prompt="Summarize market intelligence into a concise analyst note.",
            cache_key=("market_summarization_text", query, repr(documents), profile.provider, tuple(profile.models)),
        )
        result = {
            "query": query,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "document_count": len(documents),
            "dominant_tone": dominant_tone,
            "highlights": highlights,
            "opportunities": opportunities,
            "risks": risks,
            "headline_rollup": titles,
            "summary": invocation_result["text"] or summary_text,
            "source_urls": source_urls,
            "profile": asdict(invocation_result["profile"]),
            "invocation": invocation_result["invocation"],
        }
        return self._cache_set(artifact_cache_key, result)

    def invoke_text_task(
        self,
        task: str,
        prompt_text: str,
        *,
        fallback_agent: str | None = None,
        fallback_text: str,
        system_prompt: str,
        cache_key: tuple | None = None,
    ) -> dict[str, object]:
        profile = self.task_profile(task, fallback_agent=fallback_agent)
        if cache_key is not None:
            cached = self._cache_get(cache_key)
            if cached is not None:
                self._record_cache_hit(task, profile)
                return cached

        if bool(getattr(self.settings, "llm_strict", True)) and self.settings.llm_enabled and profile.generation_mode != "live_llm":
            raise RuntimeError(
                f"LLM strict mode is enabled but credentials are missing for provider={profile.provider}. "
                f"Set one of [{', '.join(profile.api_key_envs) or 'provider api key env'}]."
            )

        text = fallback_text
        actual_profile = profile
        invocation = {
            "requested_generation_mode": profile.generation_mode,
            "actual_generation_mode": "template_fallback",
            "provider": profile.provider,
            "model": profile.model,
            "models": profile.models,
            "attempted_models": [],
            "attempted_api_key_envs": [],
            "active_api_key_env": profile.active_api_key_env,
            "rotated_credentials": False,
            "rotated_models": False,
            "fallback_reason": "live_llm_unavailable",
        }

        if profile.generation_mode == "live_llm":
            live_result = self._invoke_live_chat(profile, prompt_text, system_prompt)
            if live_result["ok"]:
                text = str(live_result["text"])
                actual_profile = replace(profile, generation_mode="live_llm", model=str(live_result["active_model"]))
                invocation = {
                    "requested_generation_mode": profile.generation_mode,
                    "actual_generation_mode": "live_llm",
                    "provider": profile.provider,
                    "model": live_result["active_model"],
                    "models": profile.models,
                    "attempted_models": live_result["attempted_models"],
                    "attempted_api_key_envs": live_result["attempted_api_key_envs"],
                    "active_api_key_env": live_result["active_api_key_env"],
                    "rotated_credentials": bool(live_result["rotated_credentials"]),
                    "rotated_models": bool(live_result["rotated_models"]),
                    "fallback_reason": None,
                }
                self._record_usage(
                    task,
                    actual_profile,
                    prompt_text,
                    text,
                    input_tokens=int(live_result["input_tokens"]),
                    output_tokens=int(live_result["output_tokens"]),
                    active_api_key_env=live_result["active_api_key_env"],
                    rotated_credentials=bool(live_result["rotated_credentials"]),
                    fallback_reason=None,
                )
                result = {
                    "text": text,
                    "profile": actual_profile,
                    "invocation": invocation,
                }
                if cache_key is not None:
                    return self._cache_set(cache_key, result)
                return result

            if bool(getattr(self.settings, "llm_strict", True)) and self.settings.llm_enabled:
                raise RuntimeError(
                    f"Live LLM call failed for task={task} provider={profile.provider} "
                    f"models={','.join(profile.models)} reason={live_result.get('fallback_reason')} "
                    f"attempted_models={live_result.get('attempted_models')} attempted_keys={live_result.get('attempted_api_key_envs')}."
                )

            invocation = {
                "requested_generation_mode": profile.generation_mode,
                "actual_generation_mode": "template_fallback",
                "provider": profile.provider,
                "model": profile.model,
                "models": profile.models,
                "attempted_models": live_result["attempted_models"],
                "attempted_api_key_envs": live_result["attempted_api_key_envs"],
                "active_api_key_env": live_result["active_api_key_env"],
                "rotated_credentials": bool(live_result["rotated_credentials"]),
                "rotated_models": bool(live_result["rotated_models"]),
                "fallback_reason": live_result["fallback_reason"],
            }

        fallback_profile = replace(profile, generation_mode="template_fallback")
        self._record_usage(
            task,
            fallback_profile,
            prompt_text,
            text,
            active_api_key_env=invocation["active_api_key_env"],
            rotated_credentials=bool(invocation["rotated_credentials"]),
            fallback_reason=str(invocation.get("fallback_reason")) if invocation.get("fallback_reason") else None,
        )
        result = {
            "text": text,
            "profile": fallback_profile,
            "invocation": invocation,
        }
        if cache_key is not None:
            return self._cache_set(cache_key, result)
        return result

    def _record_usage(
        self,
        task: str,
        profile: AgentLLMProfile,
        prompt_text: str,
        output_text: str,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        active_api_key_env: str | None = None,
        rotated_credentials: bool = False,
        fallback_reason: str | None = None,
    ) -> None:
        input_tokens = input_tokens if input_tokens is not None else self._estimate_tokens(prompt_text)
        output_tokens = output_tokens if output_tokens is not None else self._estimate_tokens(output_text)
        key = f"{task}:{profile.provider}:{profile.model}"
        bucket = self.usage_totals.setdefault(
            key,
            {
                "task": task,
                "provider": profile.provider,
                "model": profile.model,
                "generation_mode": profile.generation_mode,
                "calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "active_api_key_env": None,
                "rotated_credentials": 0,
                "last_called_at": None,
            },
        )
        bucket["calls"] = int(bucket["calls"]) + 1
        bucket["input_tokens"] = int(bucket["input_tokens"]) + input_tokens
        bucket["output_tokens"] = int(bucket["output_tokens"]) + output_tokens
        if active_api_key_env:
            bucket["active_api_key_env"] = active_api_key_env
        if rotated_credentials:
            bucket["rotated_credentials"] = int(bucket.get("rotated_credentials", 0)) + 1
        bucket["last_called_at"] = datetime.now(timezone.utc).isoformat()
        self.recent_calls.append(
            {
                "task": task,
                "provider": profile.provider,
                "model": profile.model,
                "generation_mode": profile.generation_mode,
                "active_api_key_env": active_api_key_env,
                "rotated_credentials": rotated_credentials,
                "fallback_reason": fallback_reason,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        self.recent_calls = self.recent_calls[-50:]
        self._trace_to_langfuse(task, profile, prompt_text, output_text, input_tokens, output_tokens)

    def _record_cache_hit(self, task: str, profile: AgentLLMProfile) -> None:
        key = f"{task}:{profile.provider}:{profile.model}"
        bucket = self.usage_totals.setdefault(
            key,
            {
                "task": task,
                "provider": profile.provider,
                "model": profile.model,
                "generation_mode": profile.generation_mode,
                "calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_hits": 0,
                "last_called_at": None,
            },
        )
        bucket["cache_hits"] = int(bucket.get("cache_hits", 0)) + 1
        bucket["last_called_at"] = datetime.now(timezone.utc).isoformat()

    def _cache_get(self, key: tuple) -> dict | None:
        if not self.settings.performance_enabled:
            return None
        cached = self._result_cache.get(key)
        if cached is not None:
            self._cache_hits += 1
            return deepcopy(cached)
        self._cache_misses += 1
        return None

    def _cache_set(self, key: tuple, value: dict) -> dict:
        if self.settings.performance_enabled:
            self._result_cache[key] = deepcopy(value)
            self._trim_cache()
        return deepcopy(value)

    def _trim_cache(self) -> None:
        while len(self._result_cache) > self.settings.performance_llm_cache_size:
            first_key = next(iter(self._result_cache))
            self._result_cache.pop(first_key, None)

    def _provider_api_key_envs(self, provider: str) -> list[str]:
        provider_config = self.settings.llm_provider_envs.get(provider, {})
        env_names: list[str] = []
        multiple = provider_config.get("api_key_envs")
        if isinstance(multiple, list):
            env_names.extend(str(item) for item in multiple if str(item).strip())
        return env_names

    def _resolve_active_api_key(self, provider: str, available_envs: list[str]) -> tuple[str | None, int | None]:
        if not available_envs:
            return None, None
        cursor = self._provider_key_cursor.get(provider, 0) % len(available_envs)
        return available_envs[cursor], cursor

    def _rotate_provider_api_key(self, provider: str, available_envs: list[str]) -> tuple[str | None, int | None]:
        if not available_envs:
            return None, None
        current = self._provider_key_cursor.get(provider, 0)
        next_index = (current + 1) % len(available_envs)
        self._provider_key_cursor[provider] = next_index
        return available_envs[next_index], next_index

    def _default_base_url(self, provider: str) -> str | None:
        if provider == "google":
            return "https://generativelanguage.googleapis.com/v1beta/openai"
        if provider == "openai":
            return "https://api.openai.com/v1"
        return None

    def _provider_base_url(self, provider: str) -> str | None:
        provider_config = self.settings.llm_provider_envs.get(provider, {})
        base_url_env = str(provider_config.get("base_url_env", ""))
        return (os.getenv(base_url_env) if base_url_env else None) or self._default_base_url(provider)

    def _is_rate_limited(self, status_code: int | None, error_text: str) -> bool:
        lowered = (error_text or "").lower()
        return status_code == 429 or "rate limit" in lowered or "quota" in lowered or "resource exhausted" in lowered

    def _invoke_live_chat(self, profile: AgentLLMProfile, prompt_text: str, system_prompt: str) -> dict[str, object]:
        provider_credentials = [item for item in self._provider_credentials(profile.provider) if item["available"]]
        available_envs = [str(item["label"]) for item in provider_credentials]
        base_url = self._provider_base_url(profile.provider)
        if not available_envs or not base_url:
            return {
                "ok": False,
                "fallback_reason": "missing_provider_credentials",
                "attempted_models": [],
                "attempted_api_key_envs": [],
                "active_api_key_env": None,
                "active_model": None,
                "rotated_credentials": False,
                "rotated_models": False,
            }
        if profile.provider not in {"google", "openai"}:
            return {
                "ok": False,
                "fallback_reason": f"unsupported_live_provider:{profile.provider}",
                "attempted_models": [],
                "attempted_api_key_envs": [],
                "active_api_key_env": None,
                "active_model": None,
                "rotated_credentials": False,
                "rotated_models": False,
            }

        attempted: list[str] = []
        attempted_models: list[str] = []
        active_env, _ = self._resolve_active_api_key(profile.provider, available_envs)
        rotated = False
        rotated_models = False
        for model_index, model_name in enumerate(profile.models):
            attempted_models.append(model_name)
            if model_index > 0:
                rotated_models = True
            active_env, _ = self._resolve_active_api_key(profile.provider, available_envs)
            for attempt_index in range(len(available_envs)):
                env_name = active_env or available_envs[0]
                attempted.append(env_name)
                credential = next((item for item in provider_credentials if item["label"] == env_name), None)
                api_key = str(credential["value"]) if credential else ""
                payload = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt_text},
                    ],
                    "temperature": profile.temperature,
                    "max_tokens": profile.max_tokens,
                }
                req = urllib.request.Request(
                    f"{base_url.rstrip('/')}/chat/completions",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                    },
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        raw = resp.read().decode("utf-8")
                        body = json.loads(raw) if raw else {}
                        text = self._extract_chat_output(body)
                        usage = body.get("usage", {})
                        return {
                            "ok": True,
                            "text": text,
                            "attempted_models": attempted_models,
                            "attempted_api_key_envs": attempted,
                            "active_api_key_env": env_name,
                            "active_model": model_name,
                            "rotated_credentials": rotated,
                            "rotated_models": rotated_models,
                            "input_tokens": int(usage.get("prompt_tokens", self._estimate_tokens(prompt_text))),
                            "output_tokens": int(usage.get("completion_tokens", self._estimate_tokens(text))),
                        }
                except urllib.error.HTTPError as exc:
                    error_text = exc.read().decode("utf-8")
                    if self._is_rate_limited(exc.code, error_text) and attempt_index < len(available_envs) - 1:
                        active_env, _ = self._rotate_provider_api_key(profile.provider, available_envs)
                        rotated = True
                        continue
                    if self._is_rate_limited(exc.code, error_text):
                        break
                    return {
                        "ok": False,
                        "fallback_reason": f"http_{exc.code}",
                        "attempted_models": attempted_models,
                        "attempted_api_key_envs": attempted,
                        "active_api_key_env": env_name,
                        "active_model": model_name,
                        "rotated_credentials": rotated,
                        "rotated_models": rotated_models,
                    }
                except Exception as exc:
                    return {
                        "ok": False,
                        "fallback_reason": exc.__class__.__name__,
                        "attempted_models": attempted_models,
                        "attempted_api_key_envs": attempted,
                        "active_api_key_env": env_name,
                        "active_model": model_name,
                        "rotated_credentials": rotated,
                        "rotated_models": rotated_models,
                    }

        return {
            "ok": False,
            "fallback_reason": "credential_rotation_exhausted",
            "attempted_models": attempted_models,
            "attempted_api_key_envs": attempted,
            "active_api_key_env": active_env,
            "active_model": profile.model,
            "rotated_credentials": rotated,
            "rotated_models": rotated_models,
        }

    def _extract_chat_output(self, payload: dict) -> str:
        choices = payload.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
        return str(content or "")

    def _estimate_tokens(self, text: object) -> int:
        raw = str(text or "")
        return max(1, len(raw) // 4)

    def _build_langfuse_client(self):
        if not self.settings.langfuse_enabled or Langfuse is None:
            return None
        if not self.settings.langfuse_public_key or not self.settings.langfuse_secret_key:
            return None
        try:
            return Langfuse(
                public_key=self.settings.langfuse_public_key,
                secret_key=self.settings.langfuse_secret_key,
                host=self.settings.langfuse_host,
            )
        except Exception:
            return None

    def _trace_to_langfuse(
        self,
        task: str,
        profile: AgentLLMProfile,
        prompt_text: str,
        output_text: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        if self.langfuse is None:
            return
        try:
            trace = self.langfuse.trace(name=task)
            trace.generation(
                name=task,
                model=profile.model,
                input=prompt_text[:4000],
                output=output_text[:4000],
                metadata={
                    "provider": profile.provider,
                    "generation_mode": profile.generation_mode,
                },
                usage_details={
                    "input": input_tokens,
                    "output": output_tokens,
                    "total": input_tokens + output_tokens,
                },
            )
        except Exception:
            return

    def _observability_modules(self) -> list[dict[str, str]]:
        modules: list[dict[str, str]] = []
        modules.append(
            {
                "name": "prometheus",
                "status": "ok" if self.settings.prometheus_enabled else "warning",
                "detail": f"Prometheus metrics endpoint configured at {self.settings.prometheus_metrics_path}."
                if self.settings.prometheus_enabled
                else "Prometheus metrics are disabled.",
                "recommendation": "No action required."
                if self.settings.prometheus_enabled
                else "Enable observability.prometheus.enabled to expose API metrics.",
            }
        )
        sentry_ok = self.settings.sentry_enabled and bool(self.settings.sentry_dsn)
        modules.append(
            {
                "name": "sentry",
                "status": "ok" if sentry_ok else "warning",
                "detail": "Sentry error reporting is configured."
                if sentry_ok
                else "Sentry is disabled or missing DSN.",
                "recommendation": "No action required."
                if sentry_ok
                else "Set SENTINEL_SENTRY_ENABLED=1 and provide SENTINEL_SENTRY_DSN for production error visibility.",
            }
        )
        langfuse_ok = self.settings.langfuse_enabled and self.langfuse is not None
        modules.append(
            {
                "name": "langfuse",
                "status": "ok" if langfuse_ok else "warning",
                "detail": f"LangFuse tracing is configured against {self.settings.langfuse_host}."
                if langfuse_ok
                else "LangFuse is disabled or missing credentials.",
                "recommendation": "No action required."
                if langfuse_ok
                else "Set SENTINEL_LANGFUSE_ENABLED=1 and provide LangFuse public/secret keys to capture LLM traces.",
            }
        )
        modules.append(
            {
                "name": "grafana",
                "status": "ok" if self.settings.grafana_url else "warning",
                "detail": f"Grafana dashboard URL configured: {self.settings.grafana_url}."
                if self.settings.grafana_url
                else "Grafana URL is not configured.",
                "recommendation": "Open Grafana to inspect Prometheus dashboards."
                if self.settings.grafana_url
                else "Configure observability.grafana.url so users can jump to dashboards directly.",
            }
        )
        return modules
