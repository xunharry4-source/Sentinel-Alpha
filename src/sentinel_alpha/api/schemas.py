from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    user_name: str
    starting_capital: float = Field(gt=0)


class BehaviorEventIn(BaseModel):
    scenario_id: str
    price_drawdown_pct: float
    action: Literal["buy", "sell", "hold"]
    noise_level: float
    sentiment_pressure: float
    latency_seconds: float


class CompleteSimulationRequest(BaseModel):
    symbol: str = "SIM"


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
    auto_iterations: int = Field(default=1, ge=1, le=10)
    iteration_mode: Literal["guided", "free"] = "guided"
    objective_metric: Literal["return", "win_rate", "drawdown", "max_loss"] = "return"
    target_return_pct: float | None = None
    target_win_rate_pct: float | None = None
    target_drawdown_pct: float | None = None
    target_max_loss_pct: float | None = None


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
    trading_preferences: dict | None
    trade_universe: dict | None
    strategy_package: dict | None
    strategy_checks: list[StrategyCheckResult]
    execution_mode: str | None
    profile_evolution: dict | None
    market_snapshots: list[dict]
    trade_records: list[dict]
    strategy_feedback_log: list[dict]
    strategy_training_log: list[dict]
    intelligence_documents: list[dict]
    information_events: list[dict]
    history_events: list[dict]
    report_history: list[dict]
    intelligence_runs: list[dict]
    programmer_runs: list[dict]
    monitors: list[MonitorSignal]
