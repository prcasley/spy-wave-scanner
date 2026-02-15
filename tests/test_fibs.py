"""Tests for the FibMapper module."""


from src.fib_mapper import FibMapper
from src.models import FibLevel


class TestRetracements:
    def test_down_retracement_38_2(self):
        """38.2% retrace of 696.12 → 680.63 should ≈ 686.55."""
        fm = FibMapper()
        levels = fm.calculate_retracements(696.12, 680.63, direction="down")
        level_382 = next(lv for lv in levels if lv.ratio == 0.382)
        # 680.63 + (696.12 - 680.63) * 0.382 = 680.63 + 5.9191 ≈ 686.55
        assert abs(level_382.price - 686.55) < 0.05

    def test_down_retracement_50(self):
        fm = FibMapper()
        levels = fm.calculate_retracements(696.12, 680.63, direction="down")
        level_50 = next(lv for lv in levels if lv.ratio == 0.500)
        expected = 680.63 + (696.12 - 680.63) * 0.5  # 688.375
        assert abs(level_50.price - expected) < 0.05

    def test_down_retracement_100(self):
        fm = FibMapper()
        levels = fm.calculate_retracements(696.12, 680.63, direction="down")
        level_100 = next(lv for lv in levels if lv.ratio == 1.000)
        assert abs(level_100.price - 696.12) < 0.05

    def test_up_retracement(self):
        fm = FibMapper()
        levels = fm.calculate_retracements(696.12, 680.63, direction="up")
        level_382 = next(lv for lv in levels if lv.ratio == 0.382)
        # 696.12 - (696.12 - 680.63) * 0.382 = 696.12 - 5.9191 ≈ 690.20
        assert abs(level_382.price - 690.20) < 0.05

    def test_levels_sorted_ascending(self):
        fm = FibMapper()
        levels = fm.calculate_retracements(700.0, 680.0, direction="down")
        prices = [lv.price for lv in levels]
        assert prices == sorted(prices)

    def test_all_standard_ratios_present(self):
        fm = FibMapper()
        levels = fm.calculate_retracements(700.0, 680.0, direction="down")
        ratios = {lv.ratio for lv in levels}
        assert {0.236, 0.382, 0.500, 0.618, 0.786, 1.000}.issubset(ratios)


class TestExtensions:
    def test_161_8_extension_down(self):
        """Wave1: 696→691 (len=5), Wave2 end: 695
        161.8% ext = 695 - 5*1.618 = 686.91"""
        fm = FibMapper()
        levels = fm.calculate_extensions(696.0, 691.0, 695.0)
        ext_1618 = next(lv for lv in levels if lv.ratio == 1.618)
        expected = 695.0 - 5.0 * 1.618  # 686.91
        assert abs(ext_1618.price - expected) < 0.05

    def test_100_extension(self):
        fm = FibMapper()
        levels = fm.calculate_extensions(696.0, 691.0, 695.0)
        ext_100 = next(lv for lv in levels if lv.ratio == 1.000)
        # 695 - 5*1.0 = 690.0
        assert abs(ext_100.price - 690.0) < 0.05

    def test_extension_up(self):
        fm = FibMapper()
        levels = fm.calculate_extensions(680.0, 685.0, 682.0)
        ext_1618 = next(lv for lv in levels if lv.ratio == 1.618)
        # 682 + 5*1.618 = 690.09
        assert abs(ext_1618.price - 690.09) < 0.05


class TestConfluence:
    def test_finds_confluence_zone(self):
        fm = FibMapper()
        set_a = [FibLevel(0.382, 689.00, "38.2%", "set A")]
        set_b = [FibLevel(0.618, 689.20, "61.8%", "set B")]
        zones = fm.find_fib_confluence([set_a, set_b], tolerance=0.50)
        assert len(zones) == 1
        assert zones[0].strength == 2
        assert abs(zones[0].center_price - 689.10) < 0.05

    def test_no_confluence_when_far_apart(self):
        fm = FibMapper()
        set_a = [FibLevel(0.382, 689.00, "38.2%", "set A")]
        set_b = [FibLevel(0.618, 692.00, "61.8%", "set B")]
        zones = fm.find_fib_confluence([set_a, set_b], tolerance=0.50)
        assert len(zones) == 0

    def test_multiple_confluence_zones(self):
        fm = FibMapper()
        levels = [
            FibLevel(0.382, 689.00, "38.2%", "A"),
            FibLevel(0.500, 689.10, "50.0%", "B"),
            FibLevel(0.618, 682.00, "61.8%", "C"),
            FibLevel(0.786, 682.20, "78.6%", "D"),
        ]
        zones = fm.find_fib_confluence([levels], tolerance=0.50)
        assert len(zones) == 2
