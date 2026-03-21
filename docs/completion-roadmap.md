# Completion Roadmap

This document defines what "complete" means for `Sentinel-Alpha`, what is already present, and what still remains before the system can be considered production-ready instead of a research-grade platform prototype.

## Current Status

Current maturity:

- `research platform prototype`
- `high-fidelity product skeleton`
- `not yet production-ready`

The system already has:

- multi-agent workflow structure
- skills and platform contracts
- split frontend pages
- system-health and observability hooks
- configurable market-data providers
- multi-model LLM routing
- strategy iteration history and report archive
- programmer-agent and data-source-expansion-agent integration
- in-memory and incremental performance optimizations

The system does not yet have:

- a production-grade backtesting and evaluation engine
- fully hardened live LLM provider execution across all critical agents
- a closed-loop auto-repair code mutation pipeline that iterates until success
- a polished, institution-grade simulation terminal
- full production infrastructure validation under persistent deployment
- real broker/exchange execution and order-state management
- production-grade risk controls and account-level guardrails
- hardened data engineering pipelines for market, fundamentals, options, and dark-pool feeds
- full authentication, authorization, and audit coverage
- production dashboards, alerting rules, and operational runbooks
- deployment-grade backup, restore, migration, and disaster-recovery procedures

## Completion Criteria

The system should only be called "complete" when all of the following are true:

1. Strategy evaluation is based on real historical market data with proper backtest execution.
2. `train / validation / test / walk_forward` are enforced by a real evaluation engine rather than only rule-based surrogate scoring.
3. Critical agents can run against live configured LLM providers with stable error handling and observability.
4. Strategy-code generation, checking, mutation, validation, and rollback form a closed and auditable loop.
5. The user simulation environment is realistic enough to produce usable behavioral signals.
6. Persistent deployment works end-to-end with PostgreSQL, TimescaleDB, Redis, and Qdrant.
7. Monitoring can pinpoint failures at the levels of API, library, agent, provider, data source, and code-generation task.
8. Live trading execution, risk controls, and user/account permissions are enforceable and auditable.
9. Market data, fundamentals, options, and dark-pool pipelines are versioned, validated, and recoverable.
10. Production deployment includes alerting, incident diagnosis, backup, restore, and rollback procedures.

## P0 Must Finish

These are the items required before claiming the core system is functionally complete.

### 1. Real Backtest Engine

Need:

- real OHLCV ingestion into evaluation
- trade-by-trade simulation
- slippage and fee modeling
- position accounting
- per-split evaluation on real data

Why:

- current strategy comparison still relies heavily on structured heuristic evaluation
- the platform has the evaluation protocol shape, but not the full engine behind it

### 2. Real Train/Validation/Test/Walk-Forward Execution

Need:

- true time-based split runner
- walk-forward training windows on real data
- baseline vs variant A vs variant B on identical data windows
- strict out-of-sample reporting

Why:

- current protocol contract exists and is stable
- but the engine underneath must become real before strategies can be trusted

### 3. Programmer Agent Closed Loop

Need:

- compile/test after each code change
- automatic error summarization
- automatic retry prompt regeneration
- bounded retry loop
- stable rollback to the last known-good commit

Why:

- current programmer-agent path records errors well
- but it does not yet self-repair until success

### 4. Live LLM Provider Hardening

Need:

- provider-specific runtime handling for OpenAI / Anthropic / Gemini or chosen providers
- retry policy
- timeout policy
- provider error normalization
- token and cost accounting per task

Why:

- current routing is present
- but live execution still depends on configuration completeness and fallback behavior

### 5. Simulation Engine Usability

Need:

- realistic multi-segment intraday flow
- better chart realism and stress patterns
- stable order-entry model
- more convincing noise/news/discussion dynamics

Why:

- the simulation is usable for iteration
- but not yet strong enough to claim robust behavioral inference in production

### 6. Real Trading Execution

Need:

- broker or exchange adapter integration
- order creation, amendment, cancellation, and reconciliation
- broker callback ingestion and state synchronization
- idempotent order submission and retry handling
- execution failure recovery and manual takeover path

Why:

