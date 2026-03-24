"""
One-time helper to move inline Google API keys out of config/settings.toml into a repo-local .env file.

Rules:
- Never print key values.
- Only writes env vars if inline keys are found.
- Rewrites llm.providers.google.api_key_envs to ENV var names (GOOGLE_API_KEY_1..N).

Usage:
  python scripts/migrate_google_keys_to_dotenv.py
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from sentinel_alpha.config import read_config_payload, write_config_payload


ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def _is_env_name(value: str) -> bool:
    return bool(ENV_NAME_RE.fullmatch((value or "").strip()))


def main() -> int:
    payload = read_config_payload()
    llm = payload.get("llm") or {}
    providers = (llm.get("providers") or {}) if isinstance(llm, dict) else {}
    google = providers.get("google") or {}
    if not isinstance(google, dict):
        raise SystemExit("Invalid config shape: llm.providers.google must be a table.")

    raw_envs = google.get("api_key_envs") or []
    if not isinstance(raw_envs, list):
        raw_envs = []

    direct_keys: list[str] = []
    kept_env_names: list[str] = []
    for item in raw_envs:
        s = str(item or "").strip()
        if not s:
            continue
        if _is_env_name(s):
            kept_env_names.append(s)
        else:
            direct_keys.append(s)

    if not direct_keys:
        print("No inline Google keys found. Nothing to migrate.")
        return 0

    repo_root = Path(__file__).resolve().parents[1]
    env_path = repo_root / ".env"
    existing_lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    existing_kv: dict[str, str] = {}
    for raw in existing_lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        existing_kv[k.strip()] = v.strip()

    # Allocate new env var names for direct keys.
    new_env_names: list[str] = []
    start_index = 1
    while f"GOOGLE_API_KEY_{start_index}" in existing_kv:
        start_index += 1
    for offset, key in enumerate(direct_keys):
        name = f"GOOGLE_API_KEY_{start_index + offset}"
        existing_kv[name] = key
        new_env_names.append(name)

    if "GOOGLE_API_BASE" not in existing_kv:
        existing_kv["GOOGLE_API_BASE"] = "https://generativelanguage.googleapis.com/v1beta/openai"

    # Write .env (do not leak values to stdout).
    out_lines = []
    for k in sorted(existing_kv.keys()):
        out_lines.append(f"{k}={existing_kv[k]}")
    env_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")

    # Rewrite config to env var names only.
    google["api_key_envs"] = kept_env_names + new_env_names
    providers["google"] = google
    llm["providers"] = providers
    payload["llm"] = llm
    write_config_payload(payload)

    print(f"Migrated {len(direct_keys)} inline Google keys into {env_path} and rewrote config to env var names.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

