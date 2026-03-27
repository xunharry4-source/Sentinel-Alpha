---
name: sentinel-alpha-workflow
description: Use when working on Sentinel-Alpha's full operating workflow: first-run onboarding, test-data generation, simulated trading for behavioral profiling, profiler report output, target universe intake, iterative strategy generation with user feedback, deployment mode selection, and the three monitoring agents for user behavior, strategy health, and market/asset state.
---

# Sentinel-Alpha Workflow

Use this skill when the task concerns the full product flow of Sentinel-Alpha rather than an isolated module.

## Core Rule

Treat the product as a behavior-aligned trading system, not a generic backtester and not a questionnaire.

## Anti-Fabrication Rule (No Cheating)

This project forbids “looks fine” claims when the system is not actually producing live outputs or when errors exist.

Testing rule:

- the purpose of testing is to find real system errors, regressions, vulnerabilities, weak assumptions, and possible latent defects as thoroughly as practical
- do not treat tests as a box-checking exercise or something to weaken just to get a passing result
- testing should actively try to expose edge cases, failure paths, hidden coupling, and other likely defect surfaces rather than only confirming the happy path
- if a test fails because it exposed a real problem, fix the problem or surface the limitation explicitly instead of hiding it
- if you made a new change, run the relevant verification yourself before showing the change to the user as ready
- do not treat the user's manual review or click-through as the first real test pass for your new changes
- the user is not the fallback test harness for unverified modifications

Execution rule:

- when the user gives a larger workflow goal, do not stop after each small change to ask whether to continue
- if the work is long, break it into a concrete task list, execute the tasks in sequence, and update the list if new issues appear
- continue through the task list by default unless you hit a real blocker or a decision that genuinely requires user input
- treat the user's request as "finish the whole requested scope" unless the user explicitly asks for a checkpoint

Documentation rule:

- if the task adds a new feature, new page, new operator surface, or materially changes an existing workflow surface, update the related technical documentation before calling the task complete
- the documentation must state:
  - what the feature or page is
  - what problem it solves
  - what upstream or downstream systems it affects
  - how the page or feature is decomposed into concrete functions, panels, or execution steps
- if the change is UI-facing, update both the page function report and the page-to-API mapping when applicable
- do not leave a new workflow surface implemented in code while the technical docs still describe the previous behavior

### Banned behaviors

- Do not claim “LLM analysis completed” when `report_generation_mode != live_llm`.
- Do not claim “Redis persistence verified” unless Redis is actually running and `SENTINEL_REDIS_URL` is in effect.
- Do not claim “full-flow tested” if only API calls were tested; UI click chains must be verified for user-facing claims.
- Do not claim “no errors” if the frontend shows a global error banner or any API call returns non-2xx.
- Do not label template/heuristic outputs as “analysis” without explicitly labeling the generation mode.
- Do not hide or swallow failures; errors must surface in UI and in session logs.

### Required evidence for any “works” claim

- For any report output (behavioral / intelligence / research):
  - record:
    - `report_generation_mode`
    - `analysis_status`
    - `analysis_warning`
    - `llm_invocation.actual_generation_mode`
    - `llm_invocation.fallback_reason`
- For any persistence claim:
  - prove restart survival:
    - create session
    - restart API
    - fetch the same `session_id` successfully
- For any Docker/Redis claim:
  - show:
    - `docker compose ps redis`
    - `docker compose exec -T redis redis-cli ping` returning `PONG`
- For any UI claim:
  - verify the page with a real `session_id`:
    - the page shows `Current Session`
    - the expected panel is populated
    - no `Session not found` banner is shown

### Known failure modes that must never recur

- Behavioral report was rule-based while other agents used live LLM. This mismatch must be fixed, not explained away.
- Sessions were stored only in memory; after API restart, refresh caused `Session not found`. This must be prevented via persistence.
- Redis was not running, yet “Redis verified” was claimed. Redis must be started before asserting Redis-backed persistence.
- UI pages ignored URL `?session_id=` and read only localStorage, causing hidden session mismatch. URL/cookie session source must be authoritative.
- Frontend failures were silently swallowed without user-visible error. This must not happen.

Behavior rule:

- behavioral simulation is not complete if it only records coarse `buy / sell / hold`
- the workflow should preserve both:
  - user intent
  - execution quality
