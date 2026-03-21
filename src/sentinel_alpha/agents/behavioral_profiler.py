from __future__ import annotations

from statistics import mean

from sentinel_alpha.domain.models import BehaviorEvent, BehavioralReport


class BehavioralProfilerAgent:
    """Quantifies user behavior observed during scenario simulation."""

    def profile(self, events: list[BehaviorEvent]) -> BehavioralReport:
        if not events:
            raise ValueError("Behavioral profiling requires at least one behavior event.")

        sell_events = [e for e in events if e.action == "sell"]
        buy_events = [e for e in events if e.action == "buy"]
        high_noise_events = [e for e in events if e.noise_level >= 0.7]

        panic_sell_score = min(
            1.0,
            sum(1 for e in sell_events if e.price_drawdown_pct <= -8) / max(1, len(events)),
        )
        averaging_down_score = min(
            1.0,
            sum(1 for e in buy_events if e.price_drawdown_pct <= -12) / max(1, len(events)),
        )
        noise_susceptibility = min(
            1.0,
            sum(1 for e in high_noise_events if e.action in {"buy", "sell"}) / max(1, len(high_noise_events)),
        )
        intervention_risk = min(
            1.0,
            sum(1 for e in events if e.latency_seconds < 90) / max(1, len(events)),
        )

        loss_points = [-e.price_drawdown_pct for e in sell_events if e.price_drawdown_pct < 0]
        max_comfort_drawdown = mean(loss_points) if loss_points else 6.0
        discipline_score = max(
            0.0,
            min(1.0, 1.0 - (panic_sell_score * 0.35 + averaging_down_score * 0.35 + noise_susceptibility * 0.3)),
        )

        notes: list[str] = []
        if panic_sell_score > 0.45:
            notes.append("User tends to exit quickly during sharp drawdowns.")
        if averaging_down_score > 0.35:
            notes.append("User shows a tendency to add risk into weakness.")
        if noise_susceptibility > 0.5:
            notes.append("User is materially affected by narrative pressure.")

        return BehavioralReport(
            panic_sell_score=panic_sell_score,
            averaging_down_score=averaging_down_score,
            noise_susceptibility=noise_susceptibility,
            intervention_risk=intervention_risk,
            max_comfort_drawdown_pct=max(3.0, min(25.0, max_comfort_drawdown)),
            discipline_score=discipline_score,
            notes=notes,
        )
