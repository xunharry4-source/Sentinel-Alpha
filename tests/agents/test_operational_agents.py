from __future__ import annotations

from sentinel_alpha.agents.intent_aligner import IntentAlignerAgent
from sentinel_alpha.agents.market_asset_monitor_agent import MarketAssetMonitorAgent
from sentinel_alpha.agents.noise_agent import NoiseAgent
from sentinel_alpha.agents.portfolio_manager import PortfolioManagerAgent
from sentinel_alpha.agents.risk_guardian import RiskGuardianAgent
from sentinel_alpha.agents.strategy_monitor_agent import StrategyMonitorAgent
from sentinel_alpha.agents.user_monitor_agent import UserMonitorAgent


def test_noise_agent_normalizes_events() -> None:
    agent = NoiseAgent()
    events = agent.normalize_events([{"title": "Upgrade", "content": "Broker lifts target."}])

    assert events[0]["headline"] == "Upgrade"
    assert events[0]["body"] == "Broker lifts target."
    assert events[0]["channel"] == "market_feed"


def test_intent_aligner_builds_preferences_and_conflicts() -> None:
    agent = IntentAlignerAgent()
    preferences = agent.build_trading_preferences("high", "minute", "I want more action.")
    conflict = agent.detect_preference_conflict(
        {"recommended_trading_frequency": "low", "recommended_timeframe": "weekly"},
        preferences,
    )

    assert preferences["trading_frequency"] == "high"
    assert conflict is not None
    assert conflict["level"] == "high"


def test_risk_guardian_blocks_failed_checks() -> None:
    agent = RiskGuardianAgent()
    approved, message = agent.approve([{"status": "fail"}])

    assert approved is False
    assert "Re-iterate" in message


def test_portfolio_manager_returns_deployment_phase() -> None:
    agent = PortfolioManagerAgent()
    deployment = agent.set_execution_mode("advice_only")

    assert deployment["phase"] == "advice_only_active"


def test_monitor_agents_emit_structured_signals() -> None:
    user_signal = UserMonitorAgent().generate_signal({"noise_sensitivity": 0.75})
    strategy_signal = StrategyMonitorAgent().generate_signal({"behavioral_compatibility": 0.62})
    market_signal = MarketAssetMonitorAgent().generate_signal(
        {"selected_universe": ["AAPL", "AMD"]},
        None,
    )

    assert user_signal["monitor_type"] == "user"
    assert user_signal["severity"] == "warning"
    assert strategy_signal["monitor_type"] == "strategy"
    assert strategy_signal["severity"] == "warning"
    assert "AAPL" in market_signal["detail"]
