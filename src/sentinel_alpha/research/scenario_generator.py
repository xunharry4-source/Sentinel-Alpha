from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
import json
import math
from pathlib import Path
from random import Random

from sentinel_alpha.domain.models import FakeReversalAssessment, GroundTruthSnapshot, NarrativeEvent, PricePoint, ScenarioPackage


class ScenarioGenerator:
    """Builds deterministic financial stress scenarios for behavioral experiments."""

    def __init__(self, seed: int = 7) -> None:
        self.random = Random(seed)

    def generate(self, playbook: str, cohort: str = "pressure", symbol_alias: str = "Token-X") -> ScenarioPackage:
        playbook_key = playbook.lower().strip()
        aliases = {
            "uptrend": "uptrend",
            "gap": "gap",
            "oscillation": "oscillation",
            "drawdown": "drawdown",
            "fake_reversal": "fake_reversal",
            "downtrend": "downtrend",
            "boiling_frog": "drawdown",
            "black_swan": "gap",
            "fomo_trap": "uptrend",
            "clean_room": "oscillation",
        }
        playbook_key = aliases.get(playbook_key, playbook_key)
        if playbook_key == "uptrend":
            return self._uptrend(cohort, symbol_alias)
        if playbook_key == "gap":
            return self._gap(cohort, symbol_alias)
        if playbook_key == "oscillation":
            return self._oscillation(cohort, symbol_alias)
        if playbook_key == "drawdown":
            return self._drawdown(cohort, symbol_alias)
        if playbook_key == "fake_reversal":
            return self._fake_reversal(cohort, symbol_alias)
        if playbook_key == "downtrend":
            return self._downtrend(cohort, symbol_alias)
        raise ValueError(f"Unsupported playbook: {playbook}")

    def write_json(self, package: ScenarioPackage, output_path: str | Path) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(package)
        path.write_text(json.dumps(payload, indent=2, default=str))
        return path

    def _uptrend(self, cohort: str, symbol_alias: str) -> ScenarioPackage:
        start = datetime(2026, 1, 5, 9, 30, tzinfo=UTC)
        price_track: list[PricePoint] = []
        narrative_track: list[NarrativeEvent] = []
        truth_track: list[GroundTruthSnapshot] = []
        price = 100.0

        for day in range(18):
            timestamp = start + timedelta(days=day)
            rise = self.random.uniform(0.55, 1.45)
            price *= 1.0 + rise / 100.0
            drawdown = (price / 100.0 - 1.0) * 100.0
            price_track.append(
                PricePoint(timestamp, round(price, 2), round(drawdown, 2), round(rise, 2), 0.22 + day * 0.003)
            )
            truth_track.append(
                GroundTruthSnapshot(timestamp, 19.0, 16.0, 0.16, 0.18, "trend_persistent")
            )
            if cohort == "pressure":
                narrative_track.append(
                    NarrativeEvent(
                        timestamp + timedelta(hours=1),
                        "macro_desk",
                        -0.42,
                        "Valuation is stretched",
                        "Plenty of traders are fading this move. Chasing here looks reckless.",
                        True,
                    )
                )

        return ScenarioPackage("scenario-uptrend", "uptrend", cohort, symbol_alias, price_track, narrative_track, truth_track, ["trend", "fear_of_heights"])

    def _gap(self, cohort: str, symbol_alias: str) -> ScenarioPackage:
        start = datetime(2026, 2, 13, 9, 30, tzinfo=UTC)
        price_track: list[PricePoint] = []
        narrative_track: list[NarrativeEvent] = []
        truth_track: list[GroundTruthSnapshot] = []
        price = 100.0
        moves = [-8.0, -1.2, 0.8, -0.5, 1.1]

        for index, move in enumerate(moves):
            timestamp = start + timedelta(minutes=index * 5)
            price *= 1.0 + move / 100.0
            drawdown = (price / 100.0 - 1.0) * 100.0
            iv = 0.58 + abs(move) * 0.02
            price_track.append(PricePoint(timestamp, round(price, 2), round(drawdown, 2), move, iv))
            truth_track.append(GroundTruthSnapshot(timestamp, 3.0, 9.0, 0.28, 0.31, "event_shock"))
            if cohort == "pressure":
                sentiment = -0.88 if index == 0 else 0.34
                narrative_track.append(
                    NarrativeEvent(
                        timestamp + timedelta(seconds=20),
                        "breaking_news",
                        sentiment,
                        "Emergency headline hits before the open",
                        "A flood of conflicting reports is hitting desks. Nobody agrees whether this is disaster or opportunity.",
                        True,
                    )
                )

        return ScenarioPackage("scenario-gap", "gap", cohort, symbol_alias, price_track, narrative_track, truth_track, ["jump", "shock"])

    def _oscillation(self, cohort: str, symbol_alias: str) -> ScenarioPackage:
        start = datetime(2026, 1, 8, 9, 30, tzinfo=UTC)
        price_track: list[PricePoint] = []
        narrative_track: list[NarrativeEvent] = []
        truth_track: list[GroundTruthSnapshot] = []
        price = 100.0

        for step in range(16):
            timestamp = start + timedelta(hours=step * 3)
            move = 2.7 * math.sin(step * 1.35)
            price *= 1.0 + move / 100.0
            drawdown = (price / 100.0 - 1.0) * 100.0
            price_track.append(
                PricePoint(timestamp, round(price, 2), round(drawdown, 2), round(move, 2), 0.24 + abs(move) * 0.03)
            )
            truth_track.append(GroundTruthSnapshot(timestamp, 8.0, 11.0, 0.21, 0.22, "range_bound"))
            if cohort == "pressure":
                sentiment = 0.55 if step % 2 == 0 else -0.55
                headline = "Breakout confirmed" if step % 2 == 0 else "Breakdown underway"
                body = "Chat rooms are flipping hard between bullish conviction and bearish certainty."
                narrative_track.append(NarrativeEvent(timestamp + timedelta(minutes=30), "trader_chat", sentiment, headline, body, True))

        return ScenarioPackage("scenario-oscillation", "oscillation", cohort, symbol_alias, price_track, narrative_track, truth_track, ["range", "overtrading"])

    def _drawdown(self, cohort: str, symbol_alias: str) -> ScenarioPackage:
        start = datetime(2026, 1, 5, 9, 30, tzinfo=UTC)
        price_track: list[PricePoint] = []
        narrative_track: list[NarrativeEvent] = []
        truth_track: list[GroundTruthSnapshot] = []
        price = 100.0

        for day in range(20):
            timestamp = start + timedelta(days=day)
            daily_drop = self.random.uniform(-1.1, -0.45)
            price *= 1.0 + daily_drop / 100.0
            drawdown = (price / 100.0 - 1.0) * 100.0
            price_track.append(
                PricePoint(timestamp, round(price, 2), round(drawdown, 2), round(daily_drop, 2), 0.28 + day * 0.004)
            )
            truth_track.append(
                GroundTruthSnapshot(timestamp, -12.0, -18.0, 0.82, 0.74, "cash_flow_break")
            )
            if cohort == "pressure":
                narrative_track.append(
                    NarrativeEvent(
                        timestamp + timedelta(hours=2),
                        "forum",
                        0.74,
                        "Strong hands are accumulating the dip",
                        "Multiple desks are quietly building positions. Retail weakness is being absorbed.",
                        True,
                    )
                )

        return ScenarioPackage("scenario-drawdown", "drawdown", cohort, symbol_alias, price_track, narrative_track, truth_track, ["slow_bleed", "sunk_cost"])

    def _fake_reversal(self, cohort: str, symbol_alias: str) -> ScenarioPackage:
        start = datetime(2026, 2, 13, 14, 0, tzinfo=UTC)
        price_track: list[PricePoint] = []
        narrative_track: list[NarrativeEvent] = []
        truth_track: list[GroundTruthSnapshot] = []
        price = 100.0
        moves = [-9.0, -7.0, 4.5, 5.5, -6.0, -7.0, -4.5]

        for minute, move in enumerate(moves):
            timestamp = start + timedelta(minutes=minute * 10)
            price *= 1.0 + move / 100.0
            drawdown = (price / 100.0 - 1.0) * 100.0
            price_track.append(
                PricePoint(timestamp, round(price, 2), round(drawdown, 2), round(move, 2), 0.54 + abs(move) * 0.02)
            )
            truth_track.append(
                GroundTruthSnapshot(timestamp, -15.0, -12.0, 0.74, 0.69, "trend_still_bearish")
            )
            if cohort == "pressure":
                sentiment = 0.84 if minute in {2, 3} else -0.61
                headline = "V-bottom confirmed" if minute in {2, 3} else "Panic liquidations continue"
                body = (
                    "Smart money is sweeping the lows. This rebound is the first leg of the reversal."
                    if minute in {2, 3}
                    else "Weak hands are puking inventory. Desks expect more forced selling."
                )
                narrative_track.append(
                    NarrativeEvent(
                        timestamp + timedelta(seconds=20),
                        "social",
                        sentiment,
                        headline,
                        body,
                        True,
                    )
                )

        return ScenarioPackage("scenario-fake-reversal", "fake_reversal", cohort, symbol_alias, price_track, narrative_track, truth_track, ["bear_market_rally", "bottom_fishing"])

    def _downtrend(self, cohort: str, symbol_alias: str) -> ScenarioPackage:
        start = datetime(2026, 3, 2, 9, 30, tzinfo=UTC)
        price_track: list[PricePoint] = []
        narrative_track: list[NarrativeEvent] = []
        truth_track: list[GroundTruthSnapshot] = []
        price = 100.0
        drops = [-3.8, -4.2, -3.5, -4.8, -3.1, -4.0, -2.8]

        for day, drop in enumerate(drops):
            timestamp = start + timedelta(days=day)
            price *= 1.0 + drop / 100.0
            drawdown = (price / 100.0 - 1.0) * 100.0
            price_track.append(
                PricePoint(timestamp, round(price, 2), round(drawdown, 2), round(drop, 2), 0.38 + day * 0.02)
            )
            truth_track.append(
                GroundTruthSnapshot(timestamp, -22.0, -16.0, 0.78, 0.72, "fundamentals_deteriorating")
            )
            if cohort == "pressure":
                narrative_track.append(
                    NarrativeEvent(
                        timestamp + timedelta(hours=1),
                        "analyst_chat",
                        -0.36,
                        "The selloff is rational",
                        "Higher rates, weaker guidance, and tighter liquidity all justify lower multiples.",
                        True,
                    )
                )

        return ScenarioPackage("scenario-downtrend", "downtrend", cohort, symbol_alias, price_track, narrative_track, truth_track, ["trend_down", "risk_control"])

    def assess_fake_reversal(
        self,
        scenario: ScenarioPackage,
        buy_actions: int,
        total_actions: int,
        user_sentiment_score: float,
    ) -> FakeReversalAssessment:
        volatility = max(0.01, sum(abs(point.return_pct) for point in scenario.price_track) / len(scenario.price_track))
        action_frequency = buy_actions / max(1, total_actions)
        stress_score = abs(action_frequency) / volatility * max(0.1, user_sentiment_score)
        deceptive_bounce_points = [point for point in scenario.price_track if point.return_pct > 0]
        deception_score = min(1.0, (len(deceptive_bounce_points) * action_frequency * user_sentiment_score) / 2.5)
        notes: list[str] = []
        if deception_score > 0.55:
            notes.append("User repeatedly added risk during a counter-trend bounce.")
        if stress_score > 0.2:
            notes.append("Action frequency remained elevated relative to realized volatility.")
        return FakeReversalAssessment(
            scenario_id=scenario.scenario_id,
            stress_score=round(stress_score, 4),
            deception_score=round(deception_score, 4),
            premature_bottom_fishing=deception_score > 0.5,
            notes=notes,
        )
