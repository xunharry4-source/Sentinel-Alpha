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

        min_length = min(len(symbol_bars) for symbol_bars in bars.values())
        if min_length < 2:
            return None

        for index in range(1, min_length):
            strategy_return = 0.0
            active_symbols = 0
            for symbol, symbol_bars in bars.items():
                previous_close = symbol_bars[index - 1]["close"]
                close_price = symbol_bars[index]["close"]
                if previous_close <= 0:
                    continue
                active_symbols += 1
                asset_return = (close_price / previous_close) - 1.0
                symbol_exposure = float(exposure_map.get(symbol, 0.0))
                strategy_return += asset_return * symbol_exposure
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

        if not returns:
            return None
        return {
            "expected_return_pct": round((equity - 1.0) * 100.0, 2),
            "win_rate_pct": round((wins / len(returns)) * 100.0, 2),
            "drawdown_pct": round(max_drawdown * 100.0, 2),
            "max_loss_pct": round(max_loss * 100.0, 2),
        }
