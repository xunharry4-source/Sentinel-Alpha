from __future__ import annotations

import os
from dataclasses import asdict, dataclass

from sentinel_alpha.config import AppSettings, get_settings


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