- simulation events should retain:
  - `execution_status`
  - `execution_reason`
  - real `latency_seconds` from current segment dwell time
- behavioral reporting should distinguish:
  - true executed behavior
  - partial execution under liquidity constraints
  - unfilled limit behavior
  - rejected order behavior
  - impulsive fast execution
  - hesitant delayed execution
  - high-noise execution vs high-noise patience
- execution-quality summaries should remain visible in:
  - the behavioral report
  - the report page
  - the downstream strategy input view
- simulation noise panels should not remain static decorations; they should reflect whether recent behavior was noise-driven execution, probing orders, or high-noise restraint

## Configuration Rule

Do not hardcode runtime endpoints, DSNs, ports, or workflow thresholds inside application logic.

The canonical configuration sources are:

- backend runtime config: [configuration.md](/Users/harry/Documents/git/Sentinel-Alpha/docs/configuration.md)
- backend config file: [settings.toml](/Users/harry/Documents/git/Sentinel-Alpha/config/settings.toml)
- frontend runtime config: [config.json](/Users/harry/Documents/git/Sentinel-Alpha/src/sentinel_alpha/webapp/static/config.json)

Required rule:

- API base URLs must come from frontend config
- frontend host and port must come from backend config
- CORS origins must come from backend config
- PostgreSQL, TimescaleDB, Redis, and Qdrant endpoints must come from backend config
- behavioral thresholds such as minimum trade universe size must come from backend config
- if a new service is added and no config entry exists yet, the task is not complete
- if an agent or workflow step uses LLMs, provider/model selection must be declared in config
- observability endpoints and credentials must also come from config
- do not force all agent reasoning and generation through a single model; support per-agent and per-task model routing
- strategy analysis, strategy code generation, and strategy critique should be allowed to use different models

Use environment-variable override only for deployment-sensitive values when needed, but keep the base shape in the config file.

Dependency rule:

- dependency versions must be tracked in [pyproject.toml](/Users/harry/Documents/git/Sentinel-Alpha/pyproject.toml)
- when the task explicitly asks for latest dependencies, verify versions against primary package sources before updating
- Docker base images should move with the supported dependency stack, not drift behind without reason

## Docker Deployment Rule

When Docker support is added or updated, keep deployment aligned with the same architecture and config contract.

Canonical deployment artifacts:

- compose spec: [docker-compose.yml](/Users/harry/Documents/git/Sentinel-Alpha/docker-compose.yml)
- API image: [Dockerfile.api](/Users/harry/Documents/git/Sentinel-Alpha/Dockerfile.api)
- web image: [Dockerfile.web](/Users/harry/Documents/git/Sentinel-Alpha/Dockerfile.web)
- deployment doc: [docker-deployment.md](/Users/harry/Documents/git/Sentinel-Alpha/docs/docker-deployment.md)

Required rule:

- web and API containers must run the canonical module entrypoints, not duplicate ad hoc scripts
- container configuration must come from the same config contract plus environment overrides
- persistent container deployments must provision PostgreSQL or TimescaleDB, Redis, and Qdrant explicitly
- if observability is enabled, Prometheus and Grafana should be provisioned as first-class services
- database initialization must come from tracked SQL files, not manual undocumented steps
- Docker documentation must state both memory-mode and persistent-mode startup paths

## Observability Rule

Observability must explain where the failure is, not merely show red or green lights.

Required rule:

- expose Prometheus metrics from the API
- provide Grafana as the dashboard entrypoint for users
- route application exceptions into Sentry when enabled
- trace LLM and intelligence/strategy summarization workloads into LangFuse when enabled
- system health output must include:
  - module status
  - agent status
  - recent agent logs
  - recent errors
  - token usage summary
  - output provenance (rule-based vs fallback vs live LLM)

Production observability rule:

- observability is not complete until users can locate failures across:
  - API
  - database
  - provider
  - agent
  - code-mutation task
  - order execution
  - token and model usage
- monitoring work is incomplete if the user still cannot tell which layer failed and why
- production observability should include dashboards, alerting, tracing, and operator diagnosis paths
- runtime-health summaries should also include LLM execution health so users can tell whether key tasks are running on live providers or fallback paths
- LLM runtime summaries should expose cumulative API request count, total token count, and live-vs-fallback request counts
- LLM runtime summaries should also expose quality signals such as fallback ratio, recent fallback pressure, and cache-hit efficiency
- backtest coverage summaries should expose split-level sample density and sparse validation/test warnings, not only total bars and symbol counts
- data-health summaries should expose data staleness, stale sources, and max stale age instead of only raw timestamps
- runtime-health summaries should expose age-hours for research, repair, and terminal outputs so old results do not look falsely healthy
- runtime-health summaries should also expose recovery actions so each weak chain has an explicit next-step revalidation route and explicit revalidation_required flags

