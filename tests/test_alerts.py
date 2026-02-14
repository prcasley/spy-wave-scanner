"""Tests for the AlertEngine module."""

from datetime import datetime, timedelta

import pytest

from src.alert_engine import AlertEngine
from src.models import (
    Alert,
    AlertPriority,
    AlertType,
    ConfluenceZone,
    Divergence,
    DivergenceType,
    FibLevel,
    Pivot,
    PivotType,
    WaveCount,
    WaveDirection,
    WaveLabel,
    Wave,
)


# ── Helpers ────────────────────────────────────────────────────────────────

def _fib(ratio: float, price: float, label: str = "test") -> FibLevel:
    return FibLevel(ratio=ratio, price=price, label=f"{label} retracement")


def _p(ptype: PivotType, price: float, idx: int) -> Pivot:
    return Pivot(
        type=ptype,
        price=price,
        bar_index=idx,
        timestamp=datetime(2025, 1, 10, 10, 0) + timedelta(minutes=idx * 5),
        strength=5.0,
    )


def _wave_count_complete() -> WaveCount:
    """A completed 5-wave impulse down."""
    pivots = [
        _p(PivotType.HIGH, 696.0, 0),
        _p(PivotType.LOW, 691.0, 10),
        _p(PivotType.HIGH, 695.0, 20),
        _p(PivotType.LOW, 682.0, 40),
        _p(PivotType.HIGH, 689.0, 50),
        _p(PivotType.LOW, 680.0, 60),
    ]
    waves = [
        Wave(WaveLabel.W1, pivots[0], pivots[1]),
        Wave(WaveLabel.W2, pivots[1], pivots[2]),
        Wave(WaveLabel.W3, pivots[2], pivots[3]),
        Wave(WaveLabel.W4, pivots[3], pivots[4]),
        Wave(WaveLabel.W5, pivots[4], pivots[5]),
    ]
    return WaveCount(
        waves=waves,
        direction=WaveDirection.DOWN,
        pattern_type="impulse",
        confidence=0.75,
        invalidation_price=691.0,
    )


# ── Tests ──────────────────────────────────────────────────────────────────

class TestProximityAlerts:
    def test_approaching_fib_level(self):
        engine = AlertEngine(proximity_pct=0.15)
        fibs = [_fib(0.382, 689.00, "38.2%")]
        alerts = engine.check_proximity_alerts(
            current_price=689.05,
            wave_count=None,
            fib_levels=fibs,
        )
        assert len(alerts) >= 1
        assert alerts[0].alert_type in (
            AlertType.APPROACHING_RESISTANCE,
            AlertType.APPROACHING_SUPPORT,
        )

    def test_no_alert_when_far_from_levels(self):
        engine = AlertEngine(proximity_pct=0.15)
        fibs = [_fib(0.382, 689.00, "38.2%")]
        alerts = engine.check_proximity_alerts(
            current_price=685.00,
            wave_count=None,
            fib_levels=fibs,
        )
        assert len(alerts) == 0

    def test_invalidation_warning(self):
        engine = AlertEngine(invalidation_pct=0.20)
        wc = _wave_count_complete()
        alerts = engine.check_proximity_alerts(
            current_price=690.80,
            wave_count=wc,
            fib_levels=[],
        )
        inv_alerts = [a for a in alerts if a.alert_type == AlertType.INVALIDATION_WARNING]
        assert len(inv_alerts) >= 1
        assert inv_alerts[0].priority == AlertPriority.HIGH

    def test_wave_complete_alert(self):
        engine = AlertEngine()
        wc = _wave_count_complete()
        alerts = engine.check_proximity_alerts(
            current_price=680.00,
            wave_count=wc,
            fib_levels=[],
        )
        complete_alerts = [a for a in alerts if a.alert_type == AlertType.WAVE_COMPLETE]
        assert len(complete_alerts) == 1
        assert complete_alerts[0].priority == AlertPriority.HIGH


class TestConfluenceZoneAlert:
    def test_price_in_confluence(self):
        engine = AlertEngine()
        zone = ConfluenceZone(
            center_price=689.10,
            levels=[_fib(0.382, 689.00), _fib(0.618, 689.20)],
            strength=2,
        )
        alerts = engine.check_proximity_alerts(
            current_price=689.10,
            wave_count=None,
            fib_levels=[],
            confluence_zones=[zone],
        )
        conf_alerts = [a for a in alerts if a.alert_type == AlertType.CONFLUENCE_ZONE]
        assert len(conf_alerts) == 1


class TestDivergenceAlert:
    def test_divergence_alert(self):
        engine = AlertEngine()
        div = Divergence(
            type=DivergenceType.BULLISH,
            indicator="RSI(14)",
            price_pivot_1=_p(PivotType.LOW, 682.0, 40),
            price_pivot_2=_p(PivotType.LOW, 680.0, 60),
            indicator_value_1=30.0,
            indicator_value_2=35.0,
            bar_index_start=40,
            bar_index_end=60,
        )
        alerts = engine.check_proximity_alerts(
            current_price=680.50,
            wave_count=None,
            fib_levels=[],
            divergences=[div],
        )
        div_alerts = [a for a in alerts if a.alert_type == AlertType.DIVERGENCE_DETECTED]
        assert len(div_alerts) == 1
        assert div_alerts[0].priority == AlertPriority.HIGH


class TestCooldown:
    def test_duplicate_alert_suppressed(self):
        engine = AlertEngine(proximity_pct=0.15, cooldown_minutes=15)
        fibs = [_fib(0.382, 689.00, "38.2%")]
        alerts_1 = engine.check_proximity_alerts(689.05, None, fibs)
        alerts_2 = engine.check_proximity_alerts(689.05, None, fibs)
        # Second call should be suppressed by cooldown
        assert len(alerts_1) >= 1
        assert len(alerts_2) == 0


class TestFormatting:
    def test_format_alert_contains_price(self):
        engine = AlertEngine()
        alert = Alert(
            alert_type=AlertType.APPROACHING_RESISTANCE,
            priority=AlertPriority.MEDIUM,
            ticker="SPY",
            current_price=689.05,
            target_price=689.00,
            message="Test",
        )
        text = engine.format_alert(alert)
        assert "$689.05" in text
        assert "MEDIUM" in text

    def test_format_alert_contains_invalidation(self):
        engine = AlertEngine()
        alert = Alert(
            alert_type=AlertType.INVALIDATION_WARNING,
            priority=AlertPriority.HIGH,
            ticker="SPY",
            current_price=690.80,
            invalidation_price=691.00,
            message="Invalidation near",
        )
        text = engine.format_alert(alert)
        assert "$691.00" in text
        assert "HIGH" in text
