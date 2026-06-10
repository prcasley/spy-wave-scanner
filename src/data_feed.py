"""Yahoo Finance data feed — OHLCV bars + indicator computation.

Replaces the original Polygon implementation. Keeps the public ``DataFeed``
class name and ``get_bars`` / ``compute_indicators`` signatures so the rest of
the pipeline is unaffected.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import requests

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_DIR = Path.home() / ".cache" / "spy-wave-scanner"
_YAHOO_CHART_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
_YAHOO_FALLBACK_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class DataFeedError(RuntimeError):
    """Raised when Yahoo refuses to return usable bars. Fail loud, no mocks."""


class DataFeed:
    """Fetch OHLCV bars from Yahoo Finance and compute indicators.

    Parameters
    ----------
    ticker : str
        Default symbol. Per-call ``get_bars(ticker=...)`` overrides it.
    cache_dir : str, optional
        Override the parquet cache location. Defaults to
        ``~/.cache/spy-wave-scanner``.
    rate_limit_rpm : int
        Requests per minute throttle. Yahoo doesn't publish a hard limit but
        bursts get 429'd.
    api_key : str, optional
        Ignored. Accepted only for backwards compatibility with old callers.
    """

    # Yahoo `interval` values per the v8 chart API
    _TF_MAP = {
        "1min": ("1m", 7),
        "5min": ("5m", 60),
        "15min": ("15m", 60),
        "30min": ("30m", 60),
        "1h": ("60m", 730),
        "1day": ("1d", 365 * 10),
    }

    def __init__(
        self,
        ticker: str = "SPY",
        cache_dir: Optional[str] = None,
        rate_limit_rpm: int = 60,
        api_key: Optional[str] = None,  # ignored; kept for back-compat
    ) -> None:
        self.ticker = ticker.upper()
        self.cache_dir = Path(cache_dir) if cache_dir else _DEFAULT_CACHE_DIR
        self._min_interval = 60.0 / max(rate_limit_rpm, 1)
        self._last_call: float = 0.0
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": _USER_AGENT,
                "Accept": "application/json,text/plain,*/*",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        if api_key is not None:
            logger.debug("DataFeed: api_key argument ignored (Yahoo requires no key)")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.time()

    def _cache_key(self, ticker: str, timeframe: str, lookback_days: int, end: datetime) -> Path:
        return (
            self.cache_dir
            / f"{ticker}_{timeframe}_{lookback_days}d_{end.strftime('%Y%m%d_%H%M')}.parquet"
        )

    def _fetch_chart(self, ticker: str, interval: str, lookback_days: int) -> dict:
        """One-shot Yahoo v8 chart fetch with one fallback host. Fail loud."""
        params = {
            "interval": interval,
            "range": f"{lookback_days}d",
            "includePrePost": "false",
            "events": "div,splits",
        }
        last_err: Optional[Exception] = None
        for url_tmpl in (_YAHOO_CHART_URL, _YAHOO_FALLBACK_URL):
            url = url_tmpl.format(symbol=ticker)
            try:
                self._throttle()
                resp = self._session.get(url, params=params, timeout=15)
                if resp.status_code == 200:
                    payload = resp.json()
                    err = (payload.get("chart") or {}).get("error")
                    if err:
                        raise DataFeedError(f"Yahoo error for {ticker}: {err}")
                    return payload
                last_err = DataFeedError(
                    f"Yahoo HTTP {resp.status_code} for {ticker} ({url}): {resp.text[:200]}"
                )
            except (requests.RequestException, ValueError) as exc:
                last_err = exc
        raise DataFeedError(
            f"Yahoo fetch failed for {ticker} after both hosts: {last_err}"
        )

    @staticmethod
    def _payload_to_frame(payload: dict) -> pd.DataFrame:
        chart = payload.get("chart") or {}
        results = chart.get("result") or []
        if not results:
            return pd.DataFrame()
        result = results[0]
        timestamps = result.get("timestamp") or []
        indicators = (result.get("indicators") or {}).get("quote") or [{}]
        quote = indicators[0]
        if not timestamps or not quote:
            return pd.DataFrame()

        df = pd.DataFrame(
            {
                "open": quote.get("open") or [],
                "high": quote.get("high") or [],
                "low": quote.get("low") or [],
                "close": quote.get("close") or [],
                "volume": quote.get("volume") or [],
            }
        )
        df["timestamp"] = pd.to_datetime(timestamps, unit="s", utc=True)
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)
        df = df.dropna(subset=["open", "high", "low", "close"])
        df["vwap"] = np.nan  # Yahoo doesn't return vwap on chart endpoint
        return df

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_bars(
        self,
        timeframe: str = "5min",
        lookback_days: int = 5,
        end_date: Optional[datetime] = None,
        use_cache: bool = True,
        ticker: Optional[str] = None,
    ) -> pd.DataFrame:
        """Fetch OHLCV from Yahoo. Indicators are added separately.

        Returns columns: open, high, low, close, volume, vwap.
        Indexed by a UTC ``DatetimeIndex``.
        """
        sym = (ticker or self.ticker).upper()
        if timeframe not in self._TF_MAP:
            raise ValueError(
                f"Unsupported timeframe '{timeframe}'. "
                f"Choose from {list(self._TF_MAP)}"
            )
        interval, max_lookback = self._TF_MAP[timeframe]
        lookback_days = min(lookback_days, max_lookback)
        end = end_date or datetime.utcnow()

        if use_cache:
            cache_file = self._cache_key(sym, timeframe, lookback_days, end)
            if cache_file.exists():
                logger.info("Loading cached bars: %s", cache_file)
                return pd.read_parquet(cache_file)

        payload = self._fetch_chart(sym, interval, lookback_days)
        df = self._payload_to_frame(payload)

        if df.empty:
            raise DataFeedError(
                f"Yahoo returned no bars for {sym} {timeframe} ({lookback_days}d)"
            )

        logger.info(
            "Fetched %d bars for %s (%s, %dd lookback)",
            len(df), sym, timeframe, lookback_days,
        )

        if use_cache:
            cache_file = self._cache_key(sym, timeframe, lookback_days, end)
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(cache_file)

        return df

    def get_realtime_quote(self, ticker: Optional[str] = None) -> dict:
        """Use the last 1-minute bar as a real-time-ish quote. Fail loud on miss."""
        sym = (ticker or self.ticker).upper()
        df = self.get_bars(timeframe="1min", lookback_days=1, use_cache=False, ticker=sym)
        last = df.iloc[-1]
        return {
            "ticker": sym,
            "last": float(last["close"]),
            "bid": None,
            "ask": None,
            "timestamp": df.index[-1].to_pydatetime(),
        }

    def compute_indicators(
        self,
        df: pd.DataFrame,
        rsi_periods: Optional[list[int]] = None,
        macd_fast: int = 5,
        macd_slow: int = 13,
        macd_signal: int = 8,
        volume_sma_period: int = 20,
    ) -> pd.DataFrame:
        """Add RSI, MACD, and Volume SMA columns to an OHLCV DataFrame."""
        if df.empty:
            return df
        rsi_periods = rsi_periods or [7, 14]
        df = df.copy()
        for period in rsi_periods:
            df[f"rsi_{period}"] = self._compute_rsi(df["close"], period)
        ema_fast = df["close"].ewm(span=macd_fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=macd_slow, adjust=False).mean()
        df["macd"] = ema_fast - ema_slow
        df["macd_signal"] = df["macd"].ewm(span=macd_signal, adjust=False).mean()
        df["macd_histogram"] = df["macd"] - df["macd_signal"]
        df["volume_sma"] = df["volume"].rolling(window=volume_sma_period).mean()
        return df

    @staticmethod
    def _compute_rsi(series: pd.Series, period: int) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
