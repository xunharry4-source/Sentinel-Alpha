# Sentinel-Alpha Database Spec

## Goal

Persist the full product workflow:

1. onboarding
2. simulation
3. behavioral profiling
4. trade universe intake
5. strategy iteration
6. deployment mode selection
7. continuous monitoring

## Storage Mapping

### PostgreSQL

Transactional system-of-record:

- users
- workflow sessions
- trade universe requests
- profiler reports
- strategy iterations
- deployment settings
- monitor alerts
- intelligence search results

### TimescaleDB

High-frequency or sequence data:

- scenario price paths
- user behavior events
- live strategy metrics
- watched market snapshots

### Qdrant

Semantic memory:

- behavioral report embeddings
- user feedback during strategy training
- market narrative chunks
- strategy rationale snapshots
- public website intelligence chunks

### Redis

Runtime layer:

- active session state
- monitor event fan-out
- near-real-time strategy health
- workflow locks and TTL queues

## Core Tables

### `users`

- `id uuid primary key`
- `created_at timestamptz`
- `display_name text`
- `risk_consent_version text`
- `default_execution_mode text`

### `workflow_sessions`

- `id uuid primary key`
- `user_id uuid not null`
- `status text not null`
- `phase text not null`
- `created_at timestamptz`
- `updated_at timestamptz`
- `selected_execution_mode text`

### `scenario_runs`

- `id uuid primary key`
- `session_id uuid not null`
- `scenario_id text not null`
- `playbook text not null`
- `cohort text not null`
- `started_at timestamptz`
- `completed_at timestamptz`

### `behavioral_reports`

- `id uuid primary key`
- `session_id uuid not null unique`
- `loss_tolerance double precision`
- `noise_sensitivity double precision`
- `panic_sell_tendency double precision`
- `bottom_fishing_tendency double precision`
- `hold_strength double precision`
- `overtrading_tendency double precision`
- `max_drawdown_endured double precision`
- `recommended_risk_ceiling double precision`
- `archetype text`
- `report_json jsonb not null`

### `trade_universe_requests`

- `id uuid primary key`
- `session_id uuid not null`
- `input_type text not null`
- `symbols jsonb not null`
- `expanded_symbols jsonb not null`
- `expansion_reason text`
- `minimum_universe_size integer not null`

### `strategy_iterations`

- `id uuid primary key`
- `session_id uuid not null`
- `iteration_no integer not null`
- `user_feedback text`
- `candidate_json jsonb not null`
- `behavioral_compatibility double precision`
- `approved boolean not null default false`
- `created_at timestamptz`

### `deployment_settings`

- `session_id uuid primary key`
- `execution_mode text not null`
- `autonomous_enabled boolean not null`
- `advice_only boolean not null`
- `confirmed_at timestamptz`

### `monitor_signals`

- `id uuid primary key`
- `session_id uuid not null`
- `monitor_type text not null`
- `severity text not null`
- `title text not null`
- `payload jsonb not null`
- `created_at timestamptz`

### `intelligence_documents`

- `id uuid primary key`
- `session_id uuid not null`
- `query text not null`
- `source text not null`
- `title text not null`
- `url text not null`
- `published_at text`
- `payload jsonb not null`
- `created_at timestamptz`

## Sequence Data

### `scenario_price_points`

Timescale hypertable keyed by:

- `scenario_run_id`
- `event_ts`

### `user_behavior_events`

Timescale hypertable keyed by:

- `session_id`
- `event_ts`

### `strategy_health_timeseries`

Timescale hypertable keyed by:

- `session_id`
- `event_ts`

### `market_asset_snapshots`

Timescale hypertable keyed by:

- `session_id`
- `symbol`
- `event_ts`
