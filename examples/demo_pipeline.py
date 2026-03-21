from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel_alpha.domain.models import BehaviorEvent, MarketSnapshot, UserProfile
from sentinel_alpha.orchestration.pipeline import PersonalTradingExpertPipeline


def main() -> None:
    user = UserProfile(
        user_id="demo-user",
        preferred_assets=["TSLA", "BTC"],
        capital_base=500_000,
        target_holding_days=12,
        self_reported_risk_tolerance=0.45,
        confidence_level=0.55,
    )

    events = [
        BehaviorEvent("stress-gap-down", -9.5, "sell", 0.4, -0.2, 45),
        BehaviorEvent("fake-breakout", 3.0, "buy", 0.8, 0.6, 50),
        BehaviorEvent("capitulation", -16.0, "buy", 0.7, -0.7, 80),
        BehaviorEvent("rebound-fade", -6.0, "hold", 0.3, 0.1, 180),
        BehaviorEvent("panic-feed", -11.0, "sell", 0.9, -0.9, 40),
    ]

    market = MarketSnapshot(
        symbol="TSLA",
        expected_return_pct=18.0,
        realized_volatility_pct=42.0,
        trend_score=0.35,
        event_risk_score=0.62,
        liquidity_score=0.95,
    )

    brief = PersonalTradingExpertPipeline().run(user, events, market)
    print(json.dumps(asdict(brief), indent=2))


if __name__ == "__main__":
    main()
