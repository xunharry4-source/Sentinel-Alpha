# GitHub Technical Guide

This document is the GitHub-facing technical overview for `Sentinel-Alpha`.

## What This Repository Contains

`Sentinel-Alpha` is a multi-agent personal trading framework focused on:

- behavioral stress testing
- behavioral profiling
- user-aligned strategy synthesis
- strategy validation
- monitoring and deployment control

The repository is organized as an application framework rather than a single model or a single strategy script.

Canonical logo asset:

- `assets/logo.jpg`

## License

This repository is licensed under the Apache License 2.0.

- [LICENSE](/Users/harry/Documents/git/Sentinel-Alpha/LICENSE)

## Core Product Flow

The implemented product flow is:

1. create a workflow session
2. generate simulation scenarios
3. let the user perform simulated trading
4. produce a structured Behavioral Profiler report
5. recommend trading frequency, timeframe, and default strategy type
6. let the user confirm or override preferences
7. submit trade universe inputs
8. iterate strategy candidates with user feedback
9. generate strategy code artifacts and archive each iteration
10. choose the current best strategy version under the comparison protocol
11. run mandatory integrity and stress checks only on that selected best version
12. re-iterate automatically or manually if checks fail
13. optionally send code-change instructions to `Programmer Agent`
14. approve strategy
15. switch to autonomous or advice-only mode
16. continue monitoring and profile evolution

## Platform Reuse Rule

`Sentinel-Alpha` should behave as a reusable strategy platform rather than a one-off strategy script.

The intended rule is:

- future strategy work should usually modify strategy logic only
- the surrounding workflow should remain stable platform infrastructure
- testing exists to reveal real errors, regressions, vulnerabilities, and possible latent defects in the system as thoroughly as practical; it must not be treated as something to bypass, soften, or explain away

Stable platform layers:

- onboarding
- simulation and profiling
- universe intake
- objective selection
- dataset protocol
- integrity checks
- stress and overfit checks
- approval flow
- monitoring
- history and report archival

Typical strategy-only change scope:

- signal logic
- feature logic
- candidate code generation
- parameters
- prompts

## Repository Structure

### Backend

- `src/sentinel_alpha/domain`
  - core models
  - utility math
  - shared contracts
- `src/sentinel_alpha/agents`
  - `behavioral_profiler`
  - `programmer_agent`
  - `strategy_evolver`
  - `intelligence_agent`
- `src/sentinel_alpha/api`
  - FastAPI app
  - persistent app
  - workflow service
  - request/response schemas
- `src/sentinel_alpha/infra`
  - PostgreSQL adapters
  - TimescaleDB adapters
  - Qdrant adapters
  - Redis runtime bus
- `src/sentinel_alpha/strategies`
  - generic strategy interface
  - rule-based strategy
  - trend-following strategy
  - mean-reversion strategy
- `src/sentinel_alpha/research`
  - scenario generation

### Frontend

- `src/sentinel_alpha/nicegui`
  - canonical NiceGUI frontend
- `src/sentinel_alpha/nicegui/app.py`
  - unified NiceGUI workbench entry
- `src/sentinel_alpha/webapp`
  - legacy static redirect module
- `src/sentinel_alpha/webapp/static`
  - redirect shells and compatibility assets
- `src/sentinel_alpha/webapp/static/pages`
  - redirect-only compatibility pages
  - strategy page
  - intelligence page
  - operations page

### Docs and Specs

- `docs/architecture.md`
- `docs/configuration.md`
- `docs/docker-deployment.md`
- `docs/api-spec.md`
- `docs/database-spec.md`
- `docs/agent-state-machine.md`
- `docs/ui-page-function-report.md`
- `docs/ui-page-api-mapping.md`
- `skills/sentinel-alpha-workflow/SKILL.md`

Documentation rule:

- when a task adds a new feature, new page, or materially changes an existing workflow surface, update the relevant technical docs in the same task
- the doc update must explain the feature or page purpose, the impact on related systems or workflows, and the decomposition into concrete sub-functions or panels
- if the user-visible UI changes, update the page-function report and page-to-API mapping docs together with the implementation

### Persistence and Schemas

- `sql/product_schema.sql`
- `sql/behavioral_log.sql`

