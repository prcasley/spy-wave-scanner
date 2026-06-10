"""Tests for the PivotDetector module."""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from src.models import Pivot, PivotType, SequenceClassification
from src.pivot_detector import PivotDetector


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_df(highs: list[float], lows: list[float]) -> pd.DataFrame:
    """Create a minimal OHLCV DataFrame from explicit high/low arrays."""
    n = len(highs)
    idx = pd.date_range("2025-01-10 09:30", periods=n, freq="5min")
    return pd.DataFrame(
        {
            "open": [(h + lo) / 2 for h, lo in zip(highs, lows)],
            "high": highs,
            "low": lows,
            "close": [(h + lo) / 2 for h, lo in zip(highs, lows)],
            "volume": [1000] * n,
        },
        index=idx,
    )


def _zigzag(n: int = 100, amplitude: float = 5.0, base: float = 690.0) -> pd.DataFrame:
    """Generate a zigzag price series with clear swing highs/lows."""
    period = 20  # bars per half-cycle
    t = np.arange(n)
    wave = amplitude * np.sin(2 * np.pi * t / (2 * period))
    mid = base + wave
    high = mid + 0.3
    low = mid - 0.3
    return _make_df(high.tolist(), low.tolist())


# ── Tests ──────────────────────────────────────────────────────────────────

class TestFindPivots:
    def test_returns_empty_for_short_series(self):
        df = _make_df([1, 2, 3], [0.5, 1.5, 2.5])
        det = PivotDetector(sensitivity=3)
        assert det.find_pivots(df) == []

    def test_detects_clear_high_and_low(self):
        # Create a V shape: low in the middle, high at edges
        n = 25
        mid = 12
        # Prices drop toward mid then rise — forms a trough at mid
        highs = [690 + abs(i - mid) * 0.5 + 0.2 for i in range(n)]
        lows = [690 + abs(i - mid) * 0.5 for i in range(n)]
        df = _make_df(highs, lows)
        det = PivotDetector(sensitivity=3)
        pivots = det.find_pivots(df)
        # Should find at least a low near the middle
        low_pivots = [p for p in pivots if p.type == PivotType.LOW]
        assert len(low_pivots) >= 1
        lowest = min(low_pivots, key=lambda p: p.price)
        assert abs(lowest.bar_index - mid) <= 3

    def test_zigzag_produces_alternating_pivots(self):
        df = _zigzag(n=200, amplitude=3.0)
        det = PivotDetector(sensitivity=5)
        pivots = det.find_pivots(df)
        # Should get a decent number of pivots
        assert len(pivots) >= 4
        # After filtering, should alternate
        filtered = det.filter_significant_pivots(pivots, min_swing_pct=0.1)
        for i in range(1, len(filtered)):
            assert filtered[i].type != filtered[i - 1].type

    def test_sensitivity_affects_count(self):
        df = _zigzag(n=200, amplitude=3.0)
        aggressive = PivotDetector(sensitivity=3)
        conservative = PivotDetector(sensitivity=8)
        p_agg = aggressive.find_pivots(df)
        p_con = conservative.find_pivots(df)
        assert len(p_agg) >= len(p_con)


class TestFilterSignificantPivots:
    def test_removes_small_swings(self):
        now = datetime(2025, 1, 10, 10, 0)
        pivots = [
            Pivot(PivotType.HIGH, 695.0, 0, now, 5),
            Pivot(PivotType.LOW, 694.8, 5, now + timedelta(minutes=25), 3),  # tiny swing
            Pivot(PivotType.HIGH, 695.1, 10, now + timedelta(minutes=50), 4),
            Pivot(PivotType.LOW, 690.0, 20, now + timedelta(minutes=100), 8),  # big swing
        ]
        det = PivotDetector()
        filtered = det.filter_significant_pivots(pivots, min_swing_pct=0.3)
        # The tiny swing LOW at 694.8 should be removed
        assert all(p.price != 694.8 for p in filtered)
        # The big low at 690 should remain
        assert any(p.price == 690.0 for p in filtered)


class TestClassifySequence:
    def test_impulse_down(self):
        now = datetime(2025, 1, 10, 10, 0)
        pivots = [
            Pivot(PivotType.HIGH, 696, 0, now, 5),
            Pivot(PivotType.LOW, 691, 10, now + timedelta(minutes=50), 5),
            Pivot(PivotType.HIGH, 695, 20, now + timedelta(minutes=100), 5),
            Pivot(PivotType.LOW, 682, 40, now + timedelta(minutes=200), 5),
            Pivot(PivotType.HIGH, 689, 50, now + timedelta(minutes=250), 5),
            Pivot(PivotType.LOW, 680, 60, now + timedelta(minutes=300), 5),
        ]
        det = PivotDetector()
        assert det.classify_pivot_sequence(pivots) == SequenceClassification.IMPULSE_DOWN

    def test_impulse_up(self):
        now = datetime(2025, 1, 10, 10, 0)
        pivots = [
            Pivot(PivotType.LOW, 680, 0, now, 5),
            Pivot(PivotType.HIGH, 685, 10, now + timedelta(minutes=50), 5),
            Pivot(PivotType.LOW, 682, 20, now + timedelta(minutes=100), 5),
            Pivot(PivotType.HIGH, 690, 40, now + timedelta(minutes=200), 5),
            Pivot(PivotType.LOW, 687, 50, now + timedelta(minutes=250), 5),
            Pivot(PivotType.HIGH, 696, 60, now + timedelta(minutes=300), 5),
        ]
        det = PivotDetector()
        assert det.classify_pivot_sequence(pivots) == SequenceClassification.IMPULSE_UP

    def test_unclear_for_few_pivots(self):
        now = datetime(2025, 1, 10, 10, 0)
        pivots = [
            Pivot(PivotType.HIGH, 695, 0, now, 5),
            Pivot(PivotType.LOW, 690, 10, now + timedelta(minutes=50), 5),
        ]
        det = PivotDetector()
        assert det.classify_pivot_sequence(pivots) == SequenceClassification.UNCLEAR
