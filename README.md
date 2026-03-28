# Sentinel-Alpha

![Sentinel-Alpha Logo](assets/logo.jpg)

Behavior-Aligned Personal Trading Framework.

`Sentinel-Alpha` is a multi-agent trading research and product framework for building personal trading experts that adapt to an individual's behavior, intervention patterns, risk limits, and information environment.

The objective is not raw return maximization. The objective is user-aligned utility:

`U = E(R) - lambda * sigma^2 - phi(user_behavior)`

The current implementation supports multi-model routing rather than a single fixed LLM path. Different agents and tasks can use different providers and models, and strategy training can run as a guided auto-iteration loop or as a free iteration workflow.

The intended operating model is now explicit:

- future work should usually change strategy logic only
- the workflow, monitoring, archival, approval, and dataset protocol should remain platform-stable
- strategy evaluation should follow a canonical:
  - `train`
  - `validation`
  - `test`
  - `walk_forward`
  protocol rather than ad hoc per-strategy handling

Observability now includes:

- Prometheus metrics exposure
- Grafana dashboard entry configuration
- Sentry error reporting integration
- LangFuse tracing hooks for intelligence and strategy LLM tasks
- runtime LLM health summary with live-vs-fallback task visibility
- cumulative LLM API request and token totals in runtime health and page summaries
- LLM runtime quality signals including fallback ratio, recent fallback pressure, and cache-hit efficiency
- split-level backtest sample-density visibility for sparse validation/test windows
- data-health staleness detection with stale-source and max-stale-hours visibility
- runtime-health age tracking for research, repair, and terminal outputs so stale results degrade long-running confidence
- runtime-health recovery actions so each weak chain exposes a next-step revalidation route, including explicit revalidation_required flags

## No-Fabrication Policy (Must-Follow)

This repo forbids “looks fine” claims when the system is not actually producing live outputs or when errors exist.

- Never label template/heuristic results as live LLM analysis; reports must expose `report_generation_mode`, `analysis_status`, `analysis_warning`, and `llm_invocation`.
- Never claim Redis-backed persistence unless Redis is running and verified (`redis-cli ping -> PONG`) and `SENTINEL_REDIS_URL` is active.
- Never claim full-flow success unless the UI click chain is verified (not only API endpoints).
- Never swallow errors: UI must surface request failures; backend must return explicit status and keep failure detail.

Full policy: `docs/no-fabrication.md`.

The code mutation layer now includes a controlled `Programmer Agent` backed by `Aider`-style local editing flow:

- natural-language coding instruction intake
- constrained local file modification scope
- git diff capture
- commit hash capture
- rollback anchor capture
- acceptance, rollback, promotion, and stability summaries for each repair chain
- strategy-code experiment history

Free market-data integration now includes:

- `Yahoo Finance` public quote/history endpoints
- `Google News RSS` and `Yahoo Finance RSS` for public news retrieval
- `Alpha Vantage` via API key
- `Finnhub` via API key
- `AkShare` as an optional local Python provider
- `local_file` for local CSV/JSON quote and history files

Additional free datasets now include:

- fundamentals:
  - `SEC EDGAR` official free source
  - `Alpha Vantage` and `Finnhub` as free third-party fallbacks
  - `local_file` fallback
- dark pool:
  - `FINRA` official free source
  - `local_file` fallback
- options:
  - `Yahoo Finance` free third-party source
  - `Finnhub` fallback
  - `local_file` fallback

## What Exists Now

- behavioral stress scenario generation
- behavioral profiling
- execution-aware behavioral simulation with:
  - real latency capture per segment
  - execution status and execution reason
  - execution-quality ratios
  - high-noise execution vs hold ratios
- simulation execution-quality tracking with:
  - `execution_status`
  - `execution_reason`
  - executed / partial-fill / rejected / unfilled ratios