## Runtime Modes

### In-memory backend

Use this for local UI and workflow development:

```bash
cd /Users/harry/Documents/git/Sentinel-Alpha
PYTHONPATH=src uvicorn sentinel_alpha.api.app:app --host 127.0.0.1 --port 8001
```

### Persistent backend

Use this when PostgreSQL, TimescaleDB, Redis, and Qdrant are available:

```bash
cd /Users/harry/Documents/git/Sentinel-Alpha
PYTHONPATH=src uvicorn sentinel_alpha.api.persistent_app:app --host 127.0.0.1 --port 8001
```

### Frontend web module

Serve the canonical frontend from NiceGUI:

```bash
cd /Users/harry/Documents/git/Sentinel-Alpha
PYTHONPATH=src python -m sentinel_alpha.nicegui.app
```

### Recommended local development loop

Use local API plus local NiceGUI as the default development path:

```bash
cd /Users/harry/Documents/git/Sentinel-Alpha
./scripts/dev_local.sh
```

This is the preferred edit-run-debug loop. Docker should be reserved for later integrated verification and deployment checks.

The legacy static frontend module remains only as a redirect shell:

```bash
cd /Users/harry/Documents/git/Sentinel-Alpha
PYTHONPATH=src python -m sentinel_alpha.webapp.server
```

### Docker deployment

Use Docker Compose when you want a packaged runtime for the web module and API.

Memory mode:

```bash
cd /Users/harry/Documents/git/Sentinel-Alpha
docker compose --profile memory up --build
```

Persistent mode:

```bash
cd /Users/harry/Documents/git/Sentinel-Alpha
docker compose --profile persistent up --build
```

Detailed container notes are documented in [docker-deployment.md](/Users/harry/Documents/git/Sentinel-Alpha/docs/docker-deployment.md).

## Configuration

Configuration is file-driven.

Primary config sources:

- backend: `config/settings.toml`
- frontend: `src/sentinel_alpha/webapp/static/config.json`

These files define:

- backend host and port
- frontend host and port
- CORS origins
- PostgreSQL / TimescaleDB / Redis / Qdrant addresses
- minimum trade universe size
- health retry interval
- intelligence search templates
- LLM enablement
- default provider/model
- per-agent model routing
- per-task model routing
- programmer-agent command, repo scope, and allowlisted paths
- Prometheus metrics path
- Sentry settings
- LangFuse settings
- Grafana URL

Detailed configuration rules are documented in [configuration.md](/Users/harry/Documents/git/Sentinel-Alpha/docs/configuration.md).

## Dependency Baseline

The current dependency floor is tracked in [pyproject.toml](/Users/harry/Documents/git/Sentinel-Alpha/pyproject.toml).

Docker images use `python:3.13-slim`. The package baseline has been updated to the latest stable versions verified from PyPI on March 21, 2026.

The main runtime libraries are now:

- `fastapi>=0.135.1`
- `uvicorn>=0.41.0`
- `psycopg[binary]>=3.3.3`
- `qdrant-client>=1.17.0`
- `redis>=7.2.1`
- `langchain>=1.2.13`
- `langchain-core>=1.2.18`
- `langchain-qdrant>=1.1.0`

## Strategy Layer

Strategies are implemented through a generic interface.

Current strategy families:

- `rule_based_aligned`
- `trend_following_aligned`
- `mean_reversion_aligned`

Every strategy candidate must pass:

- `Strategy Integrity Checker`
- `Strategy Stress and Overfit Checker`

If any required check fails, the workflow moves into `strategy_rework_required` and approval is blocked.

Strategy training is not one-shot anymore.

The strategy evaluation protocol is also no longer ad hoc.

Each iteration now carries a canonical dataset plan:

- `train`
- `validation`
- `test`
- `walk_forward_windows`

`baseline`, `variant A`, and `variant B` are evaluated under the same protocol, and the workflow preserves:

- train objective score
- validation objective score
- test objective score
- walk-forward score
- stability score
- train-test gap

The workflow now supports:

- `guided` iteration mode
  - automatically keep iterating for the requested loop count until checks pass or the loop budget ends
- `free` iteration mode
  - keep exploring versions without forcing an early stop when a version passes

Each iteration now emits:

