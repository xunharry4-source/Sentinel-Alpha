---
name: sentinel-alpha-workflow
description: Use when working on Sentinel-Alpha's full operating workflow: first-run onboarding, test-data generation, simulated trading for behavioral profiling, profiler report output, target universe intake, iterative strategy generation with user feedback, deployment mode selection, and the three monitoring agents for user behavior, strategy health, and market/asset state.
---

# Sentinel-Alpha Workflow

Use this skill when the task concerns the full product flow of Sentinel-Alpha rather than an isolated module.

## Core Rule

Treat the product as a behavior-aligned trading system, not a generic backtester and not a questionnaire.

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
- database initialization must come from tracked SQL files, not manual undocumented steps
- Docker documentation must state both memory-mode and persistent-mode startup paths

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
