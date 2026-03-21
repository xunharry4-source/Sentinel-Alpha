from __future__ import annotations

from sentinel_alpha.domain.models import BehavioralReport, MarketSnapshot, StrategyBrief, UserProfile

try:
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import Runnable
except ImportError:  # pragma: no cover - optional runtime dependency
    Runnable = object  # type: ignore[assignment]
    ChatPromptTemplate = None  # type: ignore[assignment]
    StrOutputParser = None  # type: ignore[assignment]


class LangChainStrategyNarrative:
    """Builds a qualitative brief chain on top of the quantitative strategy output."""

    def __init__(self, llm: Runnable) -> None:
        if ChatPromptTemplate is None or StrOutputParser is None:
            raise RuntimeError("langchain-core is required to use LangChainStrategyNarrative.")

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You explain trading strategy decisions as a risk officer for a personal trading expert."
                    " Be concise, probabilistic, and behavior-aware.",
                ),
                (
                    "human",
                    "User risk tolerance: {risk_tolerance}\n"
                    "User confidence: {confidence}\n"
                    "Behavior report: {behavior_report}\n"
                    "Market snapshot: {market_snapshot}\n"
                    "Strategy brief: {strategy_brief}\n"
                    "Write a short explanation of why this strategy fits the user.",
                ),
            ]
        )
        self.chain = prompt | llm | StrOutputParser()

    def generate(
        self,
        user: UserProfile,
        report: BehavioralReport,
        market: MarketSnapshot,
        brief: StrategyBrief,
    ) -> str:
        return self.chain.invoke(
            {
                "risk_tolerance": user.self_reported_risk_tolerance,
                "confidence": user.confidence_level,
                "behavior_report": report,
                "market_snapshot": market,
                "strategy_brief": brief,
            }
        )
