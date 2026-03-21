create table if not exists user_behavior_log (
    id bigserial primary key,
    user_id uuid not null,
    scenario_id text not null,
    cohort text not null check (cohort in ('control', 'pressure')),
    event_ts timestamptz not null,
    price_at_action numeric(18, 6) not null,
    action_type varchar(10) not null check (action_type in ('BUY', 'SELL', 'HOLD', 'CHAT')),
    last_noise_sentiment double precision not null,
    heart_rate_simulated double precision not null,
    pnl_at_action double precision not null,
    created_at timestamptz not null default now()
);

create index if not exists idx_user_behavior_log_user_ts
    on user_behavior_log (user_id, event_ts desc);

create index if not exists idx_user_behavior_log_scenario
    on user_behavior_log (scenario_id, cohort);
