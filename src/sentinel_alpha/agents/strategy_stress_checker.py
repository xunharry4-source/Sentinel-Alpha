from __future__ import annotations


class StrategyStressCheckerAgent:
    """Rejects fragile or overfit candidates under user-behavior constraints."""

    def evaluate(
        self,
        strategy: dict,
        candidate: dict,
        behavior: dict,
        compatibility: float,
    ) -> dict:
        flags: list[str] = []
        required_fix_actions: list[str] = []
        metrics: dict[str, float | int | str] = {
            "behavioral_compatibility": round(compatibility, 4),
        }

        parameters = candidate.get("parameters") or {}
        metadata = candidate.get("metadata") or {}
        strategy_type = candidate.get("strategy_type") or strategy.get("strategy_type", "unknown")
        universe_size = int((metadata.get("selected_universe_size") or len(strategy.get("selected_universe") or [])) or 0)
        parameter_count = len(parameters)
        max_position_pct = float(parameters.get("max_position_pct", strategy.get("position_limit", 0.0)) or 0.0)
        noise_sensitivity = float(behavior.get("noise_sensitivity", 0.0) or 0.0)
        overtrading_tendency = float(behavior.get("overtrading_tendency", 0.0) or 0.0)
        bottom_fishing_tendency = float(behavior.get("bottom_fishing_tendency", 0.0) or 0.0)

        metrics["selected_universe_size"] = universe_size
        metrics["parameter_count"] = parameter_count
        metrics["max_position_pct"] = round(max_position_pct, 4)
        metrics["noise_sensitivity"] = round(noise_sensitivity, 4)
        metrics["overtrading_tendency"] = round(overtrading_tendency, 4)
        metrics["bottom_fishing_tendency"] = round(bottom_fishing_tendency, 4)
        metrics["strategy_type"] = strategy_type

        if universe_size < 5:
            flags.append("too_small_trade_universe")
            required_fix_actions.append("Expand the trade universe to at least 5 instruments or explicitly justify the narrow scope.")
        if compatibility < 0.55:
            flags.append("low_behavioral_compatibility")
            required_fix_actions.append("Re-iterate with stricter behavior alignment so the user is less likely to override execution.")
        if parameter_count > max(3, universe_size):
            flags.append("parameter_density_too_high")
            required_fix_actions.append("Reduce free parameters or broaden the train universe before the next iteration.")
        if noise_sensitivity > 0.75 and max_position_pct > 0.18:
            flags.append("position_limit_too_high_for_user_profile")
            required_fix_actions.append("Lower position limits for this user profile before re-running stress validation.")
        if overtrading_tendency > 0.85:
            flags.append("manual_intervention_risk_high")
            required_fix_actions.append("Increase confirmation thresholds or cooldown periods to reduce intervention churn.")
        if strategy_type == "mean_reversion_aligned" and bottom_fishing_tendency > 0.45:
            flags.append("mean_reversion_conflicts_with_bottom_fishing_profile")
            required_fix_actions.append("Switch strategy family or add multi-timeframe confirmation against premature bottom fishing.")
        if strategy_type == "trend_following_aligned" and compatibility < 0.65:
            flags.append("trend_following_not_stable_under_current_profile")
            required_fix_actions.append("Tighten the trend filter or select a less behavior-sensitive strategy family.")

        score = 1.0
        score -= 0.30 if universe_size < 5 else 0.0
        score -= 0.35 if compatibility < 0.55 else 0.10 if compatibility < 0.70 else 0.0
        score -= 0.15 if parameter_count > max(3, universe_size) else 0.0
        score -= 0.15 if noise_sensitivity > 0.75 and max_position_pct > 0.18 else 0.0
        score -= 0.10 if overtrading_tendency > 0.85 else 0.0
        score -= 0.20 if strategy_type == "mean_reversion_aligned" and bottom_fishing_tendency > 0.45 else 0.0
        score -= 0.10 if strategy_type == "trend_following_aligned" and compatibility < 0.65 else 0.0
        score = max(0.0, round(score, 2))

        status = "pass"
        if any(
            flag in flags
            for flag in (
                "too_small_trade_universe",
                "low_behavioral_compatibility",
                "parameter_density_too_high",
                "mean_reversion_conflicts_with_bottom_fishing_profile",
            )
        ):
            status = "fail"
        elif flags:
            status = "warning"

        summary = "Stress and overfit review is within tolerance."
        detail = "The candidate remains reasonably stable across behavior alignment, universe breadth, and parameter density checks."
        if status == "warning":
            summary = "Stress review found fragility that should be addressed before approval."
            detail = "The candidate is usable for research, but user behavior or concentration risk could break it in live trading."
        if status == "fail":
            summary = "Stress and overfit review rejected this strategy version."
            detail = "The candidate is too fragile under current user behavior, universe breadth, or parameter concentration assumptions."

        return {
            "check_type": "stress_overfit",
            "status": status,
            "title": "Strategy Stress and Overfit Checker",
            "score": score,
            "summary": summary,
            "detail": detail,
            "flags": flags,
            "required_fix_actions": required_fix_actions,
            "metrics": metrics,
        }
