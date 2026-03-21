from __future__ import annotations

from copy import deepcopy


class NoiseAgent:
    """Normalizes incoming information and narrative pressure events."""

    def normalize_events(self, events: list[dict]) -> list[dict]:
        normalized: list[dict] = []
        for index, event in enumerate(events, start=1):
            payload = deepcopy(event)
            payload.setdefault("event_id", f"noise-{index}")
            payload.setdefault("channel", "market_feed")
            payload.setdefault("sentiment", 0.0)
            payload.setdefault("headline", payload.get("title", "Untitled event"))
            payload.setdefault("body", payload.get("content", payload.get("headline", "")))
            payload.setdefault("source", "internal")
            normalized.append(payload)
        return normalized
