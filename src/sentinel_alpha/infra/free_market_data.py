from __future__ import annotations

from dataclasses import asdict, fields, is_dataclass
from copy import deepcopy
import csv
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sentinel_alpha.config import AppSettings, get_settings
from sentinel_alpha.domain.models import (
    DarkPoolRecord,
    DarkPoolSnapshot,
    FinancialStatementRecord,
    FinancialsSnapshot,
    OptionContractRecord,
    OptionsSnapshot,
    WeightedRecord,
)

try:
    import akshare as ak  # type: ignore
except ImportError:  # pragma: no cover
    ak = None  # type: ignore


class FreeMarketDataService:
    """Unified access layer for free and low-friction market data providers."""

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self._response_cache: dict[tuple, dict] = {}
        self._cache_hits = 0
        self._cache_misses = 0

    def provider_matrix(self) -> list[dict]:
        providers: list[dict] = []
        for name in self.settings.market_data_enabled_providers:
            config = self.settings.market_data_provider_configs.get(name, {})
            api_key_envs = self._provider_api_key_envs(config)
            api_key_present = any(os.getenv(env_name) for env_name in api_key_envs)
            enabled = bool(config.get("enabled", True))
            status = "ok"
            detail = "Provider is configured."
            if name == "akshare" and ak is None:
                status = "warning"
                detail = "akshare provider is enabled in config but akshare is not installed."
            elif api_key_envs and not api_key_present:
                status = "warning"
                detail = f"{name} provider is enabled but none of [{', '.join(api_key_envs)}] are set."
            providers.append(
                {
                    "provider": name,
                    "enabled": enabled,
                    "status": status,
                    "api_key_envs": api_key_envs,
                    "api_key_present": api_key_present,
                    "detail": detail,
                    "base_url": str(config.get("base_url", "")),
                }
            )
        return providers

    def fundamentals_provider_matrix(self) -> list[dict]:
        return self._generic_provider_matrix(
            self.settings.fundamentals_enabled_providers,
            self.settings.fundamentals_provider_configs,
            special_local_file_key="local_file",
        )

    def dark_pool_provider_matrix(self) -> list[dict]:
        return self._generic_provider_matrix(
            self.settings.dark_pool_enabled_providers,
            self.settings.dark_pool_provider_configs,
            special_local_file_key="local_file",
        )

    def options_provider_matrix(self) -> list[dict]:
        return self._generic_provider_matrix(
            self.settings.options_enabled_providers,
            self.settings.options_provider_configs,
            special_local_file_key="local_file",
        )

    def fetch_quote(self, symbol: str, provider: str | None = None) -> dict:
        resolved = self._resolve_provider(provider)
        cache_key = ("quote", resolved, symbol)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        if resolved == "yahoo":
            return self._cache_set(cache_key, self._quote_yahoo(symbol))
        if resolved == "alphavantage":
            return self._cache_set(cache_key, self._quote_alphavantage(symbol))
        if resolved == "finnhub":
            return self._cache_set(cache_key, self._quote_finnhub(symbol))
        if resolved == "akshare":
            return self._cache_set(cache_key, self._quote_akshare(symbol))
        if resolved == "local_file":
            return self._cache_set(cache_key, self._quote_local_file(symbol))
        raise ValueError(f"Unsupported market data provider: {resolved}")

    def fetch_history(
        self,
        symbol: str,
        interval: str = "1d",
        lookback: str = "6mo",
        provider: str | None = None,
    ) -> dict:
        resolved = self._resolve_provider(provider)
        cache_key = ("history", resolved, symbol, interval, lookback)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        if resolved == "yahoo":
            return self._cache_set(cache_key, self._history_yahoo(symbol, interval, lookback))
        if resolved == "alphavantage":
            return self._cache_set(cache_key, self._history_alphavantage(symbol, interval))
        if resolved == "finnhub":
            return self._cache_set(cache_key, self._history_finnhub(symbol, interval, lookback))
        if resolved == "akshare":
            return self._cache_set(cache_key, self._history_akshare(symbol))
        if resolved == "local_file":
            return self._cache_set(cache_key, self._history_local_file(symbol, interval))
        raise ValueError(f"Unsupported market data provider: {resolved}")

    def fetch_financials(self, symbol: str, provider: str | None = None) -> dict:
        resolved = self._resolve_typed_provider(provider, self.settings.fundamentals_default_provider, self.settings.fundamentals_enabled_providers)
        cache_key = ("financials", resolved, symbol)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        if resolved == "sec":
            payload = self._financials_sec(symbol)
            return self._cache_set(cache_key, self._attach_normalized_financials(payload))
        if resolved == "alphavantage":
            payload = self._financials_alphavantage(symbol)
            return self._cache_set(cache_key, self._attach_normalized_financials(payload))
        if resolved == "finnhub":
            payload = self._financials_finnhub(symbol)
            return self._cache_set(cache_key, self._attach_normalized_financials(payload))
        if resolved == "local_file":
            payload = self._read_local_json("fundamentals", symbol, "{symbol}_financials.json", "financials_filename")
            return self._cache_set(cache_key, self._attach_normalized_financials(payload))
        raise ValueError(f"Unsupported fundamentals provider: {resolved}")

    def fetch_dark_pool(self, symbol: str, provider: str | None = None) -> dict:
        resolved = self._resolve_typed_provider(provider, self.settings.dark_pool_default_provider, self.settings.dark_pool_enabled_providers)
        cache_key = ("dark_pool", resolved, symbol)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        if resolved == "finra":
            payload = self._dark_pool_finra(symbol)
            return self._cache_set(cache_key, self._attach_normalized_dark_pool(payload))
        if resolved == "local_file":
            payload = self._read_local_json("dark_pool", symbol, "{symbol}_dark_pool.json", "dark_pool_filename")
            return self._cache_set(cache_key, self._attach_normalized_dark_pool(payload))
        raise ValueError(f"Unsupported dark-pool provider: {resolved}")

    def fetch_options(self, symbol: str, provider: str | None = None, expiration: str | None = None) -> dict:
        resolved = self._resolve_typed_provider(provider, self.settings.options_default_provider, self.settings.options_enabled_providers)
        cache_key = ("options", resolved, symbol, expiration or "")
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        if resolved == "yahoo_options":
            payload = self._options_yahoo(symbol, expiration)
            return self._cache_set(cache_key, self._attach_normalized_options(payload))
        if resolved == "finnhub":
            payload = self._options_finnhub(symbol, expiration)
            return self._cache_set(cache_key, self._attach_normalized_options(payload))
        if resolved == "local_file":
            payload = self._read_local_json("options_data", symbol, "{symbol}_options.json", "options_filename")
            return self._cache_set(cache_key, self._attach_normalized_options(payload))
        raise ValueError(f"Unsupported options provider: {resolved}")

    def _cache_get(self, key: tuple) -> dict | None:
        if not self.settings.performance_enabled:
            return None
        cached = self._response_cache.get(key)
        if cached is not None:
            self._cache_hits += 1
            return deepcopy(cached)
        self._cache_misses += 1
        return None

    def _cache_set(self, key: tuple, value: dict) -> dict:
        if self.settings.performance_enabled:
            self._response_cache[key] = deepcopy(value)
            self._trim_cache()
        return deepcopy(value)

    def _trim_cache(self) -> None:
        while len(self._response_cache) > self.settings.performance_market_data_cache_size:
            first_key = next(iter(self._response_cache))
            self._response_cache.pop(first_key, None)

    def cache_stats(self) -> dict[str, int | bool]:
        return {
            "enabled": self.settings.performance_enabled,
            "entries": len(self._response_cache),
            "max_entries": self.settings.performance_market_data_cache_size,
            "hits": self._cache_hits,
            "misses": self._cache_misses,
        }

    def _resolve_provider(self, provider: str | None) -> str:
        resolved = (provider or self.settings.market_data_default_provider).lower()
        if resolved not in self.settings.market_data_enabled_providers:
            raise ValueError(f"Provider not enabled: {resolved}")
        return resolved

    def _resolve_typed_provider(self, provider: str | None, default_provider: str, enabled_providers: list[str]) -> str:
        resolved = (provider or default_provider).lower()
        if resolved not in enabled_providers:
            raise ValueError(f"Provider not enabled: {resolved}")
        return resolved

    def _generic_provider_matrix(
        self,
        enabled_providers: list[str],
        provider_configs: dict[str, dict[str, str | bool]],
        special_local_file_key: str = "local_file",
    ) -> list[dict]:
        providers: list[dict] = []
        for name in enabled_providers:
            config = provider_configs.get(name, {})
            api_key_envs = self._provider_api_key_envs(config)
            api_key_present = any(os.getenv(env_name) for env_name in api_key_envs)
            enabled = bool(config.get("enabled", True))
            status = "ok"
            detail = "Provider is configured."
            if name == "akshare" and ak is None:
                status = "warning"
                detail = "akshare provider is enabled in config but akshare is not installed."
            elif name == special_local_file_key:
                detail = f"Local file provider rooted at {config.get('base_path', 'data/local_market_data')}."
            elif api_key_envs and not api_key_present:
                status = "warning"
                detail = f"{name} provider is enabled but none of [{', '.join(api_key_envs)}] are set."
            providers.append(
                {
                    "provider": name,
                    "enabled": enabled,
                    "status": status,
                    "api_key_envs": api_key_envs,
                    "api_key_present": api_key_present,
                    "detail": detail,
                    "base_url": str(config.get("base_url", "")),
                }
            )
        return providers

    def _provider_api_key_envs(self, config: dict[str, str | bool]) -> list[str]:
        raw = config.get("api_key_envs", [])
        if not isinstance(raw, list):
            return []
        return [str(item).strip() for item in raw if str(item).strip()]

    def _provider_api_key(self, config: dict[str, str | bool]) -> str | None:
        for env_name in self._provider_api_key_envs(config):
            value = os.getenv(env_name)
            if value:
                return value
        return None

    def _request_json(self, url: str) -> dict:
        request = Request(url, headers={"User-Agent": "Sentinel-Alpha/0.1"})
        with urlopen(request, timeout=self.settings.market_data_request_timeout_seconds) as response:
            payload = response.read().decode("utf-8")
        return json.loads(payload)

    def _request_json_with_headers(self, url: str, headers: dict[str, str], timeout_seconds: int) -> dict:
        request = Request(url, headers=headers)
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read().decode("utf-8")
        return json.loads(payload)

    def _quote_yahoo(self, symbol: str) -> dict:
        base = str(self.settings.market_data_provider_configs.get("yahoo", {}).get("base_url", "")).rstrip("/")
        url = f"{base}/v7/finance/quote?{urlencode({'symbols': symbol})}"
        payload = self._request_json(url)
        result = ((payload.get("quoteResponse") or {}).get("result") or [{}])[0]
        return {
            "provider": "yahoo",
            "symbol": symbol,
            "currency": result.get("currency"),
            "price": result.get("regularMarketPrice"),
            "open": result.get("regularMarketOpen"),
            "high": result.get("regularMarketDayHigh"),
            "low": result.get("regularMarketDayLow"),
            "previous_close": result.get("regularMarketPreviousClose"),
            "timestamp": result.get("regularMarketTime"),
            "raw": result,
        }

    def _history_yahoo(self, symbol: str, interval: str, lookback: str) -> dict:
        base = str(self.settings.market_data_provider_configs.get("yahoo", {}).get("base_url", "")).rstrip("/")
        url = f"{base}/v8/finance/chart/{symbol}?{urlencode({'interval': interval, 'range': lookback, 'includePrePost': 'false', 'events': 'div,splits'})}"
        payload = self._request_json(url)
        result = ((payload.get("chart") or {}).get("result") or [{}])[0]
        timestamps = result.get("timestamp") or []
        quote = (((result.get("indicators") or {}).get("quote") or [{}])[0]) or {}
        bars = []
        for index, ts in enumerate(timestamps):
            bars.append(
                {
                    "timestamp": ts,
                    "open": (quote.get("open") or [None])[index],
                    "high": (quote.get("high") or [None])[index],
                    "low": (quote.get("low") or [None])[index],
                    "close": (quote.get("close") or [None])[index],
                    "volume": (quote.get("volume") or [None])[index],
                }
            )
        return {"provider": "yahoo", "symbol": symbol, "interval": interval, "lookback": lookback, "bars": bars}

    def _quote_alphavantage(self, symbol: str) -> dict:
        config = self.settings.market_data_provider_configs.get("alphavantage", {})
        api_key = self._provider_api_key(config)
        if not api_key:
            raise ValueError("Alpha Vantage API key is not configured.")
        base = str(config.get("base_url", "")).rstrip("/")
        url = f"{base}/query?{urlencode({'function': 'GLOBAL_QUOTE', 'symbol': symbol, 'apikey': api_key})}"
        payload = self._request_json(url)
        result = payload.get("Global Quote") or {}
        return {
            "provider": "alphavantage",
            "symbol": symbol,
            "price": result.get("05. price"),
            "open": result.get("02. open"),
            "high": result.get("03. high"),
            "low": result.get("04. low"),
            "previous_close": result.get("08. previous close"),
            "timestamp": result.get("07. latest trading day"),
            "raw": result,
        }

    def _history_alphavantage(self, symbol: str, interval: str) -> dict:
        config = self.settings.market_data_provider_configs.get("alphavantage", {})
        api_key = self._provider_api_key(config)
        if not api_key:
            raise ValueError("Alpha Vantage API key is not configured.")
        base = str(config.get("base_url", "")).rstrip("/")
        if interval.endswith("min"):
            function = "TIME_SERIES_INTRADAY"
            params = {"function": function, "symbol": symbol, "interval": interval, "outputsize": "compact", "apikey": api_key}
            series_key = f"Time Series ({interval})"
        else:
            function = "TIME_SERIES_DAILY"
            params = {"function": function, "symbol": symbol, "outputsize": "compact", "apikey": api_key}
            series_key = "Time Series (Daily)"
        url = f"{base}/query?{urlencode(params)}"
        payload = self._request_json(url)
        series = payload.get(series_key) or {}
        bars = [
            {
                "timestamp": ts,
                "open": values.get("1. open"),
                "high": values.get("2. high"),
                "low": values.get("3. low"),
                "close": values.get("4. close"),
                "volume": values.get("5. volume"),
            }
            for ts, values in sorted(series.items())
        ]
        return {"provider": "alphavantage", "symbol": symbol, "interval": interval, "bars": bars}

    def _quote_finnhub(self, symbol: str) -> dict:
        config = self.settings.market_data_provider_configs.get("finnhub", {})
        api_key = self._provider_api_key(config)
        if not api_key:
            raise ValueError("Finnhub API key is not configured.")
        base = str(config.get("base_url", "")).rstrip("/")
        url = f"{base}/quote?{urlencode({'symbol': symbol, 'token': api_key})}"
        payload = self._request_json(url)
        return {
            "provider": "finnhub",
            "symbol": symbol,
            "price": payload.get("c"),
            "open": payload.get("o"),
            "high": payload.get("h"),
            "low": payload.get("l"),
            "previous_close": payload.get("pc"),
            "timestamp": payload.get("t"),
            "raw": payload,
        }

    def _history_finnhub(self, symbol: str, interval: str, lookback: str) -> dict:
        config = self.settings.market_data_provider_configs.get("finnhub", {})
        api_key = self._provider_api_key(config)
        if not api_key:
            raise ValueError("Finnhub API key is not configured.")
        resolution_map = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "1d": "D", "1w": "W"}
        resolution = resolution_map.get(interval, "D")
        now = datetime.now(timezone.utc)
        span_days = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "5d": 5}.get(lookback, 180)
        start = int((now - timedelta(days=span_days)).timestamp())
        end = int(now.timestamp())
        base = str(config.get("base_url", "")).rstrip("/")
        url = f"{base}/stock/candle?{urlencode({'symbol': symbol, 'resolution': resolution, 'from': start, 'to': end, 'token': api_key})}"
        payload = self._request_json(url)
        bars = []
        timestamps = payload.get("t") or []
        opens = payload.get("o") or []
        highs = payload.get("h") or []
        lows = payload.get("l") or []
        closes = payload.get("c") or []
        volumes = payload.get("v") or []
        for index, ts in enumerate(timestamps):
            bars.append(
                {
                    "timestamp": ts,
                    "open": opens[index],
                    "high": highs[index],
                    "low": lows[index],
                    "close": closes[index],
                    "volume": volumes[index],
                }
            )
        return {"provider": "finnhub", "symbol": symbol, "interval": interval, "lookback": lookback, "bars": bars}

    def _quote_akshare(self, symbol: str) -> dict:
        if ak is None:
            raise ValueError("akshare is not installed.")
        snapshot = ak.stock_zh_a_spot_em()
        match = snapshot[snapshot["代码"] == symbol]
        if match.empty:
            raise ValueError(f"No AkShare quote found for symbol: {symbol}")
        row = match.iloc[0]
        return {
            "provider": "akshare",
            "symbol": symbol,
            "price": row.get("最新价"),
            "open": row.get("今开"),
            "high": row.get("最高"),
            "low": row.get("最低"),
            "previous_close": row.get("昨收"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "raw": row.to_dict(),
        }

    def _history_akshare(self, symbol: str) -> dict:
        if ak is None:
            raise ValueError("akshare is not installed.")
        frame = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="")
        bars = [
            {
                "timestamp": str(row["日期"]),
                "open": row.get("开盘"),
                "high": row.get("最高"),
                "low": row.get("最低"),
                "close": row.get("收盘"),
                "volume": row.get("成交量"),
            }
            for _, row in frame.iterrows()
        ]
        return {"provider": "akshare", "symbol": symbol, "interval": "1d", "bars": bars}

    def _quote_local_file(self, symbol: str) -> dict:
        config = self.settings.market_data_provider_configs.get("local_file", {})
        quote_path = self._local_file_path(
            str(config.get("base_path", "data/local_market_data")),
            str(config.get("quote_filename", "{symbol}_quote.json")).format(symbol=symbol),
        )
        if not quote_path.exists():
            raise ValueError(f"Local quote file not found: {quote_path}")
        if quote_path.suffix.lower() == ".json":
            payload = json.loads(quote_path.read_text(encoding="utf-8"))
            payload.setdefault("provider", "local_file")
            payload.setdefault("symbol", symbol)
            return payload
        if quote_path.suffix.lower() == ".csv":
            with quote_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            if not rows:
                raise ValueError(f"Local quote CSV is empty: {quote_path}")
            row = rows[-1]
            return {
                "provider": "local_file",
                "symbol": symbol,
                "price": row.get("price") or row.get("close"),
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "previous_close": row.get("previous_close"),
                "timestamp": row.get("timestamp"),
                "raw": row,
            }
        raise ValueError(f"Unsupported local quote file format: {quote_path.suffix}")

    def _history_local_file(self, symbol: str, interval: str) -> dict:
        config = self.settings.market_data_provider_configs.get("local_file", {})
        history_path = self._local_file_path(
            str(config.get("base_path", "data/local_market_data")),
            str(config.get("history_filename", "{symbol}_{interval}.csv")).format(symbol=symbol, interval=interval),
        )
        if not history_path.exists():
            raise ValueError(f"Local history file not found: {history_path}")
        if history_path.suffix.lower() == ".json":
            payload = json.loads(history_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                bars = payload.get("bars", [])
            else:
                bars = payload
            return {"provider": "local_file", "symbol": symbol, "interval": interval, "bars": bars}
        if history_path.suffix.lower() == ".csv":
            with history_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            bars = [
                {
                    "timestamp": row.get("timestamp"),
                    "open": row.get("open"),
                    "high": row.get("high"),
                    "low": row.get("low"),
                    "close": row.get("close"),
                    "volume": row.get("volume"),
                }
                for row in rows
            ]
            return {"provider": "local_file", "symbol": symbol, "interval": interval, "bars": bars}
        raise ValueError(f"Unsupported local history file format: {history_path.suffix}")

    def _local_file_path(self, base_path: str, filename: str) -> Path:
        root = Path(base_path)
        if not root.is_absolute():
            root = Path(self.settings.config_path).resolve().parents[1] / root
        return root / filename

    def _read_local_json(self, config_group: str, symbol: str, default_name: str, config_key: str) -> dict:
        if config_group == "fundamentals":
            config = self.settings.fundamentals_provider_configs.get("local_file", {})
        elif config_group == "dark_pool":
            config = self.settings.dark_pool_provider_configs.get("local_file", {})
        else:
            config = self.settings.options_provider_configs.get("local_file", {})
        path = self._local_file_path(
            str(config.get("base_path", "data/local_market_data")),
            str(config.get(config_key, default_name)).format(symbol=symbol),
        )
        if not path.exists():
            raise ValueError(f"Local file not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload.setdefault("provider", "local_file")
            payload.setdefault("symbol", symbol)
            return payload
        return {"provider": "local_file", "symbol": symbol, "items": payload}

    def _financials_sec(self, symbol: str) -> dict:
        config = self.settings.fundamentals_provider_configs.get("sec", {})
        headers = {"User-Agent": str(config.get("user_agent", "Sentinel-Alpha/0.1 support@sentinel-alpha.local"))}
        ticker_map = self._request_json_with_headers(
            str(config.get("company_tickers_url", "")),
            headers,
            self.settings.fundamentals_request_timeout_seconds,
        )
        cik = None
        for item in ticker_map.values():
            if str(item.get("ticker", "")).upper() == symbol.upper():
                cik = str(item.get("cik_str", "")).zfill(10)
                break
        if not cik:
            raise ValueError(f"SEC CIK not found for symbol: {symbol}")
        submissions = self._request_json_with_headers(
            f"{str(config.get('submissions_base_url', '')).rstrip('/')}/CIK{cik}.json",
            headers,
            self.settings.fundamentals_request_timeout_seconds,
        )
        companyfacts = self._request_json_with_headers(
            f"{str(config.get('companyfacts_base_url', '')).rstrip('/')}/CIK{cik}.json",
            headers,
            self.settings.fundamentals_request_timeout_seconds,
        )
        return {
            "provider": "sec",
            "symbol": symbol,
            "cik": cik,
            "entity_name": submissions.get("name"),
            "sic": submissions.get("sic"),
            "tickers": submissions.get("tickers"),
            "recent_filings": ((submissions.get("filings") or {}).get("recent") or {}),
            "companyfacts": companyfacts,
        }

    def _financials_alphavantage(self, symbol: str) -> dict:
        config = self.settings.fundamentals_provider_configs.get("alphavantage", {})
        api_key = self._provider_api_key(config)
        if not api_key:
            raise ValueError("Alpha Vantage API key is not configured.")
        base = str(config.get("base_url", "")).rstrip("/")
        overview = self._request_json(f"{base}/query?{urlencode({'function': 'OVERVIEW', 'symbol': symbol, 'apikey': api_key})}")
        income = self._request_json(f"{base}/query?{urlencode({'function': 'INCOME_STATEMENT', 'symbol': symbol, 'apikey': api_key})}")
        balance = self._request_json(f"{base}/query?{urlencode({'function': 'BALANCE_SHEET', 'symbol': symbol, 'apikey': api_key})}")
        cashflow = self._request_json(f"{base}/query?{urlencode({'function': 'CASH_FLOW', 'symbol': symbol, 'apikey': api_key})}")
        return {"provider": "alphavantage", "symbol": symbol, "overview": overview, "income_statement": income, "balance_sheet": balance, "cash_flow": cashflow}

    def _financials_finnhub(self, symbol: str) -> dict:
        config = self.settings.fundamentals_provider_configs.get("finnhub", {})
        api_key = self._provider_api_key(config)
        if not api_key:
            raise ValueError("Finnhub API key is not configured.")
        base = str(config.get("base_url", "")).rstrip("/")
        basic = self._request_json(f"{base}/stock/metric?{urlencode({'symbol': symbol, 'metric': 'all', 'token': api_key})}")
        profile = self._request_json(f"{base}/stock/profile2?{urlencode({'symbol': symbol, 'token': api_key})}")
        return {"provider": "finnhub", "symbol": symbol, "basic_financials": basic, "profile": profile}

    def _dark_pool_finra(self, symbol: str) -> dict:
        config = self.settings.dark_pool_provider_configs.get("finra", {})
        base = str(config.get("base_url", "")).rstrip("/")
        dataset = str(config.get("dataset", "otcmarket/weeklySummary")).strip("/")
        query = urlencode({"limit": 50, "compareFilters": f"issueSymbol:EQUAL:{symbol.upper()}"})
        url = f"{base}/data/group/{dataset}?{query}"
        payload = self._request_json_with_headers(
            url,
            {"User-Agent": "Sentinel-Alpha/0.1"},
            self.settings.dark_pool_request_timeout_seconds,
        )
        return {"provider": "finra", "symbol": symbol, "dataset": dataset, "items": payload}

    def _options_yahoo(self, symbol: str, expiration: str | None) -> dict:
        config = self.settings.options_provider_configs.get("yahoo_options", {})
        base = str(config.get("base_url", "")).rstrip("/")
        params = {"formatted": "false"}
        if expiration:
            params["date"] = expiration
        url = f"{base}/v7/finance/options/{symbol}?{urlencode(params)}"
        payload = self._request_json(url)
        result = ((payload.get("optionChain") or {}).get("result") or [{}])[0]
        return {
            "provider": "yahoo_options",
            "symbol": symbol,
            "expiration_dates": result.get("expirationDates", []),
            "underlying_quote": result.get("quote", {}),
            "options": result.get("options", []),
        }

    def _options_finnhub(self, symbol: str, expiration: str | None) -> dict:
        config = self.settings.options_provider_configs.get("finnhub", {})
        api_key = self._provider_api_key(config)
        if not api_key:
            raise ValueError("Finnhub API key is not configured.")
        base = str(config.get("base_url", "")).rstrip("/")
        params = {"symbol": symbol, "token": api_key}
        if expiration:
            params["expiration"] = expiration
        url = f"{base}/stock/option-chain?{urlencode(params)}"
        payload = self._request_json(url)
        return {"provider": "finnhub", "symbol": symbol, "option_chain": payload}

    def _attach_normalized_financials(self, payload: dict) -> dict:
        return {
            **payload,
            "normalized": asdict(self._normalize_financials(payload)),
        }

    def _attach_normalized_dark_pool(self, payload: dict) -> dict:
        return {
            **payload,
            "normalized": asdict(self._normalize_dark_pool(payload)),
        }

    def _attach_normalized_options(self, payload: dict) -> dict:
        return {
            **payload,
            "normalized": asdict(self._normalize_options(payload)),
        }

    def _normalize_financials(self, payload: dict) -> FinancialsSnapshot:
        provider = str(payload.get("provider", "unknown"))
        symbol = str(payload.get("symbol", "unknown"))
        records: list[FinancialStatementRecord] = []

        if provider == "sec":
            records.extend(self._extract_sec_financial_records(payload))
        elif provider == "alphavantage":
            records.extend(self._extract_alphavantage_financial_records(payload))
        elif provider == "finnhub":
            records.extend(self._extract_finnhub_financial_records(payload))
        elif provider == "local_file":
            records.extend(self._extract_local_financial_records(payload))

        deduped = self._dedupe_weighted_records(
            records,
            lambda item: f"{item.statement_type}:{item.period_end}",
            provider,
        )
        report_period = deduped[0].period_end if deduped else payload.get("report_period")
        entity_name = payload.get("entity_name") or payload.get("company_name") or payload.get("name")
        return FinancialsSnapshot(
            provider=provider,
            symbol=symbol,
            entity_name=entity_name,
            report_period=report_period,
            statements=deduped,
            dedupe_summary={"input_count": len(records), "output_count": len(deduped)},
            overall_weight=round(sum(item.weighted.final_weight for item in deduped if item.weighted) / max(1, len(deduped)), 4),
        )

    def _normalize_dark_pool(self, payload: dict) -> DarkPoolSnapshot:
        provider = str(payload.get("provider", "unknown"))
        symbol = str(payload.get("symbol", "unknown"))
        raw_items = payload.get("items") or payload.get("data") or payload.get("records") or []
        records = [
            DarkPoolRecord(
                trade_date=str(item.get("tradeDate") or item.get("weekStartDate") or item.get("date") or "unknown"),
                venue=str(item.get("venue") or item.get("market") or item.get("atsName") or provider),
                shares=self._to_float(item.get("totalWeeklyShareQuantity") or item.get("shares") or item.get("volume")),
                notional=self._to_float(item.get("notional") or item.get("dollarValue")),
                trade_count=self._to_int(item.get("tradeCount") or item.get("trades")),
            )
            for item in raw_items
            if isinstance(item, dict)
        ]
        deduped = self._dedupe_weighted_records(
            records,
            lambda item: f"{item.trade_date}:{item.venue}:{item.shares or 0}",
            provider,
        )
        return DarkPoolSnapshot(
            provider=provider,
            symbol=symbol,
            records=deduped,
            dedupe_summary={"input_count": len(records), "output_count": len(deduped)},
            overall_weight=round(sum(item.weighted.final_weight for item in deduped if item.weighted) / max(1, len(deduped)), 4),
        )

    def _normalize_options(self, payload: dict) -> OptionsSnapshot:
        provider = str(payload.get("provider", "unknown"))
        symbol = str(payload.get("symbol", "unknown"))
        raw_contracts = self._extract_option_contracts(payload)
        contracts = [
            OptionContractRecord(
                contract_symbol=str(item.get("contractSymbol") or item.get("symbol") or item.get("contract") or f"{symbol}-unknown"),
                expiration=str(item.get("expiration") or item.get("expirationDate") or payload.get("expiration") or "unknown"),
                strike=self._to_float(item.get("strike")),
                option_type=str(item.get("optionType") or item.get("type") or self._infer_option_type(item)),
                bid=self._to_float(item.get("bid")),
                ask=self._to_float(item.get("ask")),
                last=self._to_float(item.get("lastPrice") or item.get("last")),
                volume=self._to_float(item.get("volume")),
                open_interest=self._to_float(item.get("openInterest") or item.get("oi")),
                implied_volatility=self._to_float(item.get("impliedVolatility") or item.get("iv")),
            )
            for item in raw_contracts
            if isinstance(item, dict)
        ]
        deduped = self._dedupe_weighted_records(
            contracts,
            lambda item: f"{item.expiration}:{item.option_type}:{item.strike}",
            provider,
        )
        expiration_dates = payload.get("expiration_dates") or payload.get("expirationDates") or sorted({item.expiration for item in deduped if item.expiration != "unknown"})
        return OptionsSnapshot(
            provider=provider,
            symbol=symbol,
            expiration_dates=[str(item) for item in expiration_dates],
            contracts=deduped,
            dedupe_summary={"input_count": len(contracts), "output_count": len(deduped)},
            overall_weight=round(sum(item.weighted.final_weight for item in deduped if item.weighted) / max(1, len(deduped)), 4),
        )

    def _extract_sec_financial_records(self, payload: dict) -> list[FinancialStatementRecord]:
        facts = ((payload.get("companyfacts") or {}).get("facts") or {}).get("us-gaap") or {}
        records: list[FinancialStatementRecord] = []
        revenue_items = (((facts.get("Revenues") or {}).get("units") or {}).get("USD") or [])[:8]
        income_items = (((facts.get("NetIncomeLoss") or {}).get("units") or {}).get("USD") or [])[:8]
        asset_items = (((facts.get("Assets") or {}).get("units") or {}).get("USD") or [])[:8]
        liability_items = (((facts.get("Liabilities") or {}).get("units") or {}).get("USD") or [])[:8]
        for entry in revenue_items:
            period_end = str(entry.get("end") or "unknown")
            records.append(
                FinancialStatementRecord(
                    statement_type="income_statement",
                    period_end=period_end,
                    revenue=self._to_float(entry.get("val")),
                    net_income=self._match_numeric_by_period(income_items, period_end),
                    total_assets=self._match_numeric_by_period(asset_items, period_end),
                    total_liabilities=self._match_numeric_by_period(liability_items, period_end),
                )
            )
        return records

    def _extract_alphavantage_financial_records(self, payload: dict) -> list[FinancialStatementRecord]:
        records: list[FinancialStatementRecord] = []
        income_reports = (payload.get("income_statement") or {}).get("annualReports") or []
        balance_reports = (payload.get("balance_sheet") or {}).get("annualReports") or []
        cash_reports = (payload.get("cash_flow") or {}).get("annualReports") or []
        for entry in income_reports[:8]:
            period_end = str(entry.get("fiscalDateEnding") or "unknown")
            records.append(
                FinancialStatementRecord(
                    statement_type="income_statement",
                    period_end=period_end,
                    revenue=self._to_float(entry.get("totalRevenue")),
                    net_income=self._to_float(entry.get("netIncome")),
                    eps=self._to_float(entry.get("reportedEPS")),
                    total_assets=self._match_numeric_by_period(balance_reports, period_end, "totalAssets"),
                    total_liabilities=self._match_numeric_by_period(balance_reports, period_end, "totalLiabilities"),
                    operating_cash_flow=self._match_numeric_by_period(cash_reports, period_end, "operatingCashflow"),
                    free_cash_flow=self._match_numeric_by_period(cash_reports, period_end, "operatingCashflow"),
                )
            )
        return records

    def _extract_finnhub_financial_records(self, payload: dict) -> list[FinancialStatementRecord]:
        metric = (payload.get("basic_financials") or {}).get("metric") or {}
        profile = payload.get("profile") or {}
        return [
            FinancialStatementRecord(
                statement_type="overview",
                period_end=str(profile.get("ipo") or "unknown"),
                revenue=self._to_float(metric.get("salesPerShareAnnual")),
                net_income=self._to_float(metric.get("netMarginAnnual")),
                eps=self._to_float(metric.get("epsAnnual")),
                total_assets=self._to_float(metric.get("totalDebt/totalEquityAnnual")),
            )
        ]

    def _extract_local_financial_records(self, payload: dict) -> list[FinancialStatementRecord]:
        rows = payload.get("statements") or payload.get("items") or []
        return [
            FinancialStatementRecord(
                statement_type=str(item.get("statement_type") or item.get("type") or "unknown"),
                period_end=str(item.get("period_end") or item.get("date") or "unknown"),
                revenue=self._to_float(item.get("revenue")),
                net_income=self._to_float(item.get("net_income")),
                eps=self._to_float(item.get("eps")),
                total_assets=self._to_float(item.get("total_assets")),
                total_liabilities=self._to_float(item.get("total_liabilities")),
                operating_cash_flow=self._to_float(item.get("operating_cash_flow")),
                free_cash_flow=self._to_float(item.get("free_cash_flow")),
            )
            for item in rows
            if isinstance(item, dict)
        ]

    def _extract_option_contracts(self, payload: dict) -> list[dict]:
        if payload.get("options"):
            raw = []
            for chain in payload.get("options") or []:
                raw.extend(chain.get("calls") or [])
                raw.extend(chain.get("puts") or [])
            return raw
        option_chain = payload.get("option_chain") or {}
        if isinstance(option_chain, dict):
            data = option_chain.get("data") or option_chain.get("options") or option_chain.get("chain") or []
            if isinstance(data, list):
                return data
        return payload.get("contracts") or []

    def _infer_option_type(self, item: dict) -> str:
        contract_symbol = str(item.get("contractSymbol") or item.get("symbol") or "")
        if contract_symbol.endswith("C"):
            return "call"
        if contract_symbol.endswith("P"):
            return "put"
        return "unknown"

    def _dedupe_weighted_records(self, records: list, key_builder, provider: str) -> list:
        deduped: dict[str, object] = {}
        provider_weight = self._provider_weight(provider)
        for record in records:
            dedupe_key = key_builder(record)
            completeness_weight = self._record_completeness(record)
            recency_weight = self._record_recency(record)
            final_weight = round(provider_weight * completeness_weight * recency_weight, 4)
            weighted = WeightedRecord(
                dedupe_key=dedupe_key,
                provider_weight=provider_weight,
                recency_weight=recency_weight,
                completeness_weight=completeness_weight,
                final_weight=final_weight,
            )
            setattr(record, "weighted", weighted)
            existing = deduped.get(dedupe_key)
            if existing is None or final_weight > existing.weighted.final_weight:  # type: ignore[attr-defined]
                deduped[dedupe_key] = record
        return list(deduped.values())

    def _provider_weight(self, provider: str) -> float:
        weights = {
            "sec": 1.0,
            "finra": 1.0,
            "yahoo_options": 0.85,
            "yahoo": 0.85,
            "alphavantage": 0.82,
            "finnhub": 0.82,
            "akshare": 0.78,
            "local_file": 0.7,
        }
        return weights.get(provider, 0.65)

    def _record_completeness(self, record: object) -> float:
        if is_dataclass(record):
            values = [getattr(record, item.name) for item in fields(record) if item.name != "weighted"]
        else:
            values = [value for key, value in vars(record).items() if key != "weighted"]
        filled = sum(1 for value in values if value not in {None, "", "unknown", 0})
        return round(max(0.3, filled / max(1, len(values))), 4)

    def _record_recency(self, record: object) -> float:
        date_value = None
        for attr in ("period_end", "trade_date", "expiration"):
            if hasattr(record, attr):
                date_value = getattr(record, attr)
                break
        if not date_value or date_value == "unknown":
            return 0.6
        try:
            parsed = datetime.fromisoformat(str(date_value).replace("Z", "+00:00"))
            age_days = max(0, (datetime.now(timezone.utc) - parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).days)
            if age_days <= 30:
                return 1.0
            if age_days <= 180:
                return 0.85
            if age_days <= 365:
                return 0.7
            return 0.55
        except ValueError:
            return 0.6

    def _match_numeric_by_period(self, items: list[dict], period_end: str, field: str = "val") -> float | None:
        for item in items:
            item_period = str(item.get("end") or item.get("fiscalDateEnding") or "unknown")
            if item_period == period_end:
                return self._to_float(item.get(field))
        return None

    def _to_float(self, value) -> float | None:
        if value in (None, "", "None", "null"):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _to_int(self, value) -> int | None:
        if value in (None, "", "None", "null"):
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None
