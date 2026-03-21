from __future__ import annotations

from datetime import date


class SimpleBacktestEngine:
    """Minimal historical-bar backtest engine for daily split evaluation."""

    def evaluate(
        self,
        bars: list[dict] | dict[str, list[dict]],
        exposure: float | dict[str, float],
        split_plan: dict,
        fee_bps: float = 5.0,
        slippage_bps: float = 3.0,
    ) -> dict | None:
        normalized = self._normalize_input(bars)
        if not normalized:
            return None

        coverage = self._build_coverage_summary(normalized, split_plan)
        result: dict[str, dict | list] = {}
        for split_name in ("train", "validation", "test"):
            window = split_plan.get(split_name, {})
            window_bars = self._slice_bars(normalized, window.get("start"), window.get("end"))
            metrics = self._window_metrics(window_bars, exposure, fee_bps=fee_bps, slippage_bps=slippage_bps)
            if metrics is None:
                return None
            result[split_name] = {"period": window, **metrics}

        walk_forward = []
        for window in split_plan.get("walk_forward_windows", []):
            window_bars = self._slice_bars(normalized, window.get("validation_start"), window.get("validation_end"))
            metrics = self._window_metrics(window_bars, exposure, fee_bps=fee_bps, slippage_bps=slippage_bps)
            if metrics is None:
                continue
            walk_forward.append(
                {
                    "window_id": window.get("window_id"),
                    "train_start": window.get("train_start"),
                    "train_end": window.get("train_end"),
                    "validation_start": window.get("validation_start"),
                    "validation_end": window.get("validation_end"),
                    **metrics,
                }
            )
        result["walk_forward"] = walk_forward
        result["coverage"] = coverage
        return result

    def _normalize_input(self, bars: list[dict] | dict[str, list[dict]]) -> dict[str, list[dict]]:
        if isinstance(bars, dict):
            normalized = {symbol: self._normalize_bars(symbol_bars) for symbol, symbol_bars in bars.items()}
        else:
            normalized = {"__default__": self._normalize_bars(bars)}
        return {symbol: symbol_bars for symbol, symbol_bars in normalized.items() if len(symbol_bars) >= 20}

    def _normalize_bars(self, bars: list[dict]) -> list[dict]:
        normalized: list[dict] = []
        for item in bars:
            timestamp = str(item.get("timestamp", ""))[:10]
            if not timestamp:
                continue
            try:
                normalized.append(
                    {
                        "date": date.fromisoformat(timestamp),
                        "open": float(item.get("open") or item.get("open_price") or 0.0),
                        "high": float(item.get("high") or item.get("high_price") or 0.0),
                        "low": float(item.get("low") or item.get("low_price") or 0.0),
                        "close": float(item.get("close") or item.get("close_price") or 0.0),
                        "volume": float(item.get("volume") or 0.0),
                    }
                )
            except (TypeError, ValueError):
                continue
        return sorted(normalized, key=lambda item: item["date"])

    def _slice_bars(self, bars: dict[str, list[dict]], start: str | None, end: str | None) -> dict[str, list[dict]]:
        if not start or not end:
            return {}
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
        result: dict[str, list[dict]] = {}
        for symbol, symbol_bars in bars.items():
            sliced = [bar for bar in symbol_bars if start_date <= bar["date"] <= end_date]
            if sliced:
                result[symbol] = sliced
        return result

    def _window_metrics(
        self,
        bars: dict[str, list[dict]],
        exposure: float | dict[str, float],
        *,
        fee_bps: float,
        slippage_bps: float,
    ) -> dict | None:
        if not bars:
            return None
        exposure_map = exposure if isinstance(exposure, dict) else {symbol: exposure for symbol in bars}
        returns: list[float] = []
        equity = 1.0
        peak = 1.0
        max_drawdown = 0.0
        max_loss = 0.0
        wins = 0
        target_exposure_map = {symbol: float(exposure_map.get(symbol, 0.0)) for symbol in bars}
        active_weights = {symbol: weight for symbol, weight in target_exposure_map.items() if abs(weight) > 0}
        gross_target = sum(abs(weight) for weight in active_weights.values())
        net_target = sum(active_weights.values())
        turnover_series: list[float] = []
        avg_volume_series: list[float] = []

        min_length = min(len(symbol_bars) for symbol_bars in bars.values())
        if min_length < 2:
            return None

        for index in range(1, min_length):
            strategy_return = 0.0
            active_symbols = 0
            asset_returns: dict[str, float] = {}
            volume_points: list[float] = []
            for symbol, symbol_bars in bars.items():
                previous_close = symbol_bars[index - 1]["close"]
                close_price = symbol_bars[index]["close"]
                if previous_close <= 0:
                    continue
                active_symbols += 1
                asset_return = (close_price / previous_close) - 1.0
                asset_returns[symbol] = asset_return
                symbol_exposure = float(exposure_map.get(symbol, 0.0))
                strategy_return += asset_return * symbol_exposure
                volume_points.append(float(symbol_bars[index].get("volume") or 0.0))
            if active_symbols == 0:
                continue
            transaction_cost = (fee_bps + slippage_bps) / 10000.0
            strategy_return -= transaction_cost
            returns.append(strategy_return)
            if strategy_return > 0:
                wins += 1
            equity *= 1.0 + strategy_return
            peak = max(peak, equity)
            drawdown = 1.0 - (equity / peak)
            max_drawdown = max(max_drawdown, drawdown)
            max_loss = max(max_loss, max(0.0, -strategy_return))
            if volume_points:
                avg_volume_series.append(sum(volume_points) / len(volume_points))
            if len(active_weights) > 1 and gross_target > 0:
                drift_values = {
                    symbol: weight * (1.0 + asset_returns.get(symbol, 0.0))
                    for symbol, weight in active_weights.items()
                }
                gross_after = sum(abs(value) for value in drift_values.values())
                if gross_after > 0:
                    drift_weights = {symbol: value / gross_after for symbol, value in drift_values.items()}
                    target_weights = {symbol: weight / gross_target for symbol, weight in active_weights.items()}
                    turnover_pct = 50.0 * sum(
                        abs(target_weights.get(symbol, 0.0) - drift_weights.get(symbol, 0.0))
                        for symbol in active_weights
                    )
                    turnover_series.append(round(turnover_pct, 4))

        if not returns:
            return None
        return {
            "expected_return_pct": round((equity - 1.0) * 100.0, 2),
            "win_rate_pct": round((wins / len(returns)) * 100.0, 2),
            "drawdown_pct": round(max_drawdown * 100.0, 2),
            "max_loss_pct": round(max_loss * 100.0, 2),
            "observation_count": len(returns),
            "active_symbol_count": len(active_weights),
            "gross_exposure_pct": round(gross_target * 100.0, 2),
            "net_exposure_pct": round(net_target * 100.0, 2),
            "avg_daily_turnover_proxy_pct": round(sum(turnover_series) / len(turnover_series), 4) if turnover_series else 0.0,
            "avg_volume": round(sum(avg_volume_series) / len(avg_volume_series), 2) if avg_volume_series else 0.0,
        }

    def _build_coverage_summary(self, bars: dict[str, list[dict]], split_plan: dict) -> dict:
        symbols = sorted(bars.keys())
        total_bar_count = sum(len(symbol_bars) for symbol_bars in bars.values())
        symbol_bar_counts = {symbol: len(symbol_bars) for symbol, symbol_bars in bars.items()}
        min_date = min((symbol_bars[0]["date"] for symbol_bars in bars.values() if symbol_bars), default=None)
        max_date = max((symbol_bars[-1]["date"] for symbol_bars in bars.values() if symbol_bars), default=None)
        split_bar_counts = {}
        for split_name in ("train", "validation", "test"):
            window = split_plan.get(split_name, {})
            window_bars = self._slice_bars(bars, window.get("start"), window.get("end"))
            split_bar_counts[split_name] = {
                "symbol_count": len(window_bars),
                "bar_count": sum(len(symbol_bars) for symbol_bars in window_bars.values()),
            }
        return {
            "symbol_count": len(symbols),
            "symbols": symbols,
            "total_bar_count": total_bar_count,
            "symbol_bar_counts": symbol_bar_counts,
            "date_range": {
                "start": min_date.isoformat() if min_date else None,
                "end": max_date.isoformat() if max_date else None,
            },
            "walk_forward_window_count": len(split_plan.get("walk_forward_windows", [])),
            "split_bar_counts": split_bar_counts,
        }
