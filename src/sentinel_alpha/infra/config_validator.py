from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from sentinel_alpha.config import AppSettings


class ConfigValidator:
    """Validates saved runtime configuration and returns user-facing diagnostics."""

    def validate(self, settings: AppSettings) -> dict:
        checks: list[dict[str, str]] = []
        checks.extend(self._network_checks(settings))
        checks.extend(self._market_data_checks(settings))
        checks.extend(self._llm_checks(settings))
        checks.extend(self._programmer_checks(settings))

        status = "ok"
        if any(item["status"] == "error" for item in checks):
            status = "error"
        elif any(item["status"] == "warning" for item in checks):
            status = "warning"

        return {
            "status": status,
            "config_path": settings.config_path,
            "checks": checks,
            "summary": {
                "errors": sum(1 for item in checks if item["status"] == "error"),
                "warnings": sum(1 for item in checks if item["status"] == "warning"),
                "ok": sum(1 for item in checks if item["status"] == "ok"),
            },
            "restart_required": True,
        }

    def validate_target(self, settings: AppSettings, family: str, provider: str | None = None) -> dict:
        checks: list[dict[str, str]] = []
        normalized_family = family.strip().lower()
        if normalized_family == "market_data":
            checks = self._single_provider_checks("market_data", settings.market_data_provider_configs, provider)
        elif normalized_family == "fundamentals":
            checks = self._single_provider_checks("fundamentals", settings.fundamentals_provider_configs, provider)
        elif normalized_family == "dark_pool":
            checks = self._single_provider_checks("dark_pool", settings.dark_pool_provider_configs, provider)
        elif normalized_family == "options_data":
            checks = self._single_provider_checks("options_data", settings.options_provider_configs, provider)
        elif normalized_family == "llm":
            checks = self._llm_checks(settings)
        elif normalized_family == "programmer_agent":
            checks = self._programmer_checks(settings)
        else:
            checks = [
                {
                    "name": normalized_family,
                    "status": "error",
                    "detail": "Unknown validation target.",
                    "recommendation": "Use a supported family name.",
                }
            ]
        status = "ok"
        if any(item["status"] == "error" for item in checks):
            status = "error"
        elif any(item["status"] == "warning" for item in checks):
            status = "warning"
        return {
            "status": status,
            "config_path": settings.config_path,
            "checks": checks,
            "summary": {
                "errors": sum(1 for item in checks if item["status"] == "error"),
                "warnings": sum(1 for item in checks if item["status"] == "warning"),
                "ok": sum(1 for item in checks if item["status"] == "ok"),
            },
            "restart_required": False,
            "family": normalized_family,
            "provider": provider,
        }

    def _network_checks(self, settings: AppSettings) -> list[dict[str, str]]:
        checks = [
            self._url_check("api_host", f"http://{settings.api_host}:{settings.api_port}", "API host/port looks invalid."),
            self._url_check("frontend_host", f"http://{settings.frontend_host}:{settings.frontend_port}", "Frontend host/port looks invalid."),
        ]
        return checks

    def _market_data_checks(self, settings: AppSettings) -> list[dict[str, str]]:
        checks: list[dict[str, str]] = []
        checks.append(
            self._membership_check(
                "market_data_default_provider",
                settings.market_data_default_provider,
                settings.market_data_enabled_providers,
                "Default market-data provider is not enabled.",
            )
        )
        checks.append(
            self._membership_check(
                "fundamentals_default_provider",
                settings.fundamentals_default_provider,
                settings.fundamentals_enabled_providers,
                "Default fundamentals provider is not enabled.",
            )
        )
        checks.append(
            self._membership_check(
                "dark_pool_default_provider",
                settings.dark_pool_default_provider,
                settings.dark_pool_enabled_providers,
                "Default dark-pool provider is not enabled.",
            )
        )
        checks.append(
            self._membership_check(
                "options_default_provider",
                settings.options_default_provider,
                settings.options_enabled_providers,
                "Default options provider is not enabled.",
            )
        )
        checks.extend(self._provider_checks("market_data", settings.market_data_provider_configs))
        checks.extend(self._provider_checks("fundamentals", settings.fundamentals_provider_configs))
        checks.extend(self._provider_checks("dark_pool", settings.dark_pool_provider_configs))
        checks.extend(self._provider_checks("options_data", settings.options_provider_configs))
        return checks

    def _llm_checks(self, settings: AppSettings) -> list[dict[str, str]]:
        checks: list[dict[str, str]] = []
        if not settings.llm_enabled:
            checks.append(
                {
                    "name": "llm.enabled",
                    "status": "warning",
                    "detail": "LLM runtime is disabled.",
                    "recommendation": "Enable llm.enabled if model-backed agents should run live.",
                }
            )
            return checks
        provider_envs = settings.llm_provider_envs
        default_provider = settings.llm_default_provider
        if default_provider not in provider_envs:
            checks.append(
                {
                    "name": "llm.default_provider",
                    "status": "error",
                    "detail": f"Default LLM provider {default_provider} is not defined.",
                    "recommendation": "Add the provider under [llm.providers.*] or switch default_provider.",
                }
            )
        else:
            api_key_env = str(provider_envs[default_provider].get("api_key_env", ""))
            api_key_present = bool(api_key_env and os.getenv(api_key_env))
            checks.append(
                {
                    "name": "llm.default_provider",
                    "status": "ok" if api_key_present else "warning",
                    "detail": f"Default LLM provider is {default_provider}.",
                    "recommendation": "No action required." if api_key_present else f"Set {api_key_env} to activate live LLM calls.",
                }
            )
        return checks

    def _programmer_checks(self, settings: AppSettings) -> list[dict[str, str]]:
        path = Path(settings.programmer_agent_repo_path).expanduser()
        exists = path.exists()
        return [
            {
                "name": "programmer_agent.repo_path",
                "status": "ok" if exists else "error",
                "detail": f"Configured repo path: {path}",
                "recommendation": "No action required." if exists else "Update programmer_agent.repo_path to an existing repository path.",
            }
        ]

    def _provider_checks(self, family: str, provider_configs: dict[str, dict[str, str | bool]]) -> list[dict[str, str]]:
        checks: list[dict[str, str]] = []
        for provider, config in provider_configs.items():
            enabled = bool(config.get("enabled", True))
            if not enabled:
                checks.append(
                    {
                        "name": f"{family}.{provider}",
                        "status": "warning",
                        "detail": f"{provider} is disabled.",
                        "recommendation": "Enable it only if you intend to use this provider.",
                    }
                )
                continue
            base_url = str(config.get("base_url", ""))
            if provider == "local_file":
                base_path = Path(str(config.get("base_path", "data/local_market_data"))).expanduser()
                checks.append(
                    {
                        "name": f"{family}.{provider}",
                        "status": "ok" if base_path.exists() else "warning",
                        "detail": f"Local data path: {base_path}",
                        "recommendation": "No action required." if base_path.exists() else "Create the local data directory or update base_path.",
                    }
                )
                continue
            checks.append(self._url_check(f"{family}.{provider}", base_url, f"{provider} base_url is invalid or empty."))
        return checks

    def _single_provider_checks(
        self,
        family: str,
        provider_configs: dict[str, dict[str, str | bool]],
        provider: str | None,
    ) -> list[dict[str, str]]:
        if provider:
            config = provider_configs.get(provider)
            if config is None:
                return [
                    {
                        "name": f"{family}.{provider}",
                        "status": "error",
                        "detail": f"{provider} is not defined under {family}.",
                        "recommendation": "Add the provider config or choose a configured provider.",
                    }
                ]
            return self._provider_checks(family, {provider: config})
        return self._provider_checks(family, provider_configs)

    def _url_check(self, name: str, value: str, error_message: str) -> dict[str, str]:
        parsed = urlparse(value)
        ok = bool(parsed.scheme and parsed.netloc)
        return {
            "name": name,
            "status": "ok" if ok else "error",
            "detail": value,
            "recommendation": "No action required." if ok else error_message,
        }

    def _membership_check(self, name: str, current: str, enabled: list[str], error_message: str) -> dict[str, str]:
        ok = current in enabled
        return {
            "name": name,
            "status": "ok" if ok else "error",
            "detail": f"default={current}, enabled={', '.join(enabled)}",
            "recommendation": "No action required." if ok else error_message,
        }
