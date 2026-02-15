"""Module 5: Divergence Detector — RSI and MACD divergence detection."""

from __future__ import annotations

import logging

import pandas as pd

from src.models import Divergence, DivergenceType, Pivot, PivotType

logger = logging.getLogger(__name__)


class DivergenceDetector:
    """Detect bullish and bearish divergences between price and indicators.

    Bearish divergence: Price makes higher high, indicator makes lower high
        → Often signals Wave 5 completion or end of correction.

    Bullish divergence: Price makes lower low, indicator makes higher low
        → Often signals Wave 5 bottom.
    """

    # ------------------------------------------------------------------
    # RSI divergence
    # ------------------------------------------------------------------

    def detect_rsi_divergence(
        self,
        df: pd.DataFrame,
        pivots: list[Pivot],
        rsi_column: str = "rsi_14",
        min_bars_apart: int = 5,
    ) -> list[Divergence]:
        """Detect RSI divergences at swing pivots.

        Parameters
        ----------
        df : pd.DataFrame
            Must contain the specified *rsi_column*.
        pivots : list[Pivot]
            Significant pivots to check.
        rsi_column : str
            Column name for RSI values.
        min_bars_apart : int
            Minimum bar distance between the two pivots forming a divergence.
        """
        if rsi_column not in df.columns:
            logger.warning("RSI column '%s' not found in DataFrame", rsi_column)
            return []

        rsi = df[rsi_column].values
        divergences: list[Divergence] = []

        # --- Bearish divergence (at HIGHs) ---
        highs = [p for p in pivots if p.type == PivotType.HIGH]
        for i in range(1, len(highs)):
            p1, p2 = highs[i - 1], highs[i]
            if abs(p2.bar_index - p1.bar_index) < min_bars_apart:
                continue
            if p1.bar_index >= len(rsi) or p2.bar_index >= len(rsi):
                continue
            rsi1 = rsi[p1.bar_index]
            rsi2 = rsi[p2.bar_index]
            # Price higher high, RSI lower high → bearish
            if p2.price > p1.price and rsi2 < rsi1:
                divergences.append(
                    Divergence(
                        type=DivergenceType.BEARISH,
                        indicator=rsi_column.upper().replace("_", "(") + ")",
                        price_pivot_1=p1,
                        price_pivot_2=p2,
                        indicator_value_1=float(rsi1),
                        indicator_value_2=float(rsi2),
                        bar_index_start=p1.bar_index,
                        bar_index_end=p2.bar_index,
                        timestamp=p2.timestamp,
                    )
                )

        # --- Bullish divergence (at LOWs) ---
        lows = [p for p in pivots if p.type == PivotType.LOW]
        for i in range(1, len(lows)):
            p1, p2 = lows[i - 1], lows[i]
            if abs(p2.bar_index - p1.bar_index) < min_bars_apart:
                continue
            if p1.bar_index >= len(rsi) or p2.bar_index >= len(rsi):
                continue
            rsi1 = rsi[p1.bar_index]
            rsi2 = rsi[p2.bar_index]
            # Price lower low, RSI higher low → bullish
            if p2.price < p1.price and rsi2 > rsi1:
                divergences.append(
                    Divergence(
                        type=DivergenceType.BULLISH,
                        indicator=rsi_column.upper().replace("_", "(") + ")",
                        price_pivot_1=p1,
                        price_pivot_2=p2,
                        indicator_value_1=float(rsi1),
                        indicator_value_2=float(rsi2),
                        bar_index_start=p1.bar_index,
                        bar_index_end=p2.bar_index,
                        timestamp=p2.timestamp,
                    )
                )

        return divergences

    # ------------------------------------------------------------------
    # MACD divergence
    # ------------------------------------------------------------------

    def detect_macd_divergence(
        self,
        df: pd.DataFrame,
        pivots: list[Pivot],
        macd_column: str = "macd_histogram",
        min_bars_apart: int = 5,
    ) -> list[Divergence]:
        """Detect MACD histogram divergences at swing pivots.

        Tracks histogram values at wave 3 vs wave 5 endpoints for the
        classic "wave 5 divergence" signal.
        """
        if macd_column not in df.columns:
            logger.warning("MACD column '%s' not found in DataFrame", macd_column)
            return []

        macd_vals = df[macd_column].values
        divergences: list[Divergence] = []

        # --- Bearish divergence (at HIGHs) ---
        highs = [p for p in pivots if p.type == PivotType.HIGH]
        for i in range(1, len(highs)):
            p1, p2 = highs[i - 1], highs[i]
            if abs(p2.bar_index - p1.bar_index) < min_bars_apart:
                continue
            if p1.bar_index >= len(macd_vals) or p2.bar_index >= len(macd_vals):
                continue
            m1 = macd_vals[p1.bar_index]
            m2 = macd_vals[p2.bar_index]
            if p2.price > p1.price and m2 < m1:
                divergences.append(
                    Divergence(
                        type=DivergenceType.BEARISH,
                        indicator="MACD_HISTOGRAM",
                        price_pivot_1=p1,
                        price_pivot_2=p2,
                        indicator_value_1=float(m1),
                        indicator_value_2=float(m2),
                        bar_index_start=p1.bar_index,
                        bar_index_end=p2.bar_index,
                        timestamp=p2.timestamp,
                    )
                )

        # --- Bullish divergence (at LOWs) ---
        lows = [p for p in pivots if p.type == PivotType.LOW]
        for i in range(1, len(lows)):
            p1, p2 = lows[i - 1], lows[i]
            if abs(p2.bar_index - p1.bar_index) < min_bars_apart:
                continue
            if p1.bar_index >= len(macd_vals) or p2.bar_index >= len(macd_vals):
                continue
            m1 = macd_vals[p1.bar_index]
            m2 = macd_vals[p2.bar_index]
            if p2.price < p1.price and m2 > m1:
                divergences.append(
                    Divergence(
                        type=DivergenceType.BULLISH,
                        indicator="MACD_HISTOGRAM",
                        price_pivot_1=p1,
                        price_pivot_2=p2,
                        indicator_value_1=float(m1),
                        indicator_value_2=float(m2),
                        bar_index_start=p1.bar_index,
                        bar_index_end=p2.bar_index,
                        timestamp=p2.timestamp,
                    )
                )

        return divergences
