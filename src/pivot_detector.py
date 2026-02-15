"""Module 2: Swing Pivot Detector — identify local highs and lows."""

from __future__ import annotations

import logging

import pandas as pd

from src.models import Pivot, PivotType, SequenceClassification

logger = logging.getLogger(__name__)


class PivotDetector:
    """Detect swing pivot highs and lows in OHLCV data.

    Parameters
    ----------
    sensitivity : int
        Number of bars on each side required to confirm a pivot.
        * 3  — aggressive (more pivots, more noise)
        * 5  — balanced  (default; good for 5-min SPY)
        * 8  — conservative (fewer pivots, cleaner waves)
    """

    def __init__(self, sensitivity: int = 5):
        self.sensitivity = sensitivity

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find_pivots(self, df: pd.DataFrame) -> list[Pivot]:
        """Return a list of :class:`Pivot` objects found in *df*.

        The DataFrame must contain ``high``, ``low`` columns and have a
        ``DatetimeIndex``.
        """
        if df.empty or len(df) < 2 * self.sensitivity + 1:
            return []

        highs = df["high"].values
        lows = df["low"].values
        timestamps = df.index
        n = self.sensitivity
        pivots: list[Pivot] = []

        for i in range(n, len(df) - n):
            # --- Pivot high check ---
            is_high = True
            for j in range(1, n + 1):
                if highs[i] < highs[i - j] or highs[i] < highs[i + j]:
                    is_high = False
                    break
            if is_high:
                strength = self._measure_strength(highs, i, "high", len(df))
                pivots.append(
                    Pivot(
                        type=PivotType.HIGH,
                        price=float(highs[i]),
                        bar_index=i,
                        timestamp=timestamps[i].to_pydatetime(),
                        strength=strength,
                    )
                )

            # --- Pivot low check ---
            is_low = True
            for j in range(1, n + 1):
                if lows[i] > lows[i - j] or lows[i] > lows[i + j]:
                    is_low = False
                    break
            if is_low:
                strength = self._measure_strength(lows, i, "low", len(df))
                pivots.append(
                    Pivot(
                        type=PivotType.LOW,
                        price=float(lows[i]),
                        bar_index=i,
                        timestamp=timestamps[i].to_pydatetime(),
                        strength=strength,
                    )
                )

        # Sort by bar_index
        pivots.sort(key=lambda p: p.bar_index)
        return pivots

    def filter_significant_pivots(
        self,
        pivots: list[Pivot],
        min_swing_pct: float = 0.3,
    ) -> list[Pivot]:
        """Keep only pivots whose preceding swing exceeds *min_swing_pct* %.

        Also enforces alternation: consecutive pivots of the same type are
        collapsed — only the most extreme is kept.
        """
        if len(pivots) < 2:
            return list(pivots)

        # --- Step 1: enforce alternation ---
        alternated = self._enforce_alternation(pivots)

        # --- Step 2: filter by minimum swing size ---
        significant: list[Pivot] = [alternated[0]]
        for i in range(1, len(alternated)):
            prev = significant[-1]
            curr = alternated[i]
            swing_pct = abs(curr.price - prev.price) / prev.price * 100
            if swing_pct >= min_swing_pct:
                significant.append(curr)
            else:
                # If the current pivot is a "better" extreme than the last
                # recorded pivot of the same type, replace it.
                if curr.type == prev.type:
                    if (
                        curr.type == PivotType.HIGH and curr.price > prev.price
                    ) or (
                        curr.type == PivotType.LOW and curr.price < prev.price
                    ):
                        significant[-1] = curr

        return significant

    def classify_pivot_sequence(
        self, pivots: list[Pivot]
    ) -> SequenceClassification:
        """Classify a pivot sequence as impulse-up, impulse-down, corrective,
        or unclear based on the alternating high/low pattern.
        """
        if len(pivots) < 4:
            return SequenceClassification.UNCLEAR

        highs = [p.price for p in pivots if p.type == PivotType.HIGH]
        lows = [p.price for p in pivots if p.type == PivotType.LOW]

        if len(highs) < 2 or len(lows) < 2:
            return SequenceClassification.UNCLEAR

        higher_highs = all(highs[i] > highs[i - 1] for i in range(1, len(highs)))
        higher_lows = all(lows[i] > lows[i - 1] for i in range(1, len(lows)))
        lower_highs = all(highs[i] < highs[i - 1] for i in range(1, len(highs)))
        lower_lows = all(lows[i] < lows[i - 1] for i in range(1, len(lows)))

        if higher_highs and higher_lows:
            return SequenceClassification.IMPULSE_UP
        if lower_highs and lower_lows:
            return SequenceClassification.IMPULSE_DOWN
        if (lower_highs and higher_lows) or (higher_highs and lower_lows):
            return SequenceClassification.CORRECTIVE
        return SequenceClassification.UNCLEAR

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _measure_strength(
        values, index: int, pivot_type: str, length: int
    ) -> float:
        """Count how many additional bars the pivot held as extreme."""
        count = 0
        # Look right from the pivot
        for k in range(index + 1, length):
            if pivot_type == "high" and values[k] < values[index]:
                count += 1
            elif pivot_type == "low" and values[k] > values[index]:
                count += 1
            else:
                break
        return float(count)

    @staticmethod
    def _enforce_alternation(pivots: list[Pivot]) -> list[Pivot]:
        """Collapse consecutive same-type pivots, keeping the most extreme."""
        if not pivots:
            return []
        result: list[Pivot] = [pivots[0]]
        for p in pivots[1:]:
            if p.type == result[-1].type:
                # Keep the more extreme of the two
                if p.type == PivotType.HIGH:
                    if p.price > result[-1].price:
                        result[-1] = p
                else:
                    if p.price < result[-1].price:
                        result[-1] = p
            else:
                result.append(p)
        return result