- a strategy package
- structured strategy checks
- a strategy training log row
- generated strategy code artifact
- LLM route metadata for the current version
- archived strategy iteration report
- dataset plan
- evaluation protocol
- split-level evaluation metrics

The strategy page now exposes a strategy experiment surface rather than a single latest-result panel:

- current training status
- problem analysis
- baseline and dual-plan comparison
- current recommended code
- strategy iteration history
- report archive
- version comparison
- historical code inspection
- failure evolution timeline
- archived version restore
- Programmer Agent execution records

## Behavioral Alignment Layer

This codebase does not treat user profiling as a one-time questionnaire.

The system keeps evolving the effective profile from:

- simulation behavior
- strategy training feedback
- trade execution records
- monitoring outputs

Relevant workflow fields:

- `behavioral_report`
- `profile_evolution`
- `strategy_feedback_log`
- `trade_records`
- `market_snapshots`
- `report_history`
- `history_events`
- `programmer_runs`

## LLM Routing Layer

This repository now distinguishes between:

- agent-level model routing
- task-level model routing

The system is explicitly designed to avoid forcing all work through a single model.

Current task classes include:

- `intent_translation`
- `noise_generation`
- `behavior_analysis`
- `market_summarization`
- `strategy_analysis`
- `strategy_codegen`
- `strategy_critic`

## Programmer Agent Layer

The repository now includes a controlled local coding agent:

- `Programmer Agent`

This role is intended for:

- strategy code self-repair
- local strategy implementation from natural-language instructions
- controlled file mutation
- git diff capture
- commit capture
- rollback anchoring

The current implementation does not allow arbitrary repo-wide mutation. It is constrained by configuration:

- command path
- repository root
- allowlisted editable paths
- auto-commit policy
- timeout

The canonical skill is:

- [programmer-agent SKILL](/Users/harry/Documents/git/Sentinel-Alpha/skills/programmer-agent/SKILL.md)

## Observability and Diagnostics

The system-health surface now includes:

- module status
- library and SDK diagnostics
- agent diagnostics
- recent agent logs
- recent errors
- token usage summary

Observability integrations now include:

- Prometheus
- Grafana
- Sentry
- LangFuse
- `strategy_codegen`
- `strategy_critic`

This matters because user-behavior analysis, strategy reasoning, and strategy code generation are different tasks and should not be collapsed into one generic model route.

The current runtime exposes:

- `GET /api/llm-config`

The strategy package now includes:

- `llm_profile`
- `agent_model_map`
- `task_model_map`
- `generated_strategy_code`
- `llm_generation_summary`

## Web Module Pages

The canonical frontend currently exposes the NiceGUI root workbench at `/`.

The legacy static web module remains only as redirect shells for compatibility:

- `/`
- `/pages/session.html`
- `/pages/simulation.html`
- `/pages/report.html`
- `/pages/preferences.html`
- `/pages/strategy.html`
- `/pages/intelligence.html`
- `/pages/system-health.html`
- `/pages/operations.html`

The homepage is now the overview and navigation surface only. Session creation, simulation, reporting, preference selection, strategy training, intelligence retrieval, system health, and operations are split into dedicated functional pages.

## Current Status

Implemented:

- scenario generation
- behavioral profiling
- structured preference selection
- behavior-based recommendation of trading rhythm
- behavior-based recommendation of strategy type
- strategy iteration and approval checks
- multi-model LLM routing config
- generated strategy code artifacts
- iterative strategy training logs
- profile evolution
- intelligence search skeleton
- dedicated web module

Not fully complete yet:

- full broker integration
- real production market data ingestion
- live provider SDK calls for all configured LLM routes
- persistent infrastructure health verification against live databases

## Validation

Core local checks:

```bash
cd /Users/harry/Documents/git/Sentinel-Alpha
PYTHONPATH=src python -m pytest tests/test_api_workflow.py tests/test_strategy_interface.py tests/test_pipeline.py tests/test_scenario_generator.py
PYTHONDONTWRITEBYTECODE=1 python -m py_compile src/sentinel_alpha/**/*.py tests/*.py
node --check src/sentinel_alpha/webapp/static/script.js
node --check src/sentinel_alpha/webapp/static/session-shell.js
```