- a trading platform is not production-ready without a real execution state machine
- strategy output must map cleanly into auditable live orders

### 7. Production Risk Controls

Need:

- account-level max loss and max drawdown guardrails
- per-order, per-symbol, and per-day exposure limits
- hard kill switches and deployment freeze controls
- autonomous mode permission boundaries
- manual override and emergency flat-position flow

Why:

- risk enforcement must exist independently from strategy quality
- production trust requires deterministic safety controls

### 8. Authentication, Authorization, and Audit

Need:

- user identity and session authentication
- role and permission boundaries
- config-change audit logs
- strategy-approval audit logs
- execution-mode change audit logs

Why:

- production systems need traceability for who changed what and when
- live trading and configuration changes must not be anonymous

### 9. Data Engineering Hardening

Need:

- scheduled ingestion and refresh jobs
- bad-data detection and quarantine
- schema validation and provider normalization
- dedupe and weighting persistence
- historical versioning of imported data

Why:

- strategy quality and intelligence quality are capped by data quality
- production behavior cannot depend on ad hoc imports alone

### 10. Monitoring, Alerting, and Runbooks

Need:

- Grafana dashboards with production views
- Prometheus alert rules
- Sentry issue routing
- LangFuse trace review workflow
- documented incident response runbooks

Why:

- production readiness requires operators to know exactly where failures happen and how to respond

## P1 Strongly Recommended Before Launch

### 1. Persistent Infra End-to-End Verification

Need:

- PostgreSQL
- TimescaleDB
- Redis
- Qdrant
- Docker persistent profile validation with real smoke tests

### 2. Provider Reliability Layer

Need:

- per-provider retry and circuit-breaker policy
- response schema validation
- stale-data detection
- provider failover policy

### 3. Frontend Product Hardening

Need:

- skeleton loading states
- more partial rendering
- lower-noise UI hierarchy
- better simulation and strategy-lab ergonomics

### 4. Historical Replay Library Completion

Need:

- real daily and intraday template library populated
- regime coverage validation
- shape coverage validation

### 5. Alerting and Diagnostics Improvement

Need:

- response-time tracking
- slow-endpoint tracking
- per-agent phase states
- richer failure drill-down in the system-health page

### 6. Backup, Restore, and Migration Discipline

Need:

- database backup policy
- restore validation
- schema migration discipline
- startup and rollback playbooks

### 7. Frontend Operations Console Completion

Need:

- dedicated orders page
- holdings page
- risk page
- alert center
- exportable reports

### 8. Security Hardening

Need:

- secret handling review
- API rate limiting
- secure config update boundaries
- sandbox rules for code mutation and provider expansion

## P2 Research and Product Enhancements

### 1. More Strategy Families

- regime switching
- stat arb aligned variants
- options overlay strategies

### 2. More Behavioral Signals

- language hesitation markers
- intervention timing patterns
- sentiment drift over training history

### 3. Better Intelligence Fusion

- provider-level credibility weighting
- multi-source contradiction analysis
- event clustering and persistence

### 4. More Advanced Auto-Coding Flow

- branch-per-experiment flow
- richer git diff review
- automatic patch ranking

## Platform Rule

The platform direction should remain:

- users mainly change strategy logic
- platform workflow stays stable
- storage contracts stay stable
- monitoring contracts stay stable
- report/archive/history contracts stay stable

This means future changes should usually be isolated to:

- strategy logic
- strategy parameters
- strategy prompts
- provider configuration
- evaluation engine internals
- execution adapters
- provider adapters

not to:

- page structure
- workflow order
- report shapes
- history archive contract
- approval gates
- risk and audit contracts

## Suggested Build Order

Recommended order from here:

1. real backtest engine
2. real split and walk-forward execution
3. real trading execution state machine
4. production risk controls
5. programmer-agent self-repair loop
6. live LLM provider hardening
7. simulation realism upgrade
8. data engineering hardening
9. persistent deployment full smoke verification
10. auth, audit, and security hardening
11. observability dashboards and runbooks
12. frontend product hardening

## Short Verdict

Current answer to "is the project complete?":

- `complete as a platform prototype`: yes
- `complete as a production system`: no

Current best label:

- `MVP+ research platform`
