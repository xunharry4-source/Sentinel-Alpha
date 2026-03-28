from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class UserProfile:
    user_id: str
    preferred_assets: list[str]
    capital_base: float
    target_holding_days: int
    self_reported_risk_tolerance: float
    confidence_level: float = 0.5


@dataclass(slots=True)
class BehaviorEvent:
    scenario_id: str
    price_drawdown_pct: float
    action: str
    noise_level: float
    sentiment_pressure: float
    latency_seconds: float
    execution_status: str = "filled"
    execution_reason: str | None = None
    symbol: str | None = None
    timestamp: str | None = None
    market_price: float | None = None
    market_open_price: float | None = None
    market_high_price: float | None = None
    market_low_price: float | None = None
    intraday_timeframe: str | None = None
    intraday_progress_pct: float | None = None
    market_regime: str | None = None
    current_drawdown_pct: float | None = None
    daily_trend_pct: float | None = None
    current_day_return_pct: float | None = None
    chart_focus_seconds: float | None = None
    loss_refresh_count: int | None = None
    loss_refresh_drawdown_trigger_pct: float | None = None
    manual_intervention_count: int | None = None
    manual_intervention_rate: float | None = None
    trust_decay_score: float | None = None


@dataclass(slots=True)
class BehavioralReport:
    panic_sell_score: float
    averaging_down_score: float
    noise_susceptibility: float
    intervention_risk: float
    max_comfort_drawdown_pct: float
    discipline_score: float
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RiskPolicy:
    max_position_pct: float
    hard_stop_loss_pct: float
    portfolio_drawdown_limit_pct: float
    cooldown_hours: int
    narrative_override_penalty: float
    intervention_buffer_pct: float


@dataclass(slots=True)
class MarketSnapshot:
    symbol: str
    expected_return_pct: float
    realized_volatility_pct: float
    trend_score: float
    event_risk_score: float
    liquidity_score: float


@dataclass(slots=True)
class MarketDataPoint:
    timestamp: datetime
    symbol: str
    timeframe: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    source: str
    regime_tag: str | None = None


@dataclass(slots=True)
class StrategyBrief:
    symbol: str
    action_bias: str
    expected_return_pct: float
    worst_case_drawdown_pct: float
    utility_score: float
    recommended_position_pct: float
    rationale: list[str]


@dataclass(slots=True)
class PricePoint:
    timestamp: datetime
    price: float
    drawdown_pct: float
    return_pct: float
    implied_volatility: float


@dataclass(slots=True)
class NarrativeEvent:
    timestamp: datetime
    channel: str
    sentiment: float
    headline: str
    body: str
    deceptive: bool = False


@dataclass(slots=True)
class GroundTruthSnapshot:
    timestamp: datetime
    revenue_growth_pct: float
    free_cash_flow_margin_pct: float
    debt_pressure_score: float
    liquidity_stress_score: float
    hidden_risk_label: str


@dataclass(slots=True)
class ScenarioPackage:
    scenario_id: str
    playbook: str
    cohort: str
    symbol_alias: str
    price_track: list[PricePoint]
    narrative_track: list[NarrativeEvent]
    truth_track: list[GroundTruthSnapshot]
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class BehaviorLogEntry:
    user_id: str
    timestamp: datetime
    scenario_id: str
    price_at_action: float
    action_type: str
    last_noise_sentiment: float
    heart_rate_simulated: float
    pnl_at_action: float
    cohort: str


@dataclass(slots=True)
class FakeReversalAssessment:
    scenario_id: str
    stress_score: float
    deception_score: float
    premature_bottom_fishing: bool
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TradeExecutionRecord:
    timestamp: datetime
    symbol: str
    side: str
    quantity: float
    price: float
    notional: float
    execution_mode: str
    strategy_version: str | None
    realized_pnl_pct: float
    user_initiated: bool = True
    note: str | None = None


@dataclass(slots=True)
class ProfileEvolutionEvent:
    timestamp: datetime
    source_type: str
    source_ref: str
    delta_panic_sell: float = 0.0
    delta_averaging_down: float = 0.0
    delta_noise_sensitivity: float = 0.0
    delta_intervention_risk: float = 0.0
    delta_discipline: float = 0.0
    delta_confidence: float = 0.0
    note: str | None = None


@dataclass(slots=True)
class IntelligenceDocument:
    document_id: str
    query: str
    title: str
    url: str
    source: str
    published_at: str | None
    summary: str
    content: str
    sentiment_hint: float = 0.0


@dataclass(slots=True)
class WeightedRecord:
    dedupe_key: str
    provider_weight: float
    recency_weight: float
    completeness_weight: float
    final_weight: float


@dataclass(slots=True)
class FinancialStatementRecord:
    statement_type: str
    period_end: str
    revenue: float | None = None
    net_income: float | None = None
    eps: float | None = None
    total_assets: float | None = None
    total_liabilities: float | None = None
    operating_cash_flow: float | None = None
    free_cash_flow: float | None = None
    weighted: WeightedRecord | None = None


@dataclass(slots=True)
class FinancialsSnapshot:
    provider: str
    symbol: str
    entity_name: str | None
    report_period: str | None
    statements: list[FinancialStatementRecord] = field(default_factory=list)
    dedupe_summary: dict[str, int] = field(default_factory=dict)
    overall_weight: float = 0.0


@dataclass(slots=True)
class DarkPoolRecord:
    trade_date: str
    venue: str
    shares: float | None = None
    notional: float | None = None
    trade_count: int | None = None
    weighted: WeightedRecord | None = None


@dataclass(slots=True)
class DarkPoolSnapshot:
    provider: str
    symbol: str
    records: list[DarkPoolRecord] = field(default_factory=list)
    dedupe_summary: dict[str, int] = field(default_factory=dict)
    overall_weight: float = 0.0


@dataclass(slots=True)
class OptionContractRecord:
    contract_symbol: str
    expiration: str
    strike: float | None
    option_type: str
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    volume: float | None = None
    open_interest: float | None = None
    implied_volatility: float | None = None
    weighted: WeightedRecord | None = None


@dataclass(slots=True)
class OptionsSnapshot:
    provider: str
    symbol: str
    expiration_dates: list[str] = field(default_factory=list)
    contracts: list[OptionContractRecord] = field(default_factory=list)
    dedupe_summary: dict[str, int] = field(default_factory=dict)
    overall_weight: float = 0.0
