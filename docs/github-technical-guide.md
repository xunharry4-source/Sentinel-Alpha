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
9. run mandatory integrity and stress checks
10. re-iterate automatically or manually if checks fail
11. approve strategy
12. switch to autonomous or advice-only mode
13. continue monitoring and profile evolution

## Repository Structure

### Backend

- `src/sentinel_alpha/domain`
  - core models
  - utility math
  - shared contracts
- `src/sentinel_alpha/agents`
  - `behavioral_profiler`
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

- `src/sentinel_alpha/webapp`
  - dedicated frontend module
- `src/sentinel_alpha/webapp/static`
  - `index.html`
  - `script.js`
  - `styles.css`
  - `config.json`
- `src/sentinel_alpha/webapp/static/pages`
  - simulation page
  - report page
  - preferences page
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
- `skills/sentinel-alpha-workflow/SKILL.md`

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

Serve the canonical frontend from the dedicated web module:

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

The web module currently exposes:

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
