"""Unit tests for scanner trade-plan logic."""

from datetime import datetime

from src.models import Pivot, PivotType, Wave, WaveCount, WaveDirection, WaveLabel
from src.scanner import _trade_plan


def _pivot(price: float, ptype: PivotType, idx: int) -> Pivot:
    return Pivot(type=ptype, price=price, bar_index=idx, timestamp=datetime.now())


def _completed_up_correction() -> WaveCount:
    # A up (100→105), B down (105→102), C up (102→107)
    p0 = _pivot(100.0, PivotType.LOW, 0)
    p1 = _pivot(105.0, PivotType.HIGH, 10)
    p2 = _pivot(102.0, PivotType.LOW, 20)
    p3 = _pivot(107.0, PivotType.HIGH, 30)
    wc = WaveCount(
        waves=[
            Wave(WaveLabel.WA, p0, p1),
            Wave(WaveLabel.WB, p1, p2),
            Wave(WaveLabel.WC, p2, p3),
        ],
        direction=WaveDirection.UP,
        pattern_type="corrective",
        invalidation_price=100.0,
    )
    return wc


def _partial_down_impulse() -> WaveCount:
    p0 = _pivot(110.0, PivotType.HIGH, 0)
    p1 = _pivot(105.0, PivotType.LOW, 10)
    p2 = _pivot(108.0, PivotType.HIGH, 20)
    wc = WaveCount(
        waves=[Wave(WaveLabel.W1, p0, p1), Wave(WaveLabel.W2, p1, p2)],
        direction=WaveDirection.DOWN,
        pattern_type="impulse",
        invalidation_price=110.0,
    )
    return wc


def test_completed_up_correction_trades_short_with_stop_at_c_extreme():
    direction, stop = _trade_plan(_completed_up_correction())
    assert direction == "short"
    assert stop == 107.0  # beyond the C-wave high, not the A-wave origin


def test_completed_down_correction_trades_long():
    wc = _completed_up_correction()
    wc.direction = WaveDirection.DOWN
    # Mirror prices so C ends at a low
    wc.waves[-1].end.price = 95.0
    direction, stop = _trade_plan(wc)
    assert direction == "long"
    assert stop == 95.0


def test_impulse_trades_with_wave_direction_and_invalidation():
    direction, stop = _trade_plan(_partial_down_impulse())
    assert direction == "short"
    assert stop == 110.0


def test_incomplete_corrective_not_reversed():
    wc = _completed_up_correction()
    wc.waves = wc.waves[:2]  # only A and B — correction still running
    direction, stop = _trade_plan(wc)
    assert direction == "long"  # trades with the wave direction
    assert stop == 100.0