## Web Module Rule

The frontend must live inside a dedicated web module, not as ad hoc loose files at the repo root.

Canonical web module paths:

- module package: [webapp](/Users/harry/Documents/git/Sentinel-Alpha/src/sentinel_alpha/webapp)
- static frontend assets: [static](/Users/harry/Documents/git/Sentinel-Alpha/src/sentinel_alpha/webapp/static)
- web module server entry: [server.py](/Users/harry/Documents/git/Sentinel-Alpha/src/sentinel_alpha/webapp/server.py)

Required rule:

- frontend pages, scripts, styles, and frontend config must be maintained under the web module
- backend changes that affect UI contracts must update the web module, not a duplicate standalone frontend
- if compatibility copies exist outside the module, treat them as transitional only and keep the module as the source of truth
- system health must be exposed as its own functional module, not buried inside an unrelated page

## Core Agent Catalog

The system must preserve the following eight core agents as first-class roles:

| Agent | Core Responsibility | Key Capabilities |
| --- | --- | --- |
| `Scenario Director` | orchestrate simulated market environments and replay extreme historical fragments | time-series generation, historical replay |
| `Noise Agent` | generate narrative interference and misleading social/news pressure | financial NLP, deceptive news generation, persuasive dialogue |
| `Behavioral Profiler` | infer cognitive bias and trading personality from user behavior in simulation | behavioral feature extraction, psychological scoring, clustering |
| `Intelligence Agent` | gather live market intelligence, macro inputs, fundamentals, and factors | API integrations, RAG retrieval |
| `Strategy Evolver` | train personalized strategies from behavioral profile, market data, and user feedback | RL, evolutionary search, Monte Carlo simulation |
| `Portfolio Manager` | execute allocation, rebalancing, and order logic when automation is enabled | MPT, VWAP, TWAP |
| `Intent Aligner` | translate fuzzy user intent into machine-usable constraints and risk prompts | LLM parsing, chain-of-thought style reasoning, affect understanding |
| `Risk Guardian` | enforce hard-coded safety limits based on profiled stress boundaries | rule validation, real-time anomaly detection |

These eight agents define the core product architecture.

The three monitoring agents added later are supervisory agents layered on top of this core.

An additional implementation agent is allowed when local code mutation is required:

| Agent | Core Responsibility | Key Capabilities |
| --- | --- | --- |
| `Programmer Agent` | perform controlled local code changes from natural-language instructions and preserve diff/commit/rollback trace | Aider integration, git diff, commit capture, rollback anchoring |
| `Trading Terminal Integration Agent` | turn a user-specified broker or terminal into a generated adapter package with docs context, tests, and config candidate | docs retrieval, adapter generation, test generation, Programmer Agent handoff |

Two additional strategy-check agents are mandatory before any strategy version can be approved:

| Agent | Core Responsibility | Key Capabilities |
| --- | --- | --- |
| `Strategy Integrity Checker` | check future leakage, cheating logic, and win-coding patterns in each strategy version | anti-lookahead validation, anti-cheat heuristics, anti-win-coding checks |
| `Strategy Stress and Overfit Checker` | run robustness validation on each strategy version | stress testing, walk-forward checks, overfit diagnostics, perturbation testing |

The user flow is:

1. First open the system
2. Generate or load behavioral test data
3. Let the user do simulated trading in stress scenarios
4. Produce a Behavioral Profiler report
5. Ask the user to explicitly choose trading frequency and preferred timeframe
6. Ask the user which assets they actually want to trade
7. Iteratively generate strategy candidates using:
   - profiler output
   - chosen assets
   - chosen trading rhythm and timeframe
   - market data
   - user feedback during training
8. Present the strategy and risk summary
9. Let the user choose:
   - autonomous trading
   - advice-only mode
10. Keep the system under continuous monitoring with:
   - user behavior monitoring
   - strategy health monitoring
   - market and watched-asset monitoring

## Trading Terminal Integration Rule

