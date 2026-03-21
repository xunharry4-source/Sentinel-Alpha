from __future__ import annotations

from html import unescape
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from uuid import uuid4
import xml.etree.ElementTree as ET

from sentinel_alpha.config import get_settings
from sentinel_alpha.domain.models import IntelligenceDocument


class IntelligenceAgent:
    """Fetches public market narratives from configured search templates."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def search(self, query: str, max_documents: int | None = None) -> list[IntelligenceDocument]:
        if not self.settings.intelligence_enabled:
            return []
        limit = max_documents or self.settings.intelligence_max_documents
        documents: list[IntelligenceDocument] = []
        seen_urls: set[str] = set()

        for template in self.settings.intelligence_rss_search_templates:
            url = template.format(query=quote_plus(query))
            for item in self._fetch_rss(url, query):
                if item.url in seen_urls:
                    continue
                seen_urls.add(item.url)
                documents.append(item)
                if len(documents) >= limit:
                    return documents
        return documents

    def _fetch_rss(self, url: str, query: str) -> list[IntelligenceDocument]:
        request = Request(url, headers={"User-Agent": "Sentinel-Alpha/0.1"})
        with urlopen(request, timeout=self.settings.intelligence_request_timeout_seconds) as response:
            payload = response.read()
        root = ET.fromstring(payload)
        items = root.findall(".//item")
        documents: list[IntelligenceDocument] = []
        for item in items:
            title = self._text(item.findtext("title"))
            link = self._text(item.findtext("link"))
            summary = self._text(item.findtext("description"))
            source = self._extract_source(link)
            published = self._text(item.findtext("pubDate")) or None
            content = f"{title}\n{summary}".strip()
            documents.append(
                IntelligenceDocument(
                    document_id=str(uuid4()),
                    query=query,
                    title=title or "untitled",
                    url=link,
                    source=source,
                    published_at=published,
                    summary=summary,
                    content=content,
                    sentiment_hint=self._sentiment_hint(content),
                )
            )
        return documents

    def _extract_source(self, url: str) -> str:
        if "://" not in url:
            return "unknown"
        return url.split("://", 1)[1].split("/", 1)[0]

    def _text(self, value: str | None) -> str:
        return unescape((value or "").replace("<![CDATA[", "").replace("]]>", "").strip())

    def _sentiment_hint(self, text: str) -> float:
        lowered = text.lower()
        positive = sum(token in lowered for token in ("beat", "bullish", "upgrade", "rally", "growth"))
        negative = sum(token in lowered for token in ("downgrade", "bearish", "slump", "risk", "crash"))
        raw = (positive - negative) / max(1, positive + negative)
        return round(max(-1.0, min(1.0, raw)), 4)
