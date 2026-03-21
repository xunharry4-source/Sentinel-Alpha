# Sentinel-Alpha Agent State Machine

## Core Agent Catalog

| Agent | Core Responsibility | Key Capabilities |
| --- | --- | --- |
| `Scenario Director` | orchestrate simulated environments and replay extreme episodes such as crash regimes and grinding declines | time-series generation, historical fragment replay |
| `Noise Agent` | simulate social/news noise and publish misleading bullish or bearish narratives during simulation | financial NLP, deceptive content generation, persuasive dialogue |
| `Behavioral Profiler` | analyze user actions during simulation and detect cognitive biases such as bag-holding, chasing, or noise sensitivity | behavioral feature extraction, psychological quantification, clustering |
| `Intelligence Agent` | collect live macro data, company fundamentals, and technical factors | API integration, RAG retrieval |
| `Strategy Evolver` | generate and refine personalized strategies from behavior, market inputs, and user feedback | reinforcement learning, genetic optimization, Monte Carlo simulation |
| `Portfolio Manager` | allocate capital, submit orders, and rebalance positions when execution is enabled | MPT, VWAP, TWAP |
| `Intent Aligner` | translate ambiguous user intent into explicit constraints and risk prompts | LLM semantic parsing, structured reasoning, affect-aware interpretation |
| `Risk Guardian` | enforce hard stop conditions derived from the user's stress boundary | coded constraint validation, real-time anomaly detection |

The monitoring layer extends this core with:

- `User Monitor Agent`
- `Strategy Monitor Agent`
- `Market and Asset Monitor Agent`

The strategy validation layer adds:

- `Strategy Integrity Checker`
- `Strategy Stress and Overfit Checker`

## Session State Machine

```text
created
  -> scenarios_generated
  -> simulation_in_progress
  -> profiler_ready
  -> universe_ready
  -> strategy_training
  -> strategy_checked
  -> strategy_rework_required
  -> strategy_approved
  -> autonomous_active | advice_only_active
```

## Agent Participation by Phase

### `created`

- Intent Aligner initializes user context

### `scenarios_generated`

- Scenario Director selects scenario catalog
- Noise Agent prepares aligned narrative interference

### `simulation_in_progress`

- User interacts with the simulation UI
- Behavioral Profiler consumes event stream

### `profiler_ready`

- Behavioral Profiler emits structured risk personality report

### `universe_ready`

- Intelligence Agent expands the requested universe if needed
- Intent Aligner records any user constraints

### `strategy_training`

- Strategy Evolver produces candidates
- Intelligence Agent provides market context
- Intent Aligner applies user feedback

### `strategy_checked`

- Strategy Integrity Checker validates anti-lookahead, anti-cheat, and anti-win-coding constraints
- Strategy Stress and Overfit Checker validates stress robustness and overfit resistance

### `strategy_rework_required`

- at least one strategy check failed
- Strategy Evolver must generate a new version before approval can be attempted again

### `strategy_approved`

- Strategy candidate becomes deployable only after both check agents return acceptable results

### `autonomous_active`

- Portfolio Manager executes
- Risk Guardian enforces hard limits
- User Monitor Agent watches user behavior drift
- Strategy Monitor Agent watches strategy degradation
- Market and Asset Monitor Agent watches macro and watched symbols

### `advice_only_active`

- Portfolio Manager does not execute
- Risk Guardian still evaluates recommendations
- all three monitor agents remain active
