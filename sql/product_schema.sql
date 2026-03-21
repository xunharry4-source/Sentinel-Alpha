create table if not exists users (
    id uuid primary key,
    created_at timestamptz not null default now(),
    display_name text not null,
    risk_consent_version text,
    default_execution_mode text
);

create table if not exists workflow_sessions (
    id uuid primary key,
    user_id uuid not null,
    status text not null,
    phase text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    selected_execution_mode text
);

create table if not exists scenario_runs (
    id uuid primary key,
    session_id uuid not null,
    scenario_id text not null,
    playbook text not null,
    cohort text not null,
    started_at timestamptz,
    completed_at timestamptz
);

create table if not exists behavior_events_ts (
    user_id text not null,
    scenario_id text not null,
    price_drawdown_pct double precision not null,
    action text not null,
    noise_level double precision not null,
    sentiment_pressure double precision not null,
    latency_seconds double precision not null,
    created_at timestamptz not null default now()
);

create table if not exists behavioral_reports (
    id uuid primary key,
    session_id uuid not null unique,
    loss_tolerance double precision,
    noise_sensitivity double precision,
    panic_sell_tendency double precision,
    bottom_fishing_tendency double precision,
    hold_strength double precision,
    overtrading_tendency double precision,
    max_drawdown_endured double precision,
    recommended_risk_ceiling double precision,
    archetype text,
    report_json jsonb not null
);

create table if not exists trade_universe_requests (
    id uuid primary key,
    session_id uuid not null,
    input_type text not null,
    symbols jsonb not null,
    expanded_symbols jsonb not null,
    expansion_reason text,
    minimum_universe_size integer not null default 5
);

create table if not exists trading_preferences (
    id uuid primary key,
    session_id uuid not null unique,
    trading_frequency text not null,
    preferred_timeframe text not null,
    rationale text,
    preference_json jsonb not null,
    created_at timestamptz not null default now()
);

create table if not exists strategy_iterations (
    id uuid primary key,
    session_id uuid not null,
    iteration_no integer not null,
    user_feedback text,
    candidate_json jsonb not null,
    behavioral_compatibility double precision,
    approved boolean not null default false,
    created_at timestamptz not null default now()
);

create table if not exists deployment_settings (
    session_id uuid primary key,
    execution_mode text not null,
    autonomous_enabled boolean not null,
    advice_only boolean not null,
    confirmed_at timestamptz not null default now()
);

create table if not exists monitor_signals (
    id uuid primary key,
    session_id uuid not null,
    monitor_type text not null,
    severity text not null,
    title text not null,
    payload jsonb not null,
    created_at timestamptz not null default now()
);

create table if not exists market_asset_snapshots (
    id uuid primary key,
    session_id uuid not null,
    symbol text not null,
    timeframe text not null,
    snapshot_json jsonb not null,
    created_at timestamptz not null default now()
);

create table if not exists trade_execution_records (
    id uuid primary key,
    session_id uuid not null,
    symbol text not null,
    side text not null,
    quantity double precision not null,
    price double precision not null,
    notional double precision not null,
    execution_mode text not null,
    strategy_version text,
    realized_pnl_pct double precision not null,
    user_initiated boolean not null default true,
    note text,
    payload jsonb not null,
    created_at timestamptz not null default now()
);

create table if not exists profile_evolution_events (
    id uuid primary key,
    session_id uuid not null,
    source_type text not null,
    source_ref text not null,
    event_json jsonb not null,
    created_at timestamptz not null default now()
);

create table if not exists market_data_ts (
    session_id uuid not null,
    ts timestamptz not null,
    symbol text not null,
    timeframe text not null,
    open_price double precision not null,
    high_price double precision not null,
    low_price double precision not null,
    close_price double precision not null,
    volume double precision not null default 0,
    source text not null,
    regime_tag text
);

create table if not exists market_template_days (
    id uuid primary key,
    symbol text not null,
    trading_day date not null,
    source text not null,
    playbook text,
    market_regime text,
    shape_family text,
    pattern_label text,
    open_price double precision not null,
    high_price double precision not null,
    low_price double precision not null,
    close_price double precision not null,
    volume double precision not null default 0,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (symbol, trading_day, source)
);

create table if not exists market_template_intraday_segments (
    id uuid primary key,
    template_day_id uuid not null,
    symbol text not null,
    trading_day date not null,
    segment_index integer not null,
    start_ts timestamptz not null,
    end_ts timestamptz not null,
    shape_family text,
    market_regime text,
    pattern_label text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (template_day_id, segment_index)
);

create table if not exists intelligence_documents (
    id uuid primary key,
    session_id uuid not null,
    query text not null,
    source text not null,
    title text not null,
    url text not null,
    published_at text,
    payload jsonb not null,
    created_at timestamptz not null default now()
);

create table if not exists information_events (
    id uuid primary key,
    session_id uuid not null,
    channel text not null,
    trading_day text,
    source text not null,
    author text,
    handle text,
    title text not null,
    body text not null,
    info_tag text,
    sentiment_score double precision not null default 0,
    payload jsonb not null,
    created_at timestamptz not null default now()
);

create table if not exists history_events (
    id uuid primary key,
    session_id uuid not null,
    event_type text not null,
    summary text not null,
    phase text,
    payload jsonb not null,
    created_at timestamptz not null default now()
);

create table if not exists report_snapshots (
    id uuid primary key,
    session_id uuid not null,
    report_type text not null,
    title text not null,
    phase text,
    related_refs jsonb not null default '[]'::jsonb,
    payload jsonb not null,
    created_at timestamptz not null default now()
);
