from __future__ import annotations

from datetime import date
from typing import Literal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    user_name: str
    starting_capital: float = Field(gt=0)


class BehaviorEventIn(BaseModel):
    scenario_id: str = "simulation-market"
    price_drawdown_pct: float | None = None
    action: Literal["buy", "sell", "hold"]
    noise_level: float | None = None
    sentiment_pressure: float | None = None
    latency_seconds: float | None = None
    chart_focus_seconds: float | None = None
    loss_refresh_count: int | None = Field(default=None, ge=0)
    loss_refresh_drawdown_trigger_pct: float | None = None
    manual_intervention_count: int | None = Field(default=None, ge=0)
    manual_intervention_rate: float | None = Field(default=None, ge=0, le=1)
    trust_decay_score: float | None = Field(default=None, ge=0, le=1)
    execution_status: Literal["filled", "partial_fill", "unfilled", "rejected", "hold"] | None = None
    execution_reason: str | None = None


class CompleteSimulationRequest(BaseModel):
    symbol: str = "SIM"


class SimulationRetrainRequest(BaseModel):
    symbol: str | None = None


class SimulationMarketInitializeRequest(BaseModel):
    symbol: str
    provider: str | None = None
    daily_lookback: str = "6mo"
    intraday_lookback: str = "5d"
    intraday_interval: Literal["1m", "5m", "15m"] = "5m"


class SimulationMarketAdvanceRequest(BaseModel):
    steps: int = Field(default=1, ge=1, le=96)


class TradeUniverseRequest(BaseModel):
    input_type: Literal["stocks", "etfs", "sector"]
    symbols: list[str]
    allow_overfit_override: bool = False


class TradingPreferenceRequest(BaseModel):
    trading_frequency: Literal["low", "medium", "high"]
    preferred_timeframe: Literal["minute", "daily", "weekly"]
    rationale: str | None = None


class StrategyIterationRequest(BaseModel):
    feedback: str | None = None
    strategy_type: str = "rule_based_aligned"
    strategy_method: str | None = None
    strategy_description: str | None = None
    auto_iterations: int = Field(default=1, ge=1, le=10)
    iteration_mode: Literal["guided", "free"] = "guided"
    objective_metric: Literal["return", "win_rate", "drawdown", "max_loss"] = "return"
    target_return_pct: float | None = None
    target_win_rate_pct: float | None = None
    target_drawdown_pct: float | None = None
    target_max_loss_pct: float | None = None
    max_trade_allocation_pct: float | None = Field(default=None, gt=0, le=100)
    max_trade_amount: float | None = Field(default=None, gt=0)
    training_start_date: date | None = None
    training_end_date: date | None = None


class StrategyActiveSelectionRequest(BaseModel):
    strategy_ref: str


class MarketSnapshotIn(BaseModel):
    symbol: str
    timeframe: str = "1m"
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float = Field(ge=0)
    source: str = "manual"
    regime_tag: str | None = None


class TradeExecutionIn(BaseModel):
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)
    notional: float = Field(gt=0)
    execution_mode: Literal["autonomous", "advice_only", "manual"] = "manual"
    strategy_version: str | None = None
    realized_pnl_pct: float = 0.0
    user_initiated: bool = True
    note: str | None = None


class IntelligenceSearchRequest(BaseModel):
    query: str
    max_documents: int | None = Field(default=None, ge=1, le=20)


class MarketDataLookupRequest(BaseModel):
    symbol: str
    provider: str | None = None
    expiration: str | None = None


class InformationEventIn(BaseModel):
    channel: Literal["focus", "news", "chat", "discussion"]
    source: str
    title: str
    body: str
    trading_day: str | None = None
    author: str | None = None
    handle: str | None = None
    info_tag: str | None = None
    sentiment_score: float = 0.0
    metadata: dict[str, str | float | int | bool | None] = Field(default_factory=dict)


class InformationEventBatchRequest(BaseModel):
    events: list[InformationEventIn] = Field(default_factory=list)


class DeploymentRequest(BaseModel):
    execution_mode: Literal["autonomous", "advice_only"]


class ProgrammerTaskRequest(BaseModel):
    instruction: str
    target_files: list[str] = Field(default_factory=list)
    context: str | None = None
    commit_changes: bool = True


class DataSourceExpansionRequestIn(BaseModel):
    interface_documentation: str
    api_key: str | None = None
    provider_name: str | None = None
    category: Literal["market_data", "fundamentals", "dark_pool", "options"] | None = None
    base_url: str | None = None
    api_key_envs: list[str] = Field(default_factory=list)
    docs_summary: str | None = None
    docs_url: str | None = None
    sample_endpoint: str | None = None
    auth_style: Literal["header", "query", "bearer"] | None = None
    response_format: Literal["json", "csv", "xml"] | None = None


class DataSourceApplyRequest(BaseModel):
    run_id: str | None = None
    commit_changes: bool = True


class DataSourceTestRequest(BaseModel):
    run_id: str | None = None
    symbol: str = "AAPL"
    api_key: str | None = None


class DataSourceRunUpdateRequest(BaseModel):
    run_id: str
    interface_documentation: str
    api_key: str | None = None
    provider_name: str | None = None
    category: Literal["market_data", "fundamentals", "dark_pool", "options"] | None = None
    base_url: str | None = None
    api_key_envs: list[str] = Field(default_factory=list)
    docs_summary: str | None = None
    docs_url: str | None = None
    sample_endpoint: str | None = None
    auth_style: Literal["header", "query", "bearer"] | None = None
    response_format: Literal["json", "csv", "xml"] | None = None


