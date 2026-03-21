from __future__ import annotations


class IntentAlignerAgent:
    """Translates user preference inputs into structured trading constraints."""

    def build_trading_preferences(
        self,
        trading_frequency: str,
        preferred_timeframe: str,
        rationale: str | None = None,
    ) -> dict[str, str]:
        descriptions = {
            "low": "低频交易意味着更少操作次数，更强调等待和耐心，不适合频繁追逐盘中波动。",
            "medium": "中频交易强调节奏和过滤，允许阶段性出手，但仍需避免噪音驱动。",
            "high": "高频交易意味着更高盯盘要求和更高执行密度，用户需要接受更频繁的信号与波动。",
        }
        timeframe_notes = {
            "minute": "分钟线机会更多，但噪音和成本也更高，适合高频或盘中型用户。",
            "daily": "日线更适合大多数个人交易者，能过滤大量盘中噪音。",
            "weekly": "周线更强调趋势和耐心，适合低频和波段型用户。",
        }
        return {
            "trading_frequency": trading_frequency,
            "preferred_timeframe": preferred_timeframe,
            "frequency_description": descriptions[trading_frequency],
            "timeframe_description": timeframe_notes[preferred_timeframe],
            "rationale": rationale or "",
        }

    def detect_preference_conflict(
        self,
        behavioral_report: dict | None,
        trading_preferences: dict | None,
    ) -> dict[str, str] | None:
        if not behavioral_report or not trading_preferences:
            return None
        recommended_frequency = behavioral_report.get("recommended_trading_frequency")
        recommended_timeframe = behavioral_report.get("recommended_timeframe")
        selected_frequency = trading_preferences.get("trading_frequency")
        selected_timeframe = trading_preferences.get("preferred_timeframe")
        if selected_frequency == recommended_frequency and selected_timeframe == recommended_timeframe:
            return None
        severe = (
            recommended_frequency == "low" and selected_frequency == "high"
        ) or (
            recommended_timeframe == "weekly" and selected_timeframe == "minute"
        )
        warning = (
            f"你的测试结果更推荐 {recommended_frequency} 频次和 {recommended_timeframe} 周期，"
            f"但你当前选择了 {selected_frequency} 频次和 {selected_timeframe} 周期。"
            " 这意味着你未来更可能在噪音、盯盘强度或执行纪律上出现偏离。"
        )
        return {"level": "high" if severe else "warning", "warning": warning}