Trading terminal integration is not complete when the system only generates adapter code.

Required rule:

- a generated trading terminal package must include:
  - adapter code
  - test code
  - config candidate
  - documentation context
- before smoke tests run, terminal integration should expose a structured readiness summary that includes:
  - readiness status
  - base-url validity
  - auth-style readiness
  - endpoint completeness
  - docs availability
  - next actions
- terminal integration should support a smoke-test layer before live use
- smoke tests should at minimum cover:
  - ping
  - positions
  - balances or account summary
  - order placement contract
  - order-status contract
  - cancel contract
- terminal smoke tests should also validate basic response shapes for:
  - positions
  - balances
  - order status
- endpoint path checks alone are insufficient when the returned payload shape is unusable
- terminal integration should support a configurable response-field mapping layer so provider-specific payload layouts do not require hardcoded code edits
- smoke-test output must be archived into:
  - terminal integration runs
  - report history
  - history events
- terminal health should be visible outside the terminal page itself:
  - terminal integration page
  - system health page
  - configuration page
- terminal smoke-test failures must compress into a structured repair summary that includes:
  - primary repair route
  - repair priority
  - repair note
  - repair actions
- terminal integration should also expose a runtime summary that includes:
  - terminal health status
  - next action
  - primary repair route
  - contract confidence
  - shape confidence
- terminal repair summaries should be visible on:
  - terminal integration page
  - system health page
  - configuration page
- terminal runtime summaries should feed the overall runtime-health conclusion instead of duplicating separate frontend-only heuristics
- terminal diagnostics are incomplete if the user cannot jump directly from:
  - system health
  - configuration
  back into the terminal repair surface
- the terminal page should support backfilling the current repair summary into user-editable notes so the next iteration has explicit repair context

## Programmer Agent Acceptance Rule

Programmer Agent output is not complete when it only reports a diff and a raw failure.

Required rule:

- each bounded repair run should produce:
  - `failure_summary`
  - `repair_plan`
  - `acceptance_summary`
  - `rollback_summary`
  - `promotion_summary`
  - `stability_summary`
- `acceptance_summary` should state whether the latest patch is:
  - accepted
  - under review
  - rejected
- `rollback_summary` should state whether rollback is:
  - preferred
  - optional
  - unnecessary because the current validated patch is the baseline
- `promotion_summary` should state whether the latest patch is fit to become the next stable candidate
- `stability_summary` should state whether the repair chain is:
  - stable
  - caution
  - fragile
- strategy-page diagnostics should expose these summaries directly, not only raw stderr or diff output

## LLM Routing Rule

Behavior analysis, intent parsing, noise generation, strategy analysis, strategy code generation, and strategy critique are not the same task.

Required rule:

- `Intent Aligner`, `Noise Agent`, `Behavioral Profiler`, `Intelligence Agent`, and `Strategy Evolver` may use different model mappings
- within `Strategy Evolver`, at least these task classes must be allowed to use different models:
  - strategy analysis
  - strategy code generation
  - strategy critique
- LLM selection must be inspectable through API or health output
- if live provider credentials are unavailable, the workflow must degrade with explicit fallback status rather than silently pretending a live LLM ran

## Strategy Iteration Rule

Strategy training is a loop, not a one-shot action.

Required rule:

- each iteration must produce a new strategy version
- each iteration must be logged
- iteration failures must be logged with explicit error detail
- each iteration must first select the current best version under the dataset protocol
- only the selected best version should run the mandatory pre-approval check agents:
  - `Strategy Integrity Checker`
  - `Strategy Stress and Overfit Checker`
- non-selected intermediate candidates should remain comparison artifacts, not approval targets
- strategy versions must use the canonical version format:
  - `V<major>.<minor>-<test_version>-<strategy_name>`
- examples:
  - `V1.7-0-trend_following_aligned`
  - `V1.7-1-structural_upgrade`
  - `V1.7-2-strategy_improvement`
- `major.minor` identifies the main strategy generation round
- `test_version` identifies baseline or candidate test branch inside the round
- `strategy_name` identifies the strategy family or candidate plan name
- the user must be allowed to choose:
  - guided auto-iteration until the version passes
  - free iteration for a fixed number of rounds even if the user wants to keep exploring

## Strategy Logic Isolation Rule

The platform must be reusable across future strategy families without rewriting the workflow every time.

Required rule:

