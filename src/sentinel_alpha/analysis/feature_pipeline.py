from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json


@dataclass(slots=True)
class SessionFeaturePipeline:
    """Builds a stable feature snapshot from market, intelligence, and behavior state."""

    def build(
        self,
        *,
        behavioral_report: dict | None,
        profile_evolution: dict | None,
        trading_preferences: dict | None,
        market_snapshots: list[dict] | None,
        intelligence_runs: list[dict] | None,
        financials_runs: list[dict] | None,
        dark_pool_runs: list[dict] | None,
        options_runs: list[dict] | None,
    ) -> dict:
        effective_profile = (profile_evolution or {}).get("effective_profile") or behavioral_report or {}
        latest_market = market_snapshots[-1] if market_snapshots else {}
        latest_intelligence = intelligence_runs[-1] if intelligence_runs else {}
        latest_financials = financials_runs[-1] if financials_runs else {}
        latest_dark_pool = dark_pool_runs[-1] if dark_pool_runs else {}
        latest_options = options_runs[-1] if options_runs else {}

        snapshot = {
            "behavioral": {
                "noise_sensitivity": round(float(effective_profile.get("noise_sensitivity", 0.0) or 0.0), 4),
                "panic_sell_tendency": round(float(effective_profile.get("panic_sell_tendency", 0.0) or 0.0), 4),
                "bottom_fishing_tendency": round(float(effective_profile.get("bottom_fishing_tendency", 0.0) or 0.0), 4),
                "overtrading_tendency": round(float(effective_profile.get("overtrading_tendency", 0.0) or 0.0), 4),
                "hold_strength": round(float(effective_profile.get("hold_strength", 0.0) or 0.0), 4),
            },
            "market": {
                "has_snapshot": bool(latest_market),
                "symbol": latest_market.get("symbol"),
                "timeframe": latest_market.get("timeframe"),
                "close_price": latest_market.get("close_price"),
                "volume": latest_market.get("volume"),
                "regime_tag": latest_market.get("regime_tag"),
            },
            "preferences": {
                "trading_frequency": (trading_preferences or {}).get("trading_frequency"),
                "preferred_timeframe": (trading_preferences or {}).get("preferred_timeframe"),
                "conflict_level": (trading_preferences or {}).get("conflict_level"),
            },
            "intelligence": {
                "query": latest_intelligence.get("query"),
                "document_count": latest_intelligence.get("document_count", 0),
                "factors": ((latest_intelligence.get("report") or {}).get("factors") or {}),
            },
            "fundamentals": {
                "symbol": latest_financials.get("symbol"),
                "provider": latest_financials.get("provider"),
                "factors": latest_financials.get("factors") or {},
            },
            "dark_pool": {
                "symbol": latest_dark_pool.get("symbol"),
                "provider": latest_dark_pool.get("provider"),
                "factors": latest_dark_pool.get("factors") or {},
            },
            "options": {
                "symbol": latest_options.get("symbol"),
                "provider": latest_options.get("provider"),
                "expiration": latest_options.get("expiration"),
                "factors": latest_options.get("factors") or {},
            },
        }
        snapshot["source_lineage"] = self._build_source_lineage(
            latest_market=latest_market,
            latest_intelligence=latest_intelligence,
            latest_financials=latest_financials,
            latest_dark_pool=latest_dark_pool,
            latest_options=latest_options,
        )
        snapshot["data_quality"] = self._build_data_quality(snapshot)
        snapshot["meta"] = self._build_meta(snapshot)
        return snapshot

    def _build_source_lineage(
        self,
        *,
        latest_market: dict,
        latest_intelligence: dict,
        latest_financials: dict,
        latest_dark_pool: dict,
        latest_options: dict,
    ) -> dict:
        return {
            "market": {
                "source": latest_market.get("source"),
                "symbol": latest_market.get("symbol"),
                "timeframe": latest_market.get("timeframe"),
            },
            "intelligence": {
                "run_id": latest_intelligence.get("run_id"),
                "query": latest_intelligence.get("query"),
                "document_count": latest_intelligence.get("document_count", 0),
            },
            "fundamentals": {
                "run_id": latest_financials.get("run_id"),
                "symbol": latest_financials.get("symbol"),
                "provider": latest_financials.get("provider"),
            },
            "dark_pool": {
                "run_id": latest_dark_pool.get("run_id"),
                "symbol": latest_dark_pool.get("symbol"),
                "provider": latest_dark_pool.get("provider"),
            },
            "options": {
                "run_id": latest_options.get("run_id"),
                "symbol": latest_options.get("symbol"),
                "provider": latest_options.get("provider"),
                "expiration": latest_options.get("expiration"),
            },
        }

    def _build_data_quality(self, snapshot: dict) -> dict:
        sections = {
            "behavioral": bool(snapshot.get("behavioral")),
            "market": bool((snapshot.get("market") or {}).get("has_snapshot")),
            "preferences": bool((snapshot.get("preferences") or {}).get("trading_frequency") or (snapshot.get("preferences") or {}).get("preferred_timeframe")),
            "intelligence": bool((snapshot.get("intelligence") or {}).get("document_count")),
            "fundamentals": bool((snapshot.get("fundamentals") or {}).get("factors")),
            "dark_pool": bool((snapshot.get("dark_pool") or {}).get("factors")),
            "options": bool((snapshot.get("options") or {}).get("factors")),
        }
        available_sections = [name for name, present in sections.items() if present]
        provider_coverage = [
            provider
            for provider in [
                (snapshot.get("fundamentals") or {}).get("provider"),
                (snapshot.get("dark_pool") or {}).get("provider"),
                (snapshot.get("options") or {}).get("provider"),
            ]
            if provider
        ]
        completeness_score = round(len(available_sections) / len(sections), 4)
        return {
            "available_sections": available_sections,
            "missing_sections": [name for name, present in sections.items() if not present],
            "section_coverage_score": completeness_score,
            "provider_coverage": sorted(set(provider_coverage)),
            "provider_count": len(set(provider_coverage)),
        }

    def _build_meta(self, snapshot: dict) -> dict:
        canonical = {
            key: value
            for key, value in snapshot.items()
            if key not in {"meta"}
        }
        payload = json.dumps(canonical, sort_keys=True, ensure_ascii=True, default=str)
        snapshot_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        return {
            "snapshot_version": "feature_snapshot_v1",
            "snapshot_hash": snapshot_hash,
            "data_bundle_id": f"bundle-{snapshot_hash}",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        }
