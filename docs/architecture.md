# Sentinel-Alpha Initial Architecture

## License

This architecture and the repository implementation are distributed under the Apache License 2.0.

- [LICENSE](/Users/harry/Documents/git/Sentinel-Alpha/LICENSE)

## Design Principle

The framework treats trading as a joint optimization problem across:

- market opportunity
- user behavioral stability
- intervention risk
- hard safety limits

An additional architectural rule now applies:

- strategy logic is pluggable
- workflow infrastructure is stable

This means future strategy families should normally plug into the existing workflow instead of forcing rewrites to:

- phase order
- monitoring contracts
- archival contracts
- approval gates
- dataset protocol

## Phase Model

### Phase 1: Behavioral Mapping

- `ScenarioDirectorAgent`: replays market stress regimes and synthetic volatility paths
- `NoiseAgent`: injects narrative pressure, conflicting commentary, and urgency cues
- `BehavioralProfilerAgent`: converts observed user actions into quantified behavioral traits

Primary output:

- behavioral bias scores
- intervention likelihood
- drawdown pain threshold
- noise susceptibility

### Phase 2: Strategy Synthesis

- `IntelligenceAgent`: supplies market priors, volatility estimates, factor summaries, and event context
- `StrategyEvolverAgent`: transforms market priors and behavioral traits into aligned trading constraints
- `IntentAlignerAgent`: updates policy when user intent or confidence changes
- `ProgrammerAgent`: applies controlled local code mutation for strategy implementation, self-repair, and diff/commit capture

This phase now includes an explicit LLM routing layer:

- agent-level routing
- task-level routing
- multi-model strategy analysis
- multi-model strategy code generation
- multi-model strategy critique

Primary output:

- expected return estimate
- worst-case drawdown estimate
- intervention-aware position sizing
- user-aligned utility score
- generated strategy code artifact
- strategy training log
- archived strategy iteration report
- programmer-run diff and commit trace

### Phase 3: Execution

- `PortfolioManagerAgent`: applies capital allocation and execution policy
- `RiskGuardianAgent`: enforces non-negotiable constraints and halts unsafe actions

Primary output:

- approved order instructions
- hard-stop events
- post-trade learning records

## Shared State Model

The initial codebase uses a single shared state abstraction:

- `UserProfile`: stable preferences and live confidence
- `BehavioralReport`: measured behavioral tendencies from simulation
- `RiskPolicy`: machine-enforceable limits derived from the behavioral report
- `MarketSnapshot`: simplified market features for strategy synthesis
- `StrategyBrief`: end-user summary of the personalized strategy

## Infrastructure Mapping

| Layer | Tech | Responsibility | Example Data |
| --- | --- | --- | --- |
| Relational | `PostgreSQL` | durable transactional records | users, account balances, order states, strategy approvals |
| Time-Series | `TimescaleDB` | market and behavior sequences | 10-year 1-minute bars, simulated action traces, live PnL curves |
| Vector | `Qdrant` | semantic retrieval and profile memory | behavioral profile embeddings, financial news chunks, strategy motifs |
| Cache | `Redis` | low-latency coordination | quote cache, agent queues, session state, circuit-breaker signals |
| Orchestration | `LangChain` | agent chains and narrative generation | retrieval-augmented summaries, intent updates, explanation chains |

The persistence split is deliberate:

- `PostgreSQL` handles correctness and auditable state transitions.
- `TimescaleDB` handles dense temporal data without overloading transactional tables.
- `Qdrant` handles semantic recall for personalized memory and market context.
- `Redis` handles short-lived operational speed paths.

## LLM Routing

The framework should not assume that one model is optimal for every task.

Current routing layers:

- agent routing:
  - `Intent Aligner`
  - `Noise Agent`
  - `Behavioral Profiler`
  - `Intelligence Agent`
  - `Strategy Evolver`
- task routing:
  - `intent_translation`
  - `noise_generation`
  - `behavior_analysis`
  - `market_summarization`
  - `strategy_analysis`
  - `strategy_codegen`
  - `strategy_critic`

The current codebase supports configuration-driven per-agent and per-task model routing through `config/settings.toml`.