- the default expectation is that future work changes strategy logic only
- do not require workflow rewrites just because a new strategy family is introduced
- do not require UI flow rewrites just because a new strategy family is introduced
- do not require storage schema rewrites just because a new strategy family is introduced
- strategy-specific behavior should live behind the strategy interface and candidate contract
- the following layers are workflow-stable and must be treated as reusable platform infrastructure:
  - user onboarding
  - simulation and behavioral profiling
  - profile evolution
  - trade-universe intake
  - objective selection
  - strategy versioning
  - integrity checks
  - stress and overfit checks
  - deployment approval
  - monitoring
  - history and report archiving
- when adding or revising a strategy, prefer changing:
  - strategy logic
  - strategy parameters
  - strategy code generation prompts
  - strategy evaluation inputs
- when adding or revising a strategy, avoid changing:
  - workflow phase order
  - report/history contracts
  - monitoring contracts
  - validation protocol shape
  - API flow unless the existing interface is provably insufficient

Production platform rule:

- future strategy work should usually not require changes to:
  - execution state machine
  - risk-control contracts
  - auth and audit contracts
  - monitoring and alerting contracts
  - backup and restore procedures

The system should behave as a general strategy platform where new strategy families plug into a fixed operating process.

## Dataset Protocol Rule

Training data, validation data, and comparison data must follow a canonical protocol rather than ad hoc per-strategy handling.

Required rule:

- each strategy cycle must define a `dataset_plan`
- the canonical protocol is:
  - `train`
  - `validation`
  - `test`
  - `walk_forward_windows`
- baseline and every candidate variant must be evaluated under the same protocol
- recommendation should prefer the strongest test-set objective score, not just the in-sample score
- the workflow must preserve:
  - train objective score
  - validation objective score
  - test objective score
  - walk-forward score
  - stability score
  - train-test gap
- stress and overfit checks must be allowed to reject a candidate because of:
  - low out-of-sample score
  - excessive train-test gap
  - weak walk-forward stability
- this protocol is workflow-level infrastructure and should not be rewritten per strategy
- if a strategy needs a custom feature set, only the feature logic should change; the dataset protocol should remain fixed unless the product architecture itself changes

## Production Readiness Rule

The workflow is not production-ready until all of the following exist as platform capabilities:

- real broker or exchange execution
- stable order lifecycle and reconciliation
- production risk controls:
  - account loss limits
  - drawdown limits
  - position and concentration limits
  - kill switches
- stable data engineering:
  - scheduled ingestion
  - bad-data handling
  - schema validation
  - dedupe and weighting persistence
  - historical versioning
- authentication and authorization
- audit logs for:
  - configuration changes
  - strategy approvals
  - execution-mode changes
  - code mutation tasks
- backup, restore, and migration procedures
- alerting and operator runbooks

Required design rule:

- these are platform-level concerns
- they must be solved generically once, not re-implemented separately per strategy family

## Architecture Rule

The system architecture must remain explicit and layered:

- simulation layer:
  - `Scenario Director`
  - `Noise Agent`
  - `Behavioral Profiler`
- synthesis layer:
  - `Intelligence Agent`
  - `Strategy Evolver`
  - `Intent Aligner`
  - mandatory strategy-check agents
- execution layer:
  - `Portfolio Manager`
  - `Risk Guardian`
- supervision layer:
  - `User Monitor Agent`
  - `Strategy Monitor Agent`
  - `Market and Asset Monitor Agent`

Storage responsibilities must remain split by data type:

- PostgreSQL:
  - user records
  - workflow sessions
  - behavioral reports
  - strategy iterations
  - strategy feedback logs
  - deployment settings
  - monitor snapshots
  - trade execution records
  - profile evolution events
- TimescaleDB:
  - historical market replay points
  - live market snapshots
  - simulation behavior traces
- Qdrant:
  - behavioral memory
  - strategy rationale memory
  - profile evolution memory
  - website intelligence memory
- Redis:
  - runtime agent events
  - transient strategy cache

Do not collapse these responsibilities into a single generic persistence layer unless the task explicitly changes architecture.

## Profile Evolution Rule

User personality is not a one-time test artifact.

The effective user trading profile must be allowed to evolve from:

- simulation behavior
- strategy training feedback
- later manual trade behavior
- later automated execution outcomes
- monitoring drift signals where applicable

## History Rule

Everything important must leave an auditable trace.

