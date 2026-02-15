"""Tests for the WaveCounter module — Elliott Wave rule validation."""

from datetime import datetime, timedelta


from src.models import (
    Pivot,
    PivotType,
    Wave,
    WaveCount,
    WaveDirection,
    WaveLabel,
)
from src.wave_counter import WaveCounter


# ── Helpers ────────────────────────────────────────────────────────────────

def _p(ptype: PivotType, price: float, idx: int) -> Pivot:
    """Shorthand pivot constructor."""
    return Pivot(
        type=ptype,
        price=price,
        bar_index=idx,
        timestamp=datetime(2025, 1, 10, 10, 0) + timedelta(minutes=idx * 5),
        strength=5.0,
    )


def _make_impulse_down() -> list[Pivot]:
    """Textbook 5-wave impulse down (SPY example from the chart).

    Wave 1: 696 → 691  (5 pts)
    Wave 2: 691 → 695  (retrace 80% — aggressive but valid)
    Wave 3: 695 → 682  (13 pts — longest, ≈ 2.6x W1)
    Wave 4: 682 → 689  (7 pts — does NOT overlap W1 end 691)
    Wave 5: 689 → 680  (9 pts)
    """
    return [
        _p(PivotType.HIGH, 696.0, 0),   # origin
        _p(PivotType.LOW,  691.0, 10),   # W1 end
        _p(PivotType.HIGH, 695.0, 20),   # W2 end
        _p(PivotType.LOW,  682.0, 40),   # W3 end
        _p(PivotType.HIGH, 689.0, 50),   # W4 end
        _p(PivotType.LOW,  680.0, 60),   # W5 end
    ]


def _make_impulse_rule1_violation() -> list[Pivot]:
    """Wave 2 retraces > 100% of Wave 1."""
    return [
        _p(PivotType.HIGH, 696.0, 0),
        _p(PivotType.LOW,  691.0, 10),   # W1 = 5 pts
        _p(PivotType.HIGH, 697.0, 20),   # W2 retrace = 6 pts > 5 → violation
        _p(PivotType.LOW,  682.0, 40),
        _p(PivotType.HIGH, 689.0, 50),
        _p(PivotType.LOW,  680.0, 60),
    ]


def _make_impulse_rule3_violation() -> list[Pivot]:
    """Wave 4 overlaps Wave 1 territory."""
    return [
        _p(PivotType.HIGH, 696.0, 0),
        _p(PivotType.LOW,  691.0, 10),   # W1 end = 691
        _p(PivotType.HIGH, 695.0, 20),
        _p(PivotType.LOW,  682.0, 40),
        _p(PivotType.HIGH, 692.0, 50),   # W4 end = 692 > 691 → overlap
        _p(PivotType.LOW,  680.0, 60),
    ]


# ── Tests ──────────────────────────────────────────────────────────────────

class TestCountImpulse:
    def test_valid_impulse_down(self):
        wc = WaveCounter()
        pivots = _make_impulse_down()
        result = wc.count_impulse(pivots, direction=WaveDirection.DOWN)
        assert result is not None
        assert len(result.waves) == 5
        assert result.pattern_type == "impulse"

    def test_valid_impulse_has_positive_confidence(self):
        wc = WaveCounter()
        pivots = _make_impulse_down()
        result = wc.count_impulse(pivots, direction=WaveDirection.DOWN)
        assert result.confidence > 0.0

    def test_returns_none_for_too_few_pivots(self):
        wc = WaveCounter()
        pivots = _make_impulse_down()[:3]
        result = wc.count_impulse(pivots, direction=WaveDirection.DOWN)
        assert result is None


class TestValidateRules:
    def test_valid_count_passes(self):
        wc = WaveCounter()
        pivots = _make_impulse_down()
        result = wc.count_impulse(pivots, direction=WaveDirection.DOWN)
        is_valid, violations = wc.validate_wave_rules(result)
        assert is_valid
        assert violations == []

    def test_rule1_wave2_overretrace(self):
        wc = WaveCounter()
        pivots = _make_impulse_rule1_violation()
        result = wc.count_impulse(pivots, direction=WaveDirection.DOWN)
        is_valid, violations = wc.validate_wave_rules(result)
        assert not is_valid
        assert any("Rule 1" in v for v in violations)

    def test_rule3_wave4_overlap(self):
        wc = WaveCounter()
        pivots = _make_impulse_rule3_violation()
        result = wc.count_impulse(pivots, direction=WaveDirection.DOWN)
        is_valid, violations = wc.validate_wave_rules(result)
        assert not is_valid
        assert any("Rule 3" in v for v in violations)

    def test_rule2_wave3_shortest(self):
        """Wave 3 is the shortest impulse wave → violation."""
        pivots = [
            _p(PivotType.HIGH, 696.0, 0),
            _p(PivotType.LOW,  691.0, 10),   # W1 = 5
            _p(PivotType.HIGH, 695.0, 20),
            _p(PivotType.LOW,  693.0, 40),   # W3 = 2 (shortest!)
            _p(PivotType.HIGH, 694.0, 50),
            _p(PivotType.LOW,  680.0, 60),   # W5 = 14
        ]
        wc = WaveCounter()
        result = wc.count_impulse(pivots, direction=WaveDirection.DOWN)
        is_valid, violations = wc.validate_wave_rules(result)
        assert not is_valid
        assert any("Rule 2" in v for v in violations)


class TestInvalidation:
    def test_invalidation_level_set(self):
        wc = WaveCounter()
        pivots = _make_impulse_down()
        result = wc.count_impulse(pivots, direction=WaveDirection.DOWN)
        assert result.invalidation_price is not None


class TestProjection:
    def test_complete_impulse_projects_correction(self):
        wc = WaveCounter()
        pivots = _make_impulse_down()
        result = wc.count_impulse(pivots, direction=WaveDirection.DOWN)
        proj = wc.project_targets(result)
        assert proj is not None
        assert "correction" in proj.next_wave.lower() or "ABC" in proj.next_wave
        assert proj.primary_target > result.waves[-1].end.price  # rally target

    def test_partial_count_projects_next_wave(self):
        """With only W1 and W2, should project Wave 3."""
        wc = WaveCounter()
        pivots = _make_impulse_down()[:3]  # origin, W1 end, W2 end
        # Only 3 pivots → won't get 5 waves; test via manual construction
        w1 = Wave(WaveLabel.W1, pivots[0], pivots[1])
        w2 = Wave(WaveLabel.W2, pivots[1], pivots[2])
        partial = WaveCount(
            waves=[w1, w2],
            direction=WaveDirection.DOWN,
            pattern_type="impulse",
        )
        proj = wc.project_targets(partial)
        assert proj is not None
        assert proj.next_wave == "Wave 3"


class TestCorrective:
    def test_abc_correction(self):
        """Simple zigzag correction upward after a decline."""
        pivots = [
            _p(PivotType.LOW,  680.0, 0),   # A start
            _p(PivotType.HIGH, 688.0, 10),  # A end
            _p(PivotType.LOW,  683.0, 20),  # B end
            _p(PivotType.HIGH, 692.0, 30),  # C end
        ]
        wc = WaveCounter()
        result = wc.count_corrective(pivots, direction=WaveDirection.UP)
        assert result is not None
        assert result.pattern_type == "corrective"
        assert len(result.waves) == 3
