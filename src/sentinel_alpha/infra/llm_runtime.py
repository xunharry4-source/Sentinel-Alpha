from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from sentinel_alpha.config import AppSettings, get_settings

try:
    from langfuse import Langfuse
except ImportError:  # pragma: no cover
    Langfuse = None  # type: ignore[assignment]


@dataclass(slots=True)
class AgentLLMProfile:
    agent: str
    provider: str
    model: str
    temperature: float
    max_tokens: int
    enabled: bool
    api_key_present: bool
    generation_mode: str


class LLMRuntime:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self.usage_totals: dict[str, dict[str, object]] = {}
        self.recent_calls: list[dict[str, object]] = []
        self.langfuse = self._build_langfuse_client()

    def agent_profile(self, agent: str) -> AgentLLMProfile:
        return self._profile_from_config(agent, self.settings.llm_agent_configs.get(agent, {}))

    def task_profile(self, task: str, fallback_agent: str | None = None) -> AgentLLMProfile:
        config = self.settings.llm_task_configs.get(task)
        if config is None and fallback_agent is not None:
            config = self.settings.llm_agent_configs.get(fallback_agent, {})
        return self._profile_from_config(task, config or {})

    def _profile_from_config(self, name: str, config: dict[str, str | float | int]) -> AgentLLMProfile:
        provider = str(config.get("provider", self.settings.llm_default_provider))
        model = str(config.get("model", self.settings.llm_default_model))
        temperature = float(config.get("temperature", self.settings.llm_default_temperature))
        max_tokens = int(config.get("max_tokens", self.settings.llm_default_max_tokens))
        provider_envs = self.settings.llm_provider_envs.get(provider, {})
        api_key_env = str(provider_envs.get("api_key_env", ""))
        api_key_present = bool(api_key_env and os.getenv(api_key_env))
        enabled = bool(self.settings.llm_enabled)
        generation_mode = "live_llm" if enabled and api_key_present else "template_fallback"
        return AgentLLMProfile(
            agent=name,
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            enabled=enabled,
            api_key_present=api_key_present,
            generation_mode=generation_mode,
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
                "detail": f"LLM runtime is enabled with default provider {self.settings.llm_default_provider} and model {self.settings.llm_default_model}.",
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
                else f"Provide {self.settings.llm_provider_envs.get(profile.provider, {}).get('api_key_env', 'provider api key')} to activate this agent's live LLM path."
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
        return {
            "enabled": self.settings.llm_enabled,
            "default": {
                "provider": self.settings.llm_default_provider,
                "model": self.settings.llm_default_model,
                "temperature": self.settings.llm_default_temperature,
                "max_tokens": self.settings.llm_default_max_tokens,
            },
            "providers": self.settings.llm_provider_envs,
            "agents": self.agent_matrix(),
            "tasks": {
                task: asdict(self.task_profile(task))
                for task in sorted(self.settings.llm_task_configs.keys())
            },
            "usage": self.usage_snapshot(),
        }

    def usage_snapshot(self) -> dict:
        return {
            "totals": self.usage_totals,
            "recent_calls": self.recent_calls[-20:],
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
        symbols = ", ".join(selected_universe)
        signals = candidate_payload.get("signals", [])
        parameters = candidate_payload.get("parameters", {})
        rationale = candidate_payload.get("metadata", {})
        code = (
            f"# generated_by={codegen_profile.provider}/{codegen_profile.model}\n"
            f"# generation_mode={codegen_profile.generation_mode}\n"
            f"# analysis_model={analysis_profile.provider}/{analysis_profile.model}\n"
            f"# critic_model={critic_profile.provider}/{critic_profile.model}\n"
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
        self._record_usage("strategy_codegen", codegen_profile, prompt_basis, code)
        self._record_usage("strategy_critic", critic_profile, code, "strategy code reviewed")
        return {
            "profile": {
                "agent": asdict(profile),
                "analysis": asdict(analysis_profile),
                "codegen": asdict(codegen_profile),
                "critic": asdict(critic_profile),
            },
            "code": code,
            "summary": (
                f"Strategy code prepared through analysis={analysis_profile.provider}/{analysis_profile.model}, "
                f"codegen={codegen_profile.provider}/{codegen_profile.model}, "
                f"critic={critic_profile.provider}/{critic_profile.model}."
            ),
        }

    def summarize_intelligence(self, query: str, documents: list[dict]) -> dict:
        profile = self.task_profile("market_summarization", fallback_agent="intelligence_agent")
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
        self._record_usage("market_summarization", profile, f"{query}|{documents}", summary_text)
        return {
            "query": query,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "document_count": len(documents),
            "dominant_tone": dominant_tone,
            "highlights": highlights,
            "opportunities": opportunities,
            "risks": risks,
            "headline_rollup": titles,
            "summary": summary_text,
            "source_urls": source_urls,
            "profile": asdict(profile),
        }

    def _record_usage(self, task: str, profile: AgentLLMProfile, prompt_text: str, output_text: str) -> None:
        input_tokens = self._estimate_tokens(prompt_text)
        output_tokens = self._estimate_tokens(output_text)
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
                "last_called_at": None,
            },
        )
        bucket["calls"] = int(bucket["calls"]) + 1
        bucket["input_tokens"] = int(bucket["input_tokens"]) + input_tokens
        bucket["output_tokens"] = int(bucket["output_tokens"]) + output_tokens
        bucket["last_called_at"] = datetime.now(timezone.utc).isoformat()
        self.recent_calls.append(
            {
                "task": task,
                "provider": profile.provider,
                "model": profile.model,
                "generation_mode": profile.generation_mode,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        self.recent_calls = self.recent_calls[-50:]
        self._trace_to_langfuse(task, profile, prompt_text, output_text, input_tokens, output_tokens)

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