Required rule:

- do not keep only the latest state when the event has decision value
- the system must preserve history for:
  - behavioral reports
  - strategy iteration reports
  - intelligence summaries
  - strategy feedback
  - trade records
  - market snapshots
  - monitor outputs
  - profile evolution events
- reports must be archived, not silently overwritten
- history entries must preserve timestamp, phase, event type, and a structured payload
- intelligence history must preserve raw source URLs alongside the summarized report
- user feedback must be visible in:
  - strategy feedback history
  - report archives
  - history timeline
- report pages must not only show the current profiler output; they must also replay:
  - user feedback
  - feedback-to-training outcomes
  - latest strategy research conclusion
  - latest data-bundle quality context
  - latest release snapshot
  - latest research trend summary
  - latest research health conclusion

## Cross-Page Repair Routing Rule

The user should not have to infer manually where to go next after discovering a problem.

Required rule:

- report, intelligence, system-health, and configuration pages should expose direct navigation back to the relevant repair surface
- when possible, page-to-page jumps should preserve a target focus so the destination page can auto-focus the relevant panel
- examples of valid repair targets:
  - strategy research summary
  - strategy repair routing
  - strategy research/code loop
  - configuration provider section
- a task that adds diagnostics without a path back to repair is incomplete

## Research Presentation Rule

Strategy research output is incomplete if the user still has to manually infer whether research quality is improving or deteriorating.

Required rule:

- strategy and report pages must surface:
  - latest research summary
  - release snapshot
  - research trend summary
  - research health conclusion
  - repair trend summary
- research health should compress:
  - gate
  - robustness
  - test trend
  - walk-forward trend
  - train-test gap trend
  into a direct conclusion such as:
  - `healthy`
  - `warning`
  - `fragile`
- repair trend should compress:
  - latest primary repair lane
  - recent repair-lane distribution
  - recent priority movement
  - recent source movement
  into a direct conclusion such as:
  - `converging`
  - `flat`
  - `diverging`
- unified repair routing must be archived, not computed only in the browser:
  - `research_summary.repair_route_summary`
  - `training_log_entry.repair_route_summary`
  - `research_export.repair_route_summary`
  - `research_export.primary_repair_route`
  - `history_events.payload.repair_route_lane`
  - `history_events.payload.repair_route_priority`
- strategy-iteration history events should preserve enough payload to replay:
  - winner
  - gate
  - evaluation source
  - robustness grade
  - train objective score
  - validation objective score
  - test objective score
  - walk-forward score
  - primary repair route lane
  - primary repair route priority
  - train-test gap
- strategy-iteration report archives should preserve a stable `research_export` payload so the strategy and report pages read the same research contract

## Intelligence Rule

`Intelligence Agent` is allowed to search configured public websites and feeds, but the source selection must come from configuration, not from hardcoded URLs in business logic.

Required behavior:

- site and feed templates must be defined in config
- fetched documents must be normalized into structured intelligence records
- fetched documents must be attached to workflow state
- fetched documents should be stored in PostgreSQL as session intelligence records
- fetched documents should be embedded into Qdrant for semantic reuse
- fetched intelligence may inform strategy synthesis, but raw source provenance must be preserved

At minimum, any implementation touching workflow persistence must preserve or extend:

- `behavioral_report`
- `profile_evolution`
- `strategy_feedback_log`
- `trade_records`
- `market_snapshots`

## Phase 1: First-Run Behavioral Mapping

### Goal

Measure the user's actual trading personality through behavior under pressure.

### Required sequence

1. Initialize a new user session.
2. Generate or load scenario packages.
3. Run simulated trading scenarios with:
   - price path
   - aligned or divergent noise
   - hidden ground truth
4. Record all user actions and timing.
5. Convert behavior into a profiler report.

### Required agents

- `Scenario Director`: choose and sequence the scenarios
- `Noise Agent`: inject narrative pressure
- `Behavioral Profiler`: score the user's behavior

### Minimum scenario coverage

Use the six core torture scenarios:

- `uptrend`
- `gap`
- `oscillation`
- `drawdown`
- `fake_reversal`
- `downtrend`

Each scenario should support:

- `pressure` cohort
- `control` cohort where relevant

### Required report outputs

The profiler report should at minimum include:

- `loss_tolerance`
- `noise_sensitivity`
- `panic_sell_tendency`
- `bottom_fishing_tendency`
- `hold_strength`
- `overtrading_tendency`
- `max_drawdown_endured`
- `recommended_risk_ceiling`

Do not end Phase 1 with only charts or raw logs. Always produce a structured Behavioral Profiler report.

## Phase 2: Trade Universe Intake

Before trade universe intake, force a structured trading rhythm choice.

Required user choices:

- trading frequency:
  - `low`
  - `medium`
  - `high`
- preferred timeframe:
  - `minute`
  - `daily`
  - `weekly`

Do not rely on vague language like "trade whenever there is an opportunity." Force the user to choose a practical execution rhythm and explain the implications.

### Goal

Constrain strategy training to the assets the user actually wants to trade.

### Input types

Allow the user to provide:

- individual stocks
- ETFs
- sectors or themes

### Overfitting guardrail

Do not train on a universe smaller than `5` tradeable objects unless the user explicitly overrides it.

Preferred interpretation:

- at least `5` stocks, or
- at least `5` ETFs, or
- a sector/theme basket that expands to at least `5` liquid instruments

If the user gives fewer than `5`, expand the universe by:

1. highly correlated peers
2. same-sector leaders
3. benchmark ETFs

Record the expansion logic explicitly.

## Minimum Universe Rule

Default minimum is `5` tradeable objects.

Reason:

- fewer than `5` objects makes the synthesis loop too easy to overfit
- the strategy evolver needs cross-asset variation to test robustness
- the monitoring layer also needs a meaningful comparison set

Only allow fewer than `5` if the user explicitly accepts the overfitting risk.

## Phase 3: Strategy Synthesis

### Goal

Generate user-aligned strategies, not raw-return-maximizing strategies.

### Required inputs

- Behavioral Profiler report
- chosen trade universe
- market intelligence
- user feedback during training

### Required agents

- `Intelligence Agent`
- `Strategy Evolver`
- `Intent Aligner`

### Iteration loop

For each strategy iteration:

1. Build candidate strategy rules for the chosen universe.
2. Stress the strategy against the user's behavioral limits.
3. Check where the user is likely to intervene or break discipline.
4. Let the user provide feedback during training.
5. Recompute risk penalties and position limits.
6. Regenerate the next strategy candidate.
7. Run both strategy-check agents before the version can be approved.

### User feedback handling

During training, accept natural-language feedback such as:

- "I don't want that much drawdown."
- "Reduce concentration."
- "I only trust large-cap tech."
- "Avoid trading around earnings."

`Intent Aligner` must translate this into updated strategy constraints.

### Required outputs

At the end of synthesis, provide:

- expected return range
- maximum potential loss
- expected drawdown
- position concentration limits
- probability summary
- behavioral compatibility summary

The strategy package should be iterated until one of the following is true:

- the user approves the current version
- the user stops training
- the system reaches a defined iteration cap and requests manual review

### Mandatory strategy checks

Before a strategy version is approvable, always run:

#### 1. Strategy Integrity Checker

Checks:

- future leakage
- lookahead bias
- cheating patterns
- impossible hindsight logic
- explicit or hidden win-coding

#### 2. Strategy Stress and Overfit Checker

Checks:

- stress scenarios
- walk-forward stability
- overfit risk
- parameter sensitivity
- regime robustness

Do not allow strategy approval unless both checks are at least acceptable.

## Phase 4: Deployment Choice

### Goal

The user must explicitly choose how much execution authority the system receives.

### Supported modes

#### 1. Autonomous Trading

Use when the user confirms execution authority.

Required agents:

- `Portfolio Manager`
- `Risk Guardian`

System behavior:

- execute the approved strategy
- enforce hard risk limits from the profiler report
- accept mid-course user feedback
- continuously compare real behavior against prior behavioral mapping
- continuously feed monitoring signals into execution decisions

#### 2. Advice-Only Mode

Use when the user disables autonomous trading.

System behavior:

- do not place trades
- only output signals, risk warnings, and allocation suggestions
- still update behavioral understanding from user reactions if available
- keep monitoring active even when execution is disabled

## Phase 5: Continuous Monitoring

### Goal

Observe the live system from three different angles after strategy generation, regardless of whether the system is in autonomous mode or advice-only mode.

### Required monitoring agents

#### 1. User Monitor Agent

Purpose:

- monitor the user's real behavior against the prior Behavioral Profiler report

