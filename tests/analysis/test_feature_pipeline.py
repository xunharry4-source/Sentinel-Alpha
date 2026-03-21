from __future__ import annotations

from sentinel_alpha.analysis import SessionFeaturePipeline


def test_feature_pipeline_merges_behavior_market_and_intelligence_layers() -> None:
    pipeline = SessionFeaturePipeline()
    features = pipeline.build(
        behavioral_report={
            "noise_sensitivity": 0.7,
            "panic_sell_tendency": 0.5,
            "bottom_fishing_tendency": 0.4,
            "overtrading_tendency": 0.6,
            "hold_strength": 0.45,
        },
        profile_evolution={
            "effective_profile": {
                "noise_sensitivity": 0.72,
                "panic_sell_tendency": 0.52,
                "bottom_fishing_tendency": 0.38,
                "overtrading_tendency": 0.58,
                "hold_strength": 0.47,
            }
        },
        trading_preferences={
            "trading_frequency": "medium",
            "preferred_timeframe": "daily",
            "conflict_level": "warning",
        },
        market_snapshots=[
            {
                "symbol": "AAPL",
                "timeframe": "1d",
                "close_price": 192.5,
                "volume": 1234567,
                "regime_tag": "bull",
                "timestamp": "2026-03-21T10:00:00Z",
            }
        ],
        intelligence_runs=[
            {
                "run_id": "intel-3",
                "query": "AAPL",
                "document_count": 5,
                "generated_at": "2026-03-21T11:00:00Z",
                "report": {"factors": {"credibility_score": 0.64, "contradiction_score": 0.25}},
            }
        ],
        financials_runs=[{"run_id": "financials-2", "symbol": "AAPL", "provider": "sec", "generated_at": "2026-03-20T12:00:00Z", "factors": {"quality_score": 0.81}}],
        dark_pool_runs=[{"run_id": "dark-pool-2", "symbol": "AAPL", "provider": "finra", "generated_at": "2026-03-21T09:30:00Z", "factors": {"accumulation_score": 0.62}}],
        options_runs=[{"run_id": "options-2", "symbol": "AAPL", "provider": "yahoo_options", "expiration": "2026-04-17", "generated_at": "2026-03-21T09:45:00Z", "factors": {"options_pressure_score": 0.57}}],
    )

    assert features["behavioral"]["noise_sensitivity"] == 0.72
    assert features["market"]["symbol"] == "AAPL"
    assert features["preferences"]["preferred_timeframe"] == "daily"
    assert features["intelligence"]["factors"]["credibility_score"] == 0.64
    assert features["fundamentals"]["factors"]["quality_score"] == 0.81
    assert features["dark_pool"]["factors"]["accumulation_score"] == 0.62
    assert features["options"]["factors"]["options_pressure_score"] == 0.57
    assert features["data_quality"]["section_coverage_score"] == 1.0
    assert "behavioral" in features["data_quality"]["available_sections"]
    assert features["data_quality"]["provider_count"] == 3
    assert features["data_quality"]["freshness"]["known_timestamp_count"] == 5
    assert features["data_quality"]["freshness"]["max_gap_hours"] > 0
    assert isinstance(features["data_quality"]["alignment_warnings"], list)
    assert features["data_quality"]["quality_grade"] in {"healthy", "warning", "degraded"}
    assert features["data_quality"]["training_readiness"]["status"] in {"ready", "caution", "blocked"}
    assert features["meta"]["snapshot_version"] == "feature_snapshot_v1"
    assert features["meta"]["snapshot_hash"]
    assert features["meta"]["data_bundle_id"].startswith("bundle-")
    assert features["source_lineage"]["intelligence"]["run_id"] == "intel-3"
    assert features["source_lineage"]["fundamentals"]["run_id"] == "financials-2"
    assert features["source_lineage"]["dark_pool"]["provider"] == "finra"
    assert features["source_lineage"]["options"]["expiration"] == "2026-04-17"
