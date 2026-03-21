from __future__ import annotations

from sentinel_alpha.domain.models import BehavioralReport, MarketSnapshot


def behavior_penalty(report: BehavioralReport, market: MarketSnapshot) -> float:
    panic_penalty = report.panic_sell_score * market.realized_volatility_pct * 0.08
    noise_penalty = report.noise_susceptibility * market.event_risk_score * 0.12
    averaging_penalty = report.averaging_down_score * max(0.0, 1.0 - market.trend_score) * 0.1
    intervention_penalty = report.intervention_risk * 0.15
    discipline_offset = report.discipline_score * 0.08
    return max(0.0, panic_penalty + noise_penalty + averaging_penalty + intervention_penalty - discipline_offset)


def aligned_utility(
    expected_return_pct: float,
    volatility_pct: float,
    risk_aversion_lambda: float,
    report: BehavioralReport,
    market: MarketSnapshot,
) -> float:
    variance_penalty = risk_aversion_lambda * (volatility_pct / 100.0) ** 2
    return expected_return_pct / 100.0 - variance_penalty - behavior_penalty(report, market)