Responsibilities:

- compare current reactions with historical behavioral traits
- detect panic overrides, impulsive manual interventions, confidence drops, and hesitation spikes
- flag when the user's current state deviates materially from the profiled baseline
- trigger re-testing when the user encounters an untested stress pattern

Typical outputs:

- user confidence drift
- intervention risk drift
- re-test recommendation

#### 2. Strategy Monitor Agent

Purpose:

- monitor whether the currently deployed strategy is still behaving as designed

Responsibilities:

- track drawdown, hit rate, concentration, turnover, and slippage drift
- detect behavioral mismatch between the strategy and the user
- detect degradation, parameter instability, or regime mismatch
- recommend retraining, rollback, or reduced position limits

Typical outputs:

- strategy health score
- degradation alert
- retrain recommendation

#### 3. Market and Asset Monitor Agent

Purpose:

- monitor the external market and the specific stocks, ETFs, or sectors the user selected

Responsibilities:

- watch macro conditions, volatility regime, event risk, earnings windows, liquidity stress, and sector rotation
- watch the selected trade universe continuously
- detect when the market regime has shifted away from the assumptions used in synthesis
- feed these changes back into Strategy Evolver, Risk Guardian, and Intent Aligner

Typical outputs:

- market regime label
- event risk alerts
- watched-universe status changes

### Monitoring rule

Monitoring is always on after strategy generation.

- In autonomous mode, monitoring can directly constrain execution.
- In advice-only mode, monitoring only changes the recommendations and warnings.

## Product-Level Guardrails

- The simulation UI should feel like a real trading system because the Behavioral Profiler needs real trading-like behavior.
- The final output of the testing stage is a profiler report, not merely a score or a dashboard.
- The final output of the strategy stage is a user-aligned strategy package, not just backtest performance.
- The final system must always support a non-autonomous advice-only fallback.
- The monitoring layer must remain active after deployment mode is selected.
- The user monitor, strategy monitor, and market/asset monitor must be treated as separate concerns.

## Implementation Checklist

When implementing or reviewing this workflow, verify all of the following:

- first-run flow exists
- scenario generation exists
- simulated trading capture exists
- Behavioral Profiler report exists
- minimum trade universe guardrail exists
- iterative strategy loop accepts user feedback
- deployment mode selection exists
- autonomous trading can be disabled
- user monitor agent exists
- strategy monitor agent exists
- market and asset monitor agent exists
- monitoring remains active in advice-only mode
- strategy integrity checker exists
- strategy stress and overfit checker exists
- strategy approval is blocked if a check fails

## Default Data Handoff

Use this handoff structure between phases:

### Phase 1 -> Phase 2

```json
{
  "user_id": "U12345",
  "behavioral_profile": {
    "loss_tolerance": -18.5,
    "noise_sensitivity": 0.82,
    "panic_sell_tendency": 0.71,
    "bottom_fishing_tendency": 0.64,
    "hold_strength": 0.33,
    "overtrading_tendency": 0.58,
    "max_drawdown_endured": 22.0,
    "recommended_risk_ceiling": 0.35
  }
}
```

### Phase 2 -> Phase 4

```json
{
  "user_id": "U12345",
  "selected_universe": ["TSLA", "NVDA", "QQQ", "SOXX", "SMH"],
  "strategy_package": {
    "expected_return_range": [0.12, 0.24],
    "max_potential_loss": -0.14,
    "expected_drawdown": -0.09,
    "position_limit": 0.18,
    "behavioral_compatibility": 0.81
  },
  "execution_mode": "autonomous_or_advice_only",
  "monitoring": {
    "user_monitor": "active",
    "strategy_monitor": "active",
    "market_asset_monitor": "active"
  }
}
```

- Backtest quality signals such as concentration, exposure, and turnover should be treated as first-class research constraints, not only display metrics

- Programmer Agent results should expose a unified repair_chain_summary so chain-level decisions do not require manual stitching across multiple sub-summaries

- terminal integration results should expose a unified terminal_reliability_summary so long-running terminal decisions do not require manual stitching across readiness, runtime, and smoke-test summaries

- research results should expose a unified research_reliability_summary so users do not need to manually stitch trust signals across coverage, binding, quality, and robustness blocks

- runtime-health outputs should expose a unified runtime_recovery_summary so long-running decisions do not require manual stitching across five module summaries