- explicit trading-frequency and timeframe preference flow
- behavior-based recommendation of trading rhythm
- behavior-based recommendation of default strategy type
- unified strategy interface with multiple strategy families
- mandatory integrity and stress checks before strategy approval
- multi-model LLM configuration for agent routing and task routing
- generated strategy code artifacts stored in each strategy package
- iterative strategy training logs and loop state
- strategy report archive, version history, failure evolution, and version restore workflow
- profile evolution from feedback and trade records
- system health diagnostics with module status, agent logs, recent errors, and token usage
- library and SDK diagnostics inside system health
- controlled Programmer Agent for local strategy-code mutation and self-repair
- Programmer Agent acceptance gate, rollback guidance, promotion gate, and repair-chain stability summary
- trading-terminal integration generation, smoke testing, and health summary
- terminal smoke-test repair summaries and terminal-repair jump flow
- terminal integration readiness summary before smoke testing
- terminal response-shape checks for positions, balances, and order-status
- configurable terminal `response_field_map` for provider-specific payload layouts
- terminal runtime summary with status, next action, primary repair route, contract confidence, and shape confidence
- PostgreSQL / TimescaleDB / Qdrant / Redis persistence adapters
- NiceGUI-based frontend workbench
- legacy static frontend web module (kept for compatibility during migration)

## Project Status

### Completed

The project already has several closed loops that are usable rather than merely illustrative:

- strategy research loop
  - structured inputs, data bundles, research summaries, winner selection, rejection reasons, release-gate reasoning, archive replay
- autoresearch loop
  - iteration hypotheses, per-variant hypotheses, cycle summaries, next hypotheses, memory, convergence tracking
- Programmer Agent loop
  - bounded retries, compile/contract/pytest gates, failure summaries, repair plans, acceptance, rollback, promotion, stability
- terminal integration loop
  - docs-driven adapter generation, readiness checks, smoke tests, response-shape validation, configurable field maps, repair summaries, runtime summaries
- runtime visibility loop
  - research, repair, terminal, data, and LLM health summaries across strategy, report, configuration, terminal, and system-health pages

In practice, the platform is already beyond a UI mock or one-shot demo. It behaves like a real single-user research workbench with replayable state and explicit diagnostics.

### In Progress

The main areas still being hardened are:

- deeper real backtest coupling
  - the workflow shape is stable, but the research engine still needs deeper real-market execution strength
- live LLM hardening
  - routing and fallback visibility are present, but production-grade live-provider behavior is still being tightened
- long-running single-user operation
  - runtime health summaries now exist, but long-duration recovery and resilience are still being strengthened

### Remaining

The largest remaining hard problems are:

- finalizing the real backtest engine into a deeper research execution layer
- making Programmer Agent more autonomous and harder to destabilize
- pushing terminal integration from strong smoke-level integration toward stronger real-endpoint confidence
- strengthening long-running platform recovery and sustained-operation behavior

Behavioral simulation is no longer treated as coarse `buy / sell / hold` intent only. The current platform also preserves execution quality, so profiling can distinguish:

- true executed behavior
- partial execution under liquidity pressure
- unfilled limit behavior
- rejected order behavior

That execution-quality summary is surfaced both in the behavioral report and in the downstream strategy input view.

## Main Docs

- technical guide: [github-technical-guide.md](docs/github-technical-guide.md)
- architecture: [architecture.md](docs/architecture.md)
- configuration: [configuration.md](docs/configuration.md)
- completion roadmap: [completion-roadmap.md](docs/completion-roadmap.md)
- Docker deployment: [docker-deployment.md](docs/docker-deployment.md)
- API spec: [api-spec.md](docs/api-spec.md)
- database spec: [database-spec.md](docs/database-spec.md)
- workflow skill: [SKILL.md](skills/sentinel-alpha-workflow/SKILL.md)

## Run

Default development flow:

- use local API + local NiceGUI hot reload during development
- do not use Docker as the primary edit-run-debug loop
- use Docker only after the local flow is stable and ready for integrated packaging or deployment verification

Backend, in-memory:

```bash
cd Sentinel-Alpha
PYTHONPATH=src uvicorn sentinel_alpha.api.app:app --host 127.0.0.1 --port 8001
```

Backend, persistent:

```bash
cd Sentinel-Alpha
PYTHONPATH=src uvicorn sentinel_alpha.api.persistent_app:app --host 127.0.0.1 --port 8001
```

