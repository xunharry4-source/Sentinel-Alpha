from __future__ import annotations

from sentinel_alpha.agents.intelligence_agent import IntelligenceAgent
from sentinel_alpha.domain.models import IntelligenceDocument


def test_intelligence_agent_search_uses_normalized_documents() -> None:
    agent = IntelligenceAgent()
    agent._fetch_rss = lambda url, query: [  # type: ignore[method-assign]
        IntelligenceDocument(
            document_id="doc-1",
            query=query,
            title="AMD target raised",
            url="https://example.com/amd",
            source="example.com",
            published_at="2026-03-21",
            summary="Analyst raises target.",
            content="Analyst raises target and expects AI demand strength.",
            sentiment_hint=0.4,
        )
    ]

    documents = agent.search("AMD AI", max_documents=3)
    assert len(documents) == 1
    assert documents[0].query == "AMD AI"
    assert documents[0].url == "https://example.com/amd"
