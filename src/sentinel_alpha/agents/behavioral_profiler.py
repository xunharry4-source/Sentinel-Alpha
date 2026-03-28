from __future__ import annotations

from statistics import mean

from sentinel_alpha.domain.models import BehaviorEvent, BehavioralReport


class BehavioralProfilerAgent:
    """Quantifies user behavior observed during scenario simulation."""

    def profile(self, events: list[BehaviorEvent]) -> BehavioralReport:
        if not events:
            raise ValueError("Behavioral profiling requires at least one behavior event.")

        executed_events = [e for e in events if e.execution_status in {"filled", "partial_fill"}]
        sell_events = [e for e in executed_events if e.action == "sell"]
        buy_events = [e for e in executed_events if e.action == "buy"]
        high_noise_events = [e for e in events if e.noise_level >= 0.7]
        high_noise_executed_events = [e for e in high_noise_events if e.execution_status in {"filled", "partial_fill"}]
        rejected_or_unfilled = [e for e in events if e.execution_status in {"rejected", "unfilled"}]
        fast_events = [e for e in events if e.latency_seconds < 45]
        slow_events = [e for e in events if e.latency_seconds > 240]
        hesitant_focus_events = [e for e in events if (e.chart_focus_seconds or 0.0) >= 180]
        anxious_refresh_events = [e for e in events if (e.loss_refresh_count or 0) >= 3]
        trust_decay_events = [e for e in events if (e.trust_decay_score or 0.0) >= 0.45]
        late_drawdown_events = [e for e in events if (e.intraday_progress_pct or 0.0) >= 60 and (e.current_drawdown_pct or e.price_drawdown_pct) <= -3]
        opening_impulse_events = [e for e in events if (e.intraday_progress_pct or 0.0) <= 15 and e.action in {"buy", "sell"}]
        downtrend_buy_events = [e for e in buy_events if (e.daily_trend_pct or 0.0) < -2.0]

        panic_sell_score = min(
            1.0,
            sum(1 for e in sell_events if min(e.price_drawdown_pct, e.current_drawdown_pct or 0.0) <= -8) / max(1, len(events)),
        )
        averaging_down_score = min(
            1.0,
            sum(1 for e in buy_events if min(e.price_drawdown_pct, e.current_drawdown_pct or 0.0) <= -12) / max(1, len(events)),
        )
        noise_susceptibility = min(
            1.0,
            sum(1 for e in high_noise_executed_events if e.action in {"buy", "sell"}) / max(1, len(high_noise_events)),
        )
        intervention_risk = min(
            1.0,
            (
                sum(1 for e in events if e.latency_seconds < 90)
                + sum(1 for e in opening_impulse_events)
            )
            / max(1, len(events) * 1.5),
        )

        loss_points = [
            -min(e.price_drawdown_pct, e.current_drawdown_pct or e.price_drawdown_pct)
            for e in sell_events
            if min(e.price_drawdown_pct, e.current_drawdown_pct or e.price_drawdown_pct) < 0
        ]
        max_comfort_drawdown = mean(loss_points) if loss_points else 6.0
        discipline_score = max(
            0.0,
            min(
                1.0,
                1.0
                - (
                    panic_sell_score * 0.3
                    + averaging_down_score * 0.25
                    + noise_susceptibility * 0.2
                    + min(1.0, len(opening_impulse_events) / max(1, len(events))) * 0.1
                    + min(1.0, len(downtrend_buy_events) / max(1, len(buy_events) or 1)) * 0.15
                ),
            ),
        )

        notes: list[str] = []
        if panic_sell_score > 0.45:
            notes.append("User tends to exit quickly during sharp drawdowns.")
        if averaging_down_score > 0.35:
            notes.append("User shows a tendency to add risk into weakness.")
        if noise_susceptibility > 0.5:
            notes.append("User is materially affected by narrative pressure.")
        if rejected_or_unfilled and len(rejected_or_unfilled) / max(1, len(events)) > 0.35:
            notes.append("User frequently submits orders that do not execute cleanly under current market conditions.")
        if fast_events and len(fast_events) / max(1, len(events)) > 0.4:
            notes.append("User reacts quickly and may be prone to impulse execution.")
        if slow_events and len(slow_events) / max(1, len(events)) > 0.35:
            notes.append("User often delays decisions and may hesitate before acting.")
        if hesitant_focus_events and len(hesitant_focus_events) / max(1, len(events)) > 0.35:
            notes.append("User spends a long time watching the chart before acting, which suggests hesitation under uncertainty.")
        if anxious_refresh_events and len(anxious_refresh_events) / max(1, len(events)) > 0.25:
            notes.append("User starts probing the market repeatedly once drawdown deepens, suggesting anxiety-driven refresh behavior.")
        if trust_decay_events and len(trust_decay_events) / max(1, len(events)) > 0.2:
            notes.append("User frequently overrides automated execution, indicating trust decay toward automation.")
        if opening_impulse_events and len(opening_impulse_events) / max(1, len(events)) > 0.3:
            notes.append("User often trades very early in the simulated session before price structure settles.")
        if late_drawdown_events and len(late_drawdown_events) / max(1, len(events)) > 0.3:
            notes.append("User repeatedly acts after intraday weakness has already developed.")
        if downtrend_buy_events and len(downtrend_buy_events) / max(1, len(buy_events) or 1) > 0.35:
            notes.append("User tends to add exposure against a weakening daily trend.")

        return BehavioralReport(
            panic_sell_score=panic_sell_score,
            averaging_down_score=averaging_down_score,
            noise_susceptibility=noise_susceptibility,
            intervention_risk=intervention_risk,
            max_comfort_drawdown_pct=max(3.0, min(25.0, max_comfort_drawdown)),
            discipline_score=discipline_score,
            notes=notes,
        )
