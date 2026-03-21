from __future__ import annotations


class StrategyIntegrityCheckerAgent:
    """Rejects future leakage, cheating markers, and impossible confidence assumptions."""

    def evaluate(self, strategy: dict, candidate: dict) -> dict:
        flags: list[str] = []
        required_fix_actions: list[str] = []
        metrics: dict[str, float | int | str] = {}

        parameters = candidate.get("parameters") or {}
        metadata = candidate.get("metadata") or {}
        signals = candidate.get("signals") or []
        rationale_tokens = " ".join(
            " ".join(signal.get("rationale") or [])
            for signal in signals
            if isinstance(signal, dict)
        ).lower()
        suspicious_terms = [
            "future",
            "tomorrow",
            "next candle",
            "post-close result",
            "guaranteed",
            "known earnings result",
            "after the event",
        ]
        detected_terms = [term for term in suspicious_terms if term in rationale_tokens]
        if detected_terms:
            flags.append(f"future_leakage_terms={','.join(detected_terms)}")
            required_fix_actions.append("Remove any rationale or feature that references unavailable future information.")

        parameter_keys = {str(key).lower() for key in parameters}
        metadata_keys = {str(key).lower() for key in metadata}
        suspicious_keys = [
            key
            for key in parameter_keys | metadata_keys
            if any(token in key for token in ("future", "leak", "cheat", "oracle", "perfect", "winrate"))
        ]
        if suspicious_keys:
            flags.append(f"suspicious_keys={','.join(sorted(suspicious_keys))}")
            required_fix_actions.append("Rename or remove parameters that imply future leakage or engineered win logic.")

        max_conviction = max(
            (float(signal.get("conviction", 0.0)) for signal in signals if isinstance(signal, dict)),
            default=0.0,
        )
        metrics["max_signal_conviction"] = round(max_conviction, 4)
        if max_conviction >= 0.97:
            flags.append("win_coding_conviction_spike")
            required_fix_actions.append("Reduce impossible conviction levels and justify confidence with observable features only.")

        iteration_no = int(strategy.get("iteration_no", 1))
        metrics["iteration_no"] = iteration_no
        metrics["strategy_type"] = str(candidate.get("strategy_type", strategy.get("strategy_type", "unknown")))
        if iteration_no > 5:
            flags.append("excessive_manual_iteration_count")
            required_fix_actions.append("Review the optimization loop for silent curve fitting across too many manual revisions.")

        universe_size = int((metadata.get("selected_universe_size") or len(strategy.get("selected_universe") or [])) or 0)
        metrics["selected_universe_size"] = universe_size
        if universe_size <= 1:
            flags.append("single_asset_candidate")
            required_fix_actions.append("Expand the universe or attach a benchmark basket before approving the strategy.")

        score = 1.0
        score -= 0.45 if detected_terms else 0.0
        score -= 0.25 if suspicious_keys else 0.0
        score -= 0.25 if max_conviction >= 0.97 else 0.0
        score -= 0.10 if iteration_no > 5 else 0.0
        score -= 0.10 if universe_size <= 1 else 0.0
        score = max(0.0, round(score, 2))

        status = "pass"
        if detected_terms or suspicious_keys or max_conviction >= 0.97:
            status = "fail"
        elif flags:
            status = "warning"

        summary = "No obvious future leakage or engineered win logic was found."
        detail = "Integrity checks passed on rationale, parameter naming, conviction profile, and iteration path."
        if status == "warning":
            summary = "Integrity review found weak spots that need manual attention before release."
            detail = "The candidate is not outright invalid, but its optimization path or concentration setup increases audit risk."
        if status == "fail":
            summary = "Integrity review rejected this strategy version."
            detail = "The candidate exposes future-information leakage, cheating-like markers, or impossible confidence assumptions."

        return {
            "check_type": "integrity",
            "status": status,
            "title": "Strategy Integrity Checker",
            "score": score,
            "summary": summary,
            "detail": detail,
            "flags": flags,
            "required_fix_actions": required_fix_actions,
            "metrics": metrics,
        }
