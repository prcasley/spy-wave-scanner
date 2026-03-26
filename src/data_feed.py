"""Module 1: Data Feed — fetch and normalise OHLCV data from Polygon.io."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from polygon import RESTClient

logger = logging.getLogger(__name__)

# Default cache directory
_DEFAULT_CACHE_DIR = Path.home() / ".cache" / "spy-wave-scanner"


class DataFeed:
    """Fetch OHLCV bars from Polygon.io and compute technical indicators."""

    # Map user-friendly timeframe strings to Polygon multiplier/timespan pairs
    _TF_MAP = {
        "1min": (1, "minute"),
        "5min": (5, "minute"),
        "15min": (15, "minute"),
        "1h": (1, "hour"),
        "1day": (1, "day"),
    }

    def __init__(
        self,
        api_key: str,
        ticker: str = "SPY",
        cache_dir: Optional[str] = None,
        rate_limit_rpm: int = 5,
    ):
        self.client = RESTClient(api_key)
        self.ticker = ticker
        self.cache_dir = Path(cache_dir) if cache_dir else _DEFAULT_CACHE_DIR
        self._min_interval = 60.0 / max(rate_limit_rpm, 1)
        self._last_call: float = 0.0

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _throttle(self) -> None:
        """Sleep if needed to respect Polygon API rate limits."""
        elapsed = time.time() - self._last_call
        if elapsed < self._min_interval:
            wait = self._min_interval - elapsed
            logger.debug("Rate limit: sleeping %.1fs", wait)
            time.sleep(wait)
        self._last_call = time.time()

    # ------------------------------------------------------------------
    # Caching
    # ------------------------------------------------------------------

    def _cache_key(self, timeframe: str, lookback_days: int, end_date: datetime) -> Path:
        """Build a cache file path for this query."""
        date_str = end_date.strftime("%Y%m%d")
        return self.cache_dir / f"{self.ticker}_{timeframe}_{lookback_days}d_{date_str}.parquet"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_bars(
        self,
        timeframe: str = "5min",
        lookback_days: int = 5,
        end_date: Optional[datetime] = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Fetch OHLCV bars from Polygon.io.

        Parameters
        ----------
        timeframe : str
            One of ``1min``, ``5min``, ``15min``, ``1h``, ``1day``.
        lookback_days : int
            Number of calendar days to look back.
        end_date : datetime, optional
            End of the query window.  Defaults to now.
        use_cache : bool
            If True, check for cached data before hitting the API.

        Returns
        -------
        pd.DataFrame
            Columns: open, high, low, close, volume, vwap, timestamp
            Indexed by a ``DatetimeIndex``.
        """
        if timeframe not in self._TF_MAP:
            raise ValueError(
                f"Unsupported timeframe '{timeframe}'. "
                f"Choose from {list(self._TF_MAP)}"
            )

        end = end_date or datetime.now()

        # Check cache first
        if use_cache:
            cache_file = self._cache_key(timeframe, lookback_days, end)
            if cache_file.exists():
                logger.info("Loading cached data from %s", cache_file)
                return pd.read_parquet(cache_file)

        multiplier, timespan = self._TF_MAP[timeframe]
        start = end - timedelta(days=lookback_days)

        self._throttle()

        aggs = self.client.get_aggs(
            ticker=self.ticker,
            multiplier=multiplier,
            timespan=timespan,
            from_=start.strftime("%Y-%m-%d"),
            to=end.strftime("%Y-%m-%d"),
            limit=50_000,
        )

        if not aggs:
            logger.warning("No bars returned for %s %s", self.ticker, timeframe)
            return pd.DataFrame()

        rows = []
        for bar in aggs:
            rows.append(
                {
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                    "vwap": getattr(bar, "vwap", np.nan),
                    "timestamp": pd.Timestamp(bar.timestamp, unit="ms", tz="UTC"),
                }
            )

        df = pd.DataFrame(rows)
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)
        logger.info(
            "Fetched %d bars for %s (%s, %d-day lookback)",
            len(df), self.ticker, timeframe, lookback_days,
        )

        # Save to cache
        if use_cache:
            cache_file = self._cache_key(timeframe, lookback_days, end)
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(cache_file)
            logger.info("Cached data to %s", cache_file)

        return df

    def get_realtime_quote(self) -> dict:
        """Return current bid / ask / last for proximity alert checks."""
        self._throttle()
        snapshot = self.client.get_snapshot_ticker(
            "stocks", self.ticker
        )
        return {
            "ticker": self.ticker,
            "last": snapshot.last_trade.price if snapshot.last_trade else None,
            "bid": snapshot.last_quote.bid if snapshot.last_quote else None,
            "ask": snapshot.last_quote.ask if snapshot.last_quote else None,
            "timestamp": datetime.now(),
        }

    def compute_indicators(
        self,
        df: pd.DataFrame,
        rsi_periods: list[int] | None = None,
        macd_fast: int = 5,
        macd_slow: int = 13,
        macd_signal: int = 8,
        volume_sma_period: int = 20,
    ) -> pd.DataFrame:
        """Add RSI, MACD, and Volume SMA columns to an OHLCV DataFrame.

        Parameters
        ----------
        df : pd.DataFrame
            Must contain at least ``close`` and ``volume`` columns.
        rsi_periods : list[int]
            RSI look-back windows.  Defaults to ``[7, 14]``.
        macd_fast, macd_slow, macd_signal : int
            MACD parameters.
        volume_sma_period : int
            Window for volume simple moving average.
        """
        if df.empty:
            return df

        rsi_periods = rsi_periods or [7, 14]
        df = df.copy()

        # RSI (Wilder's smoothing)
        for period in rsi_periods:
            df[f"rsi_{period}"] = self._compute_rsi(df["close"], period)

        # MACD
        ema_fast = df["close"].ewm(span=macd_fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=macd_slow, adjust=False).mean()
        df["macd"] = ema_fast - ema_slow
        df["macd_signal"] = df["macd"].ewm(span=macd_signal, adjust=False).mean()
        df["macd_histogram"] = df["macd"] - df["macd_signal"]

        # Volume SMA
        df["volume_sma"] = df["volume"].rolling(window=volume_sma_period).mean()

        return df

    @staticmethod
    def _compute_rsi(series: pd.Series, period: int) -> pd.Series:
        """Compute RSI using Wilder's exponential smoothing."""
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        # avg_loss == 0 means pure upward movement → RSI = 100
        return rsi.fillna(100.0)