Frontend WebUI, NiceGUI:

```bash
cd Sentinel-Alpha
PYTHONPATH=src python -m sentinel_alpha.nicegui.app
```

Local hot-reload development, API + NiceGUI together:

```bash
cd Sentinel-Alpha
./scripts/dev_local.sh
```

Default local URLs:

- API: `http://127.0.0.1:8001`
- NiceGUI: `http://127.0.0.1:8010`
- local script enables API reload and NiceGUI reload automatically

Legacy static frontend redirect shell, compatibility only:

```bash
cd Sentinel-Alpha
PYTHONPATH=src python -m sentinel_alpha.webapp.server
```

Dependency baseline:

- Python: `3.11+` locally, `python:3.13-slim` in Docker
- package constraints: [pyproject.toml](pyproject.toml)

Docker, memory mode:

```bash
cd Sentinel-Alpha
docker compose --profile memory up --build
```

The `web` service now starts the NiceGUI workbench by default on port `8010 -> 8000`.
Docker is not the default development loop anymore. Use local API + local NiceGUI first, then use Docker when the feature is already stable enough for integrated verification.

Docker, persistent mode:

```bash
cd Sentinel-Alpha
docker compose --profile persistent up --build
```

Docker deployment details:

- [docker-deployment.md](docs/docker-deployment.md)

Market data APIs:

- `GET /api/market-data/providers`
- `GET /api/market-data/quote`
- `GET /api/market-data/history`
- `GET /api/market-data/financials`
- `GET /api/market-data/dark-pool`
- `GET /api/market-data/options`

Local file market-data defaults:

- base path: `data/local_market_data`
- quote file: `{symbol}_quote.json`
- history file: `{symbol}_{interval}.csv`

## License

This project is licensed under the Apache License 2.0.

- [LICENSE](LICENSE)

## Frontend

Canonical frontend module:

- [nicegui](src/sentinel_alpha/nicegui)
- [app.py](src/sentinel_alpha/nicegui/app.py)
- [webapp](src/sentinel_alpha/webapp)
- [index.html](src/sentinel_alpha/webapp/static/index.html)

Frontend entry rule:

- NiceGUI is the only canonical user-facing WebUI.
- Legacy static pages under `src/sentinel_alpha/webapp/static/pages/` are redirect shells only and must not be treated as active feature surfaces.
- Any new user-facing page capability must land in [app.py](src/sentinel_alpha/nicegui/app.py), not as a new static HTML workflow.

## LLM Routing

LLM selection is configuration-driven rather than hardcoded in business logic.

Current config supports:

- global LLM enablement
- default provider/model/temperature/max tokens
- per-agent routing
- per-task routing

Important task routes now include:

- `intent_translation`
- `noise_generation`
- `behavior_analysis`
- `market_summarization`
- `strategy_analysis`
- `strategy_codegen`
- `strategy_critic`
- `Programmer Agent`

Current programmer-agent support:

- controlled execution through local config
- target-path allowlist
- diff / commit / rollback outputs
- session-level archival through `programmer_runs`, `history_events`, and `report_history`

## Current Research Platform State

The current platform already supports a usable research feedback loop:

- structured `feature_snapshot`
- `input_manifest`
- `data_bundle_id` and bundle registry
- strategy `research_summary`
- winner selection summary
- robustness summary
- evaluation snapshot and evaluation highlights
- release-gate summary
- rejection summary
- next-iteration repair routing
- release snapshot
- research trend summary
- research health conclusion
- repair trend summary
- repair convergence conclusion
- archived unified repair routes (`repair_route_summary`, `primary_repair_route`)
- cross-page jump flow from:
  - report page
  - intelligence page
  - system-health page
  - configuration page
  back into strategy or configuration repair surfaces
- terminal repair flow from:
  - system-health page
  - configuration page
  back into terminal integration repair surfaces

## Production Gaps

The current repository is a strong platform prototype, not a finished production trading system.

The remaining production-critical areas are:

- real broker and exchange execution
- hardened backtest and walk-forward engine on real data
- production risk controls and kill switches
- stable data pipelines for market, financials, options, and dark-pool data
- authentication, authorization, and audit trail coverage
- monitoring, alerting, runbooks, backup, and restore discipline