class DataSourceRunDeleteRequest(BaseModel):
    run_id: str


class DataSourceProviderUpdateRequest(BaseModel):
    family: Literal["market_data", "fundamentals", "dark_pool", "options_data"]
    provider: str
    enabled: bool = True
    set_as_default: bool = False
    base_url: str | None = None
    base_path: str | None = None
    api_key_envs: list[str] = Field(default_factory=list)
    docs_url: str | None = None
    quote_filename: str | None = None
    history_filename: str | None = None
    financials_filename: str | None = None
    dark_pool_filename: str | None = None
    options_filename: str | None = None


class DataSourceProviderDeleteRequest(BaseModel):
    family: Literal["market_data", "fundamentals", "dark_pool", "options_data"]
    provider: str


class TradingTerminalIntegrationRequestIn(BaseModel):
    interface_documentation: str
    api_key: str | None = None
    terminal_name: str | None = None
    terminal_type: Literal["broker_api", "desktop_terminal", "rest_gateway", "fix_gateway", "local_sdk"] | None = None
    official_docs_url: str | None = None
    docs_search_url: str | None = None
    api_base_url: str | None = None
    api_key_envs: list[str] = Field(default_factory=list)
    auth_style: Literal["header", "query", "bearer"] | None = None
    order_endpoint: str | None = None
    cancel_endpoint: str | None = None
    order_status_endpoint: str | None = None
    positions_endpoint: str | None = None
    balances_endpoint: str | None = None
    trade_records_endpoint: str | None = None
    docs_summary: str | None = None
    user_notes: str | None = None
    response_field_map: dict[str, str] | None = None


class TradingTerminalRunUpdateRequest(BaseModel):
    run_id: str
    interface_documentation: str
    api_key: str | None = None
    terminal_name: str | None = None
    terminal_type: Literal["broker_api", "desktop_terminal", "rest_gateway", "fix_gateway", "local_sdk"] | None = None
    official_docs_url: str | None = None
    docs_search_url: str | None = None
    api_base_url: str | None = None
    api_key_envs: list[str] = Field(default_factory=list)
    auth_style: Literal["header", "query", "bearer"] | None = None
    order_endpoint: str | None = None
    cancel_endpoint: str | None = None
    order_status_endpoint: str | None = None
    positions_endpoint: str | None = None
    balances_endpoint: str | None = None
    trade_records_endpoint: str | None = None
    docs_summary: str | None = None
    user_notes: str | None = None
    response_field_map: dict[str, str] | None = None


class TradingTerminalRunDeleteRequest(BaseModel):
    run_id: str


class TradingTerminalApplyRequest(BaseModel):
    run_id: str | None = None
    commit_changes: bool = True


class TradingTerminalTestRequest(BaseModel):
    run_id: str | None = None


class ConfigUpdateRequest(BaseModel):
    payload: dict[str, Any]


class ConfigSingleTestRequest(BaseModel):
    payload: dict[str, Any] | None = None
    family: Literal["market_data", "fundamentals", "dark_pool", "options_data", "llm", "programmer_agent"]
    provider: str | None = None


class MonitorSignal(BaseModel):
    monitor_type: Literal["user", "strategy", "market"]
    severity: Literal["info", "warning", "critical"]
    title: str
    detail: str


class StrategyCheckResult(BaseModel):
    check_type: Literal["integrity", "stress_overfit"]
    status: Literal["pass", "warning", "fail"]
    title: str
    score: float = Field(ge=0.0, le=1.0)
    summary: str
    detail: str
    flags: list[str] = Field(default_factory=list)
    required_fix_actions: list[str] = Field(default_factory=list)
    metrics: dict[str, float | int | str] = Field(default_factory=dict)


class SessionSnapshot(BaseModel):
    session_id: UUID
    user_name: str
    phase: str
    status: str
    starting_capital: float
    scenarios: list[dict]
    behavioral_report: dict | None
    behavioral_user_report: dict | None = None
    behavioral_system_report: dict | None = None
    simulation_market: dict | None = None
    trading_preferences: dict | None
    trade_universe: dict | None
    strategy_package: dict | None
    active_trading_strategy: dict | None = None
    strategy_status_summary: dict | None = None
    strategy_checks: list[StrategyCheckResult]
    execution_mode: str | None
    profile_evolution: dict | None
    habit_goal_evolution: dict | None = None
    intelligence_history_analysis: dict | None = None
    simulation_training_state: dict | None = None
    market_snapshots: list[dict]
    trade_records: list[dict]
    strategy_feedback_log: list[dict]
    strategy_training_log: list[dict]
    intelligence_documents: list[dict]
    information_events: list[dict]
    data_bundles: list[dict]
    history_events: list[dict]
    report_history: list[dict]
    intelligence_runs: list[dict]
    agent_activity: list[dict] = Field(default_factory=list)
    programmer_runs: list[dict]
    data_source_runs: list[dict]
    terminal_integration_runs: list[dict]
    financials_runs: list[dict]
    dark_pool_runs: list[dict]
    options_runs: list[dict]
    token_usage: dict | None = None
    monitors: list[MonitorSignal]
