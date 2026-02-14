"""Module 1: Data Feed — fetch and normalise OHLCV data from Polygon.io."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from polygon import RESTClient

logger = logging.getLogger(__name__)


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

    def __init__(self, api_key: str, ticker: str = "SPY"):
        self.client = RESTClient(api_key)
        self.ticker = ticker

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_bars(
        self,
        timeframe: str = "5min",
        lookback_days: int = 5,
        end_date: Optional[datetime] = None,
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

        multiplier, timespan = self._TF_MAP[timeframe]
        end = end_date or datetime.now()
        start = end - timedelta(days=lookback_days)

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
        return df

    def get_realtime_quote(self) -> dict:
        """Return current bid / ask / last for proximity alert checks."""
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
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