Canonical gap and completion tracking:

- [completion-roadmap.md](docs/completion-roadmap.md)

Current API support:

- `GET /api/llm-config`

Important runtime behavior:

- if provider credentials are present and LLM is enabled, the system can expose the live-model route
- if provider credentials are missing, the system falls back explicitly instead of pretending a live model ran

## Strategy Iteration

Strategy training is now modeled as a loop:

- submit or expand trade universe
- choose strategy type
- choose iteration mode:
  - `guided`
  - `free`
- choose auto-iteration count
- generate candidate
- generate strategy code artifact
- choose the current best version under the comparison protocol
- run integrity and stress/overfit checks only on that selected best version
- if checks fail, keep iterating
- if checks pass, allow approval

The reusable platform rule is:

- change strategy logic, code, parameters, and prompts when evolving strategy families
- avoid changing workflow phases, monitoring contracts, archival contracts, or approval gates unless the platform architecture itself is being redesigned
- avoid changing risk, audit, and dataset-protocol contracts unless the platform architecture itself is being redesigned
- treat testing as a tool for finding system errors, weaknesses, vulnerabilities, and possible latent defects as thoroughly as practical, not as a hurdle to bypass or a reason to hide problems
- if a task introduced new changes, run relevant tests or verification before presenting the result as ready
- do not use the user as the first effective test layer for a fresh change; verify it first, then ask the user to review
- default to completing the requested scope in one continuous execution flow instead of stopping after each small edit to ask whether to continue
- if the task is large, split it into a task list and continue through the list, updating it when new issues are found
- if a task adds a new feature, page, or material workflow change, update the technical documentation first and keep that documentation in the same change set
- the documentation must explain the feature or page description, its impact on the system, and the decomposition of the feature or page into concrete sub-functions
- do not leave new UI or workflow behavior undocumented while claiming the task is complete

The strategy evaluation protocol is:

- build a canonical `dataset_plan`
- evaluate `baseline`, `variant A`, and `variant B` under the same:
  - `train`
  - `validation`
  - `test`
  - `walk_forward`
  windows
- prefer the strongest valid `test` score, then use validation and walk-forward stability as rejection guards
- if tests expose breakage, instability, vulnerabilities, or weak assumptions, fix the underlying issue instead of narrowing, skipping, weakening, or gaming the test

Every iteration writes:

- strategy package
- strategy checks
- strategy training log
- feedback history
- strategy report archive
- version-comparison-ready metadata

Current strategy packages now include:

- `dataset_plan`
- `evaluation_protocol`
- per-variant dataset evaluation
- `train objective score`
- `validation objective score`
- `test objective score`
- `walk_forward score`
- `stability score`
- `train_test_gap`

The strategy frontend now exposes:

- current training status
- iteration history
- report archive
- version A vs version B comparison
- historical code viewer
- failure evolution timeline
- restore archived version into current experiment inputs
- Programmer Agent execution panel

## Validation

```bash
cd Sentinel-Alpha
PYTHONPATH=src python -m pytest tests/test_api_workflow.py tests/test_strategy_interface.py tests/test_pipeline.py tests/test_scenario_generator.py
PYTHONDONTWRITEBYTECODE=1 python -m py_compile src/sentinel_alpha/**/*.py tests/*.py
node --check src/sentinel_alpha/webapp/static/script.js
node --check src/sentinel_alpha/webapp/static/session-shell.js
```

- backtest quality signals such as concentration, exposure, and turnover should also influence robustness and release-gate decisions

- Programmer Agent should emit a unified repair_chain_summary so promotion, rollback, review, and auto-continue decisions are readable as one chain-level conclusion

- terminal integration should expose a unified terminal_reliability_summary so readiness, smoke status, field mapping, and contract confidence collapse into one sustained-use decision

- research summaries should expose a unified research_reliability_summary so coverage, backtest binding, backtest quality, and robustness collapse into one trust decision

- runtime health should expose a unified runtime_recovery_summary so overall continue/revalidate/stabilize/pause decisions are explicit
