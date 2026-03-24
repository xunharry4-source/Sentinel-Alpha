# No-Fabrication Policy

This project forbids “looks fine” claims when the system is not actually producing live outputs or when errors exist.

## Core Principle

Never let UI, logs, or reports imply that something is working if it is not actually working.

If any layer fails, the failure must be explicit:

- UI must show an error banner for failed requests.
- Backend must return explicit failure status and preserve failure detail in session history.
- Reports must carry provenance fields for how they were generated.

## Banned Behaviors

- Claiming “LLM analysis completed” when `report_generation_mode != live_llm`.
- Claiming “Redis persistence verified” without:
  - Redis running, and
  - `SENTINEL_REDIS_URL` active, and
  - `redis-cli ping -> PONG`.
- Claiming “full-flow tested” when only API endpoints were called and no UI click chain was validated.
- Claiming “no errors” when the UI error banner is visible or any call returns non-2xx.
- Labeling template/heuristic output as “analysis” without explicitly labeling generation mode.
- Swallowing failures (silent catch with no user-visible output).

## Required Evidence for “Works” Claims

### Report provenance

Any behavioral / intelligence / research output must expose:

- `report_generation_mode`
- `analysis_status`
- `analysis_warning`
- `llm_invocation.actual_generation_mode`
- `llm_invocation.fallback_reason`

### Persistence

To claim persistence is working:

1. Create session
2. Restart API
3. Fetch the same `session_id` successfully

### Redis

To claim Redis-backed persistence is working:

- `docker compose ps redis`
- `docker compose exec -T redis redis-cli ping` returns `PONG`

## Why This Exists

The platform is agentic. If the system lies about provenance, debugging becomes impossible and user trust is destroyed.

