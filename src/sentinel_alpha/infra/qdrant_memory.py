from __future__ import annotations

from uuid import uuid4

from sentinel_alpha.config import get_settings
from sentinel_alpha.domain.models import BehavioralReport, StrategyBrief, UserProfile

try:
    from langchain_qdrant import QdrantVectorStore
    from qdrant_client import QdrantClient
except ImportError:  # pragma: no cover
    QdrantVectorStore = None  # type: ignore[assignment]
    QdrantClient = None  # type: ignore[assignment]


class QdrantBehaviorMemoryStore:
    """Stores profile memory and strategy rationale in Qdrant."""

    def __init__(
        self,
        embedding_function: object,
        url: str | None = None,
        collection_name: str | None = None,
    ) -> None:
        if QdrantClient is None or QdrantVectorStore is None:
            raise RuntimeError("qdrant-client and langchain-qdrant are required to use QdrantBehaviorMemoryStore.")

        settings = get_settings()
        resolved_url = url or settings.qdrant_url
        resolved_collection = collection_name or settings.qdrant_collection
        client = QdrantClient(url=resolved_url)
        self.vectorstore = QdrantVectorStore(
            client=client,
            collection_name=resolved_collection,
            embedding=embedding_function,
        )

    def add_behavior_memory(
        self,
        user: UserProfile,
        report: BehavioralReport,
        brief: StrategyBrief,
    ) -> None:
        text = "\n".join(
            [
                f"user_id={user.user_id}",
                f"assets={','.join(user.preferred_assets)}",
                f"panic_sell={report.panic_sell_score:.2f}",
                f"averaging_down={report.averaging_down_score:.2f}",
                f"noise_susceptibility={report.noise_susceptibility:.2f}",
                f"discipline={report.discipline_score:.2f}",
                f"action_bias={brief.action_bias}",
                *report.notes,
                *brief.rationale,
            ]
        )
        self.vectorstore.add_texts(
            texts=[text],
            metadatas=[{"user_id": user.user_id, "symbol": brief.symbol}],
            ids=[str(uuid4())],
        )

    def add_profile_evolution_memory(
        self,
        user_id: str,
        source_type: str,
        narrative: str,
        metadata: dict[str, str | float | int],
    ) -> None:
        merged_metadata = {"user_id": user_id, "source_type": source_type, **metadata}
        self.vectorstore.add_texts(
            texts=[narrative],
            metadatas=[merged_metadata],
            ids=[str(uuid4())],
        )

    def add_market_intelligence_memory(
        self,
        query: str,
        title: str,
        content: str,
        metadata: dict[str, str | float | int],
    ) -> None:
        self.vectorstore.add_texts(
            texts=[f"{query}\n{title}\n{content}".strip()],
            metadatas=[{"query": query, **metadata}],
            ids=[str(uuid4())],
        )