The strategy layer now exposes the resolved model map through workflow state so every strategy version can be audited for:

- which agent route was configured
- which task route was configured
- which model family planned the strategy code artifact
- whether the run was live-model or fallback-mode

## Critical Research Interface

The first research question implemented here is:

How should irrational behavior observed in simulation become dynamic stop-loss and sizing constraints?

Current mapping:

- stronger loss aversion lowers max position size
- stronger panic selling lowers tolerated drawdown
- stronger noise susceptibility lowers confidence in narrative-driven setups
- stronger averaging-down tendency increases stop discipline and cool-down windows

This mapping is intentionally explicit and inspectable instead of hidden inside a black-box optimizer.

## Strategy Training Loop

Strategy synthesis is a loop, not a single function call.

Current iteration modes:

- `guided`
  - continue iterating within the requested loop budget until a version passes mandatory checks
- `free`
  - continue iterating for the requested loop budget even if a version already passes, so the user can keep exploring

Every iteration should produce:

- a new strategy version
- strategy package metadata
- generated strategy code artifact
- dataset plan
- integrity-check result
- stress/overfit-check result
- strategy training log entry
- archived report snapshot

The canonical dataset protocol for strategy comparison is:

- `train`
- `validation`
- `test`
- `walk_forward_windows`

`baseline` and every candidate variant must be evaluated under the same protocol.

The workflow should preserve at least:

- train objective score
- validation objective score
- test objective score
- walk-forward score
- stability score
- train-test gap

The approval logic should prefer:

1. stronger test-set objective score
2. acceptable validation behavior
3. acceptable walk-forward stability
4. selecting the current best version under the dataset protocol
5. passing integrity and stress/overfit checks on that selected version

If code-level strategy mutation is required, `ProgrammerAgent` may be invoked after `StrategyEvolverAgent` produces the change request and before the next validation loop starts.

`ProgrammerAgent` must preserve:

- changed files
- git diff
- commit hash
- rollback commit

If any required strategy check fails, the workflow must remain in rework state until a later iteration passes.

## Stimulus Matrix

Each simulation package should be tagged across three coordinated dimensions:

| Dimension | Contents | Purpose |
| --- | --- | --- |
| `P` Price | tick path, candles, volatility, gap pattern | measure physical tolerance to profit and loss |
| `N` Narrative | news snippets, comments, analyst takes | measure susceptibility to noise and persuasion |
| `T` Truth | hidden fundamentals and eventual outcome | evaluate whether the user's action was directionally correct |

## Canonical Playbooks

- `uptrend`: steady stair-step rise plus bubble warnings
- `gap`: jump opening with contradictory event headlines
- `oscillation`: repeated false breaks with alternating narratives
- `drawdown`: deep grind lower with abandonment and insolvency rumors
- `fake_reversal`: bear-market rally with bottom-call propaganda
- `downtrend`: persistent decline with rationalized bearish explanations

For A/B testing, each playbook supports:

- `pressure`: price plus synchronized or divergent narrative manipulation
- `control`: the same price path with narrative removed

## Behavioral Logging

The behavioral capture layer should store action context, not only orders:

- price at action
- last observed narrative sentiment
- simulated stress proxy
- floating PnL at action
- control or pressure cohort label

See [behavioral_log.sql](/Users/harry/Documents/git/Sentinel-Alpha/sql/behavioral_log.sql) and [scenario_generator.py](/Users/harry/Documents/git/Sentinel-Alpha/src/sentinel_alpha/research/scenario_generator.py).

## Fake Reversal Collaboration Logic

The `fake_reversal` playbook is the most behaviorally diagnostic:

- `ScenarioDirectorAgent` creates a sequence of sharp losses, a convincing rebound, then fresh lows.
- `NoiseAgent` turns aggressively bullish during the rebound window and bearish again after re-failure.
- `BehavioralProfilerAgent` computes:
  - bottom-fishing frequency
  - action frequency under stress
  - deception score during counter-trend rallies

The current implementation exposes this through `ScenarioGenerator.assess_fake_reversal(...)`.
