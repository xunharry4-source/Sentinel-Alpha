from __future__ import annotations

from datetime import date
from typing import Protocol


class StrategyMetricsEngine(Protocol):
    def evaluate_candidate(
        self,
        *,
        candidate: dict,
        objective_metric: str,
        targets: dict[str, float],
        variant_index: int,
        dataset_plan: dict,
        backtest_engine,
        market_data,
        settings,
    ) -> dict:
        """Return the canonical strategy evaluation payload."""


class DefaultStrategyMetricsEngine:
    """Canonical strategy metrics implementation for surrogate and local-history evaluation."""

    def evaluate_candidate(
        self,
        *,
        candidate: dict,
        objective_metric: str,
        targets: dict[str, float],
        variant_index: int,
        dataset_plan: dict,
        backtest_engine,
        market_data,
        settings,
    ) -> dict:
        real_backtest = self._evaluate_candidate_with_local_history(
            candidate=candidate,
            objective_metric=objective_metric,
            targets=targets,
            dataset_plan=dataset_plan,
            backtest_engine=backtest_engine,
            market_data=market_data,
            settings=settings,
        )
        if real_backtest is not None:
            return real_backtest

        avg_conviction = sum(float(item.get("conviction", 0.0)) for item in candidate.get("signals", [])) / max(1, len(candidate.get("signals", [])))
        max_position = float(candidate.get("parameters", {}).get("max_position_pct", 0.12) or 0.12)
        hard_stop = float(candidate.get("parameters", {}).get("hard_stop_loss_pct", 0.06) or 0.06)
        expected_return_pct = round(8 + avg_conviction * 18 + variant_index * 0.7, 2)
        win_rate_pct = round(48 + avg_conviction * 22 - variant_index * 0.4, 2)
        drawdown_pct = round(max(3.0, hard_stop * 100 * 1.6 + max_position * 12), 2)
        max_loss_pct = round(max(2.0, hard_stop * 100), 2)
        objective_value = {
            "return": expected_return_pct,
            "win_rate": win_rate_pct,
            "drawdown": -drawdown_pct,
            "max_loss": -max_loss_pct,
        }[objective_metric]
        split_metrics = self._build_split_metrics(
            expected_return_pct=expected_return_pct,
            win_rate_pct=win_rate_pct,
            drawdown_pct=drawdown_pct,
            max_loss_pct=max_loss_pct,
            variant_index=variant_index,
            dataset_plan=dataset_plan,
            objective_metric=objective_metric,
            targets=targets,
        )
        annual_performance = self._build_surrogate_annual_performance(
            dataset_plan=dataset_plan,
            expected_return_pct=split_metrics["test"]["expected_return_pct"],
            win_rate_pct=split_metrics["test"]["win_rate_pct"],
            drawdown_pct=split_metrics["test"]["drawdown_pct"],
            max_loss_pct=split_metrics["test"]["max_loss_pct"],
            variant_index=variant_index,
        )
        split_metrics["full_period"] = self._build_surrogate_full_period(dataset_plan, split_metrics, annual_performance)
        score = split_metrics["test"]["objective_score"]
        stability_score = split_metrics["stability"]["score"]
        return {
            "expected_return_pct": expected_return_pct,
            "win_rate_pct": win_rate_pct,
            "drawdown_pct": drawdown_pct,
            "max_loss_pct": max_loss_pct,
            "objective_metric": objective_metric,
            "objective_value": objective_value,
            "objective_score": score,
            "dataset_evaluation": split_metrics,
            "validation_objective_score": split_metrics["validation"]["objective_score"],
            "test_objective_score": split_metrics["test"]["objective_score"],
            "walk_forward_score": split_metrics["stability"]["walk_forward_score"],
            "stability_score": stability_score,
            "evaluation_source": "heuristic_surrogate",
            "coverage_summary": {
                "symbol_count": len(list(dict.fromkeys(signal.get("symbol") for signal in candidate.get("signals", []) if signal.get("symbol")))),
                "symbols": sorted(list(dict.fromkeys(signal.get("symbol") for signal in candidate.get("signals", []) if signal.get("symbol")))),
                "total_bar_count": None,
                "symbol_bar_counts": {},
                "date_range": {
                    "start": dataset_plan.get("train", {}).get("start"),
                    "end": dataset_plan.get("test", {}).get("end"),
                },
                "walk_forward_window_count": len(dataset_plan.get("walk_forward_windows", [])),
                "split_bar_counts": {
                    "train": {"symbol_count": None, "bar_count": None},
                    "validation": {"symbol_count": None, "bar_count": None},
                    "test": {"symbol_count": None, "bar_count": None},
                },
            },
            "annual_performance": annual_performance,
        }

    def _build_split_metrics(
        self,
        *,
        expected_return_pct: float,
        win_rate_pct: float,
        drawdown_pct: float,
        max_loss_pct: float,
        variant_index: int,
        dataset_plan: dict,
        objective_metric: str,
        targets: dict[str, float],
    ) -> dict:
        split_adjustments = {
            "train": {"return": 1.08, "win_rate": 1.03, "drawdown": 0.94, "max_loss": 0.95},
            "validation": {"return": 0.98, "win_rate": 0.99, "drawdown": 1.03, "max_loss": 1.04},
            "test": {"return": 0.94, "win_rate": 0.97, "drawdown": 1.08, "max_loss": 1.09},
        }
        result: dict[str, dict] = {}
        for split_name, multipliers in split_adjustments.items():
            split_return = round(expected_return_pct * multipliers["return"], 2)
            split_win_rate = round(win_rate_pct * multipliers["win_rate"], 2)
            split_drawdown = round(drawdown_pct * multipliers["drawdown"], 2)
            split_max_loss = round(max_loss_pct * multipliers["max_loss"], 2)
            gross_exposure_pct = round(100.0 * min(1.0, 0.22 + 0.03 * max(0, variant_index)), 2)
            net_exposure_pct = round(gross_exposure_pct * 0.85, 2)
            result[split_name] = {
                "period": dataset_plan[split_name],
                "expected_return_pct": split_return,
                "win_rate_pct": split_win_rate,
                "drawdown_pct": split_drawdown,
                "max_loss_pct": split_max_loss,
                "observation_count": 0,
                "active_symbol_count": 0,
                "gross_exposure_pct": gross_exposure_pct,
                "net_exposure_pct": net_exposure_pct,
                "avg_daily_turnover_proxy_pct": round(2.0 + variant_index * 0.4, 2),
                "avg_volume": 0.0,
                "objective_score": self._objective_score(
                    objective_metric=objective_metric,
                    targets=targets,
                    expected_return_pct=split_return,
                    win_rate_pct=split_win_rate,
                    drawdown_pct=split_drawdown,
                    max_loss_pct=split_max_loss,
                ),
            }

        walk_forward_results = []
        for index, window in enumerate(dataset_plan.get("walk_forward_windows", []), start=1):
            wf_return = round(expected_return_pct * (0.95 - index * 0.01) + variant_index * 0.15, 2)
            wf_win_rate = round(win_rate_pct * (0.985 - index * 0.005), 2)
            wf_drawdown = round(drawdown_pct * (1.03 + index * 0.01), 2)
            wf_max_loss = round(max_loss_pct * (1.04 + index * 0.01), 2)
            walk_forward_results.append(
                {
                    "window_id": window["window_id"],
                    "train_start": window["train_start"],
                    "train_end": window["train_end"],
                    "validation_start": window["validation_start"],
                    "validation_end": window["validation_end"],
                    "objective_score": self._objective_score(
                        objective_metric=objective_metric,
                        targets=targets,
                        expected_return_pct=wf_return,
                        win_rate_pct=wf_win_rate,
                        drawdown_pct=wf_drawdown,
                        max_loss_pct=wf_max_loss,
                    ),
                    "expected_return_pct": wf_return,
                    "win_rate_pct": wf_win_rate,
                    "drawdown_pct": wf_drawdown,
                    "max_loss_pct": wf_max_loss,
                    "observation_count": 0,
                    "active_symbol_count": 0,
                    "gross_exposure_pct": round(100.0 * min(1.0, 0.22 + 0.03 * max(0, variant_index)), 2),
                    "net_exposure_pct": round(100.0 * min(1.0, 0.22 + 0.03 * max(0, variant_index)) * 0.85, 2),
                    "avg_daily_turnover_proxy_pct": round(2.0 + variant_index * 0.4, 2),
                    "avg_volume": 0.0,
                }
            )

        walk_forward_score = round(sum(item["objective_score"] for item in walk_forward_results) / max(1, len(walk_forward_results)), 4)
        stability_gap = abs(result["train"]["objective_score"] - result["test"]["objective_score"])
        stability_score = round(max(0.0, 1 - stability_gap) * 0.6 + walk_forward_score * 0.4, 4)
        result["walk_forward"] = walk_forward_results
        result["stability"] = {
            "score": stability_score,
            "walk_forward_score": walk_forward_score,
            "train_test_gap": round(stability_gap, 4),
        }
        return result

    def _objective_score(
        self,
        *,
        objective_metric: str,
        targets: dict[str, float],
        expected_return_pct: float,
        win_rate_pct: float,
        drawdown_pct: float,
        max_loss_pct: float,
    ) -> float:
        score = 0.0
        score += expected_return_pct / max(1.0, targets["target_return_pct"]) * (0.5 if objective_metric == "return" else 0.2)
        score += win_rate_pct / max(1.0, targets["target_win_rate_pct"]) * (0.5 if objective_metric == "win_rate" else 0.2)
        score += max(0.0, 1 - drawdown_pct / max(1.0, targets["target_drawdown_pct"])) * (0.5 if objective_metric == "drawdown" else 0.3)
        score += max(0.0, 1 - max_loss_pct / max(1.0, targets["target_max_loss_pct"])) * (0.5 if objective_metric == "max_loss" else 0.3)
        return round(score, 4)

    def _evaluate_candidate_with_local_history(
        self,
        *,
        candidate: dict,
        objective_metric: str,
        targets: dict[str, float],
        dataset_plan: dict,
        backtest_engine,
        market_data,
        settings,
    ) -> dict | None:
        bars_by_symbol: dict[str, list[dict]] = {}
        exposure_by_symbol: dict[str, float] = {}
        max_position = float(candidate.get("parameters", {}).get("max_position_pct", 0.12) or 0.12)
        for signal in candidate.get("signals", []):
            symbol = signal.get("symbol")
            if not symbol:
                continue
            history = self._fetch_real_history(market_data=market_data, settings=settings, symbol=symbol)
            if history is None:
                continue
            bars = history.get("bars", [])
            if not bars:
                continue
            bars_by_symbol[symbol] = bars
            action = str(signal.get("action", "hold")).lower()
            direction = 1.0 if action == "buy" else -1.0 if action == "sell" else 0.0
            exposure_by_symbol[symbol] = direction * float(signal.get("conviction", 0.0) or 0.0) * max_position
        if not bars_by_symbol:
            return None
        split_metrics = backtest_engine.evaluate(bars=bars_by_symbol, exposure=exposure_by_symbol, split_plan=dataset_plan)
        if split_metrics is None:
            return None
        for split_name in ("train", "validation", "test"):
            metrics = split_metrics.get(split_name)
            if metrics is None:
                return None
            metrics["objective_score"] = self._objective_score(
                objective_metric=objective_metric,
                targets=targets,
                expected_return_pct=metrics["expected_return_pct"],
                win_rate_pct=metrics["win_rate_pct"],
                drawdown_pct=metrics["drawdown_pct"],
                max_loss_pct=metrics["max_loss_pct"],
            )
        walk_forward_results = []
        for window in split_metrics.get("walk_forward", []):
            walk_forward_results.append(
                {
                    **window,
                    "objective_score": self._objective_score(
                        objective_metric=objective_metric,
                        targets=targets,
                        expected_return_pct=window["expected_return_pct"],
                        win_rate_pct=window["win_rate_pct"],
                        drawdown_pct=window["drawdown_pct"],
                        max_loss_pct=window["max_loss_pct"],
                    ),
                }
            )
        walk_forward_score = round(sum(item["objective_score"] for item in walk_forward_results) / max(1, len(walk_forward_results)), 4)
        stability_gap = abs(split_metrics["train"]["objective_score"] - split_metrics["test"]["objective_score"])
        stability_score = round(max(0.0, 1 - stability_gap) * 0.6 + walk_forward_score * 0.4, 4)
        dataset_evaluation = {
            "train": split_metrics["train"],
            "validation": split_metrics["validation"],
            "test": split_metrics["test"],
            "walk_forward": walk_forward_results,
            "full_period": split_metrics.get("full_period") or {},
            "stability": {
                "score": stability_score,
                "walk_forward_score": walk_forward_score,
                "train_test_gap": round(stability_gap, 4),
            },
        }
        return {
            "expected_return_pct": split_metrics["test"]["expected_return_pct"],
            "win_rate_pct": split_metrics["test"]["win_rate_pct"],
            "drawdown_pct": split_metrics["test"]["drawdown_pct"],
            "max_loss_pct": split_metrics["test"]["max_loss_pct"],
            "objective_metric": objective_metric,
            "objective_value": {
                "return": split_metrics["test"]["expected_return_pct"],
                "win_rate": split_metrics["test"]["win_rate_pct"],
                "drawdown": -split_metrics["test"]["drawdown_pct"],
                "max_loss": -split_metrics["test"]["max_loss_pct"],
            }[objective_metric],
            "objective_score": split_metrics["test"]["objective_score"],
            "dataset_evaluation": dataset_evaluation,
            "validation_objective_score": split_metrics["validation"]["objective_score"],
            "test_objective_score": split_metrics["test"]["objective_score"],
            "walk_forward_score": walk_forward_score,
            "stability_score": stability_score,
            "evaluation_source": "local_history_backtest",
            "coverage_summary": split_metrics.get("coverage") or {},
            "annual_performance": (split_metrics.get("full_period") or {}).get("annual_breakdown", []),
        }

    def _fetch_real_history(self, *, market_data, settings, symbol: str) -> dict | None:
        for provider in settings.market_data_enabled_providers:
            try:
                history = market_data.fetch_history(symbol=symbol, interval="1d", provider=provider)
            except Exception:
                continue
            if history.get("bars"):
                return history
        return None

    def _build_surrogate_annual_performance(
        self,
        *,
        dataset_plan: dict,
        expected_return_pct: float,
        win_rate_pct: float,
        drawdown_pct: float,
        max_loss_pct: float,
        variant_index: int,
    ) -> list[dict]:
        start = dataset_plan.get("train", {}).get("start")
        end = dataset_plan.get("test", {}).get("end")
        if not start or not end:
            return []
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
        year_ranges: list[tuple[int, date, date]] = []
        current_year = start_date.year
        while current_year <= end_date.year:
            year_start = max(start_date, date(current_year, 1, 1))
            year_end = min(end_date, date(current_year, 12, 31))
            if year_end >= year_start:
                year_ranges.append((current_year, year_start, year_end))
            current_year += 1
        if not year_ranges:
            return []
        total_days = sum((year_end - year_start).days + 1 for _, year_start, year_end in year_ranges)
        weighted_windows = []
        for index, (year, year_start, year_end) in enumerate(year_ranges, start=1):
            days = (year_end - year_start).days + 1
            weight = days * (1 + 0.06 * (index - 1))
            weighted_windows.append((year, year_start, year_end, days, weight))
        total_weight = sum(item[4] for item in weighted_windows) or 1.0
        compounded_equity = 1.0
        rows = []
        for index, (year, year_start, year_end, days, weight) in enumerate(weighted_windows, start=1):
            year_fraction = days / max(1, total_days)
            year_return_pct = round(expected_return_pct * (weight / total_weight), 2)
            compounded_equity *= 1.0 + year_return_pct / 100.0
            rows.append(
                {
                    "year": year,
                    "start": year_start.isoformat(),
                    "end": year_end.isoformat(),
                    "return_pct": year_return_pct,
                    "compounded_return_pct": round((compounded_equity - 1.0) * 100.0, 2),
                    "max_loss_pct": round(max_loss_pct * (0.9 + 0.08 * index), 2),
                    "max_drawdown_pct": round(drawdown_pct * (0.92 + 0.06 * index), 2),
                    "win_rate_pct": round(max(0.0, min(100.0, win_rate_pct - 1.2 + index * 0.4 - variant_index * 0.2)), 2),
                    "avg_loss_trade_pct": round(max(0.05, max_loss_pct * (0.42 + year_fraction * 0.4)), 2),
                    "avg_gain_trade_pct": round(max(0.05, (abs(year_return_pct) * 0.18) + (win_rate_pct / 100.0) + variant_index * 0.04), 2),
                    "winning_trade_count": max(1, int(round(days / 14 * max(0.25, win_rate_pct / 100.0)))),
                    "losing_trade_count": max(1, int(round(days / 18 * max(0.15, 1 - win_rate_pct / 100.0)))),
                    "observation_count": max(1, days - 1),
                }
            )
        return rows

    def _build_surrogate_full_period(self, dataset_plan: dict, split_metrics: dict, annual_performance: list[dict]) -> dict:
        total_winning = sum(int(item.get("winning_trade_count", 0)) for item in annual_performance)
        total_losing = sum(int(item.get("losing_trade_count", 0)) for item in annual_performance)
        weighted_avg_loss = (
            round(
                sum(float(item.get("avg_loss_trade_pct", 0.0)) * max(1, int(item.get("losing_trade_count", 0))) for item in annual_performance)
                / max(1, total_losing),
                2,
            )
            if annual_performance
            else 0.0
        )
        weighted_avg_gain = (
            round(
                sum(float(item.get("avg_gain_trade_pct", 0.0)) * max(1, int(item.get("winning_trade_count", 0))) for item in annual_performance)
                / max(1, total_winning),
                2,
            )
            if annual_performance
            else 0.0
        )
        return {
            "period": {
                "start": dataset_plan.get("train", {}).get("start"),
                "end": dataset_plan.get("test", {}).get("end"),
            },
            "expected_return_pct": split_metrics["test"]["expected_return_pct"],
            "compounded_return_pct": split_metrics["test"]["expected_return_pct"],
            "win_rate_pct": split_metrics["test"]["win_rate_pct"],
            "drawdown_pct": split_metrics["test"]["drawdown_pct"],
            "max_loss_pct": split_metrics["test"]["max_loss_pct"],
            "avg_loss_trade_pct": weighted_avg_loss,
            "avg_gain_trade_pct": weighted_avg_gain,
            "winning_trade_count": total_winning,
            "losing_trade_count": total_losing,
            "annual_breakdown": annual_performance,
        }
