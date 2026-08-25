#!/usr/bin/env python3
"""Invariant tests for the dashboard generator.

Standard library only, so this runs in the workflow before a build without
installing anything. Each test pins a bug that actually shipped once — read the
"Design notes" section of dashboard/README.md before changing any of them.

    python dashboard/test_generate.py
"""
from __future__ import annotations
import math
import os
import random
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("TWELVEDATA_KEY", "test")
import generate as G  # noqa: E402

PAGES_URL = "https://example.invalid/dashboard/"


def _row(symbol: str, day_pct: float, pcr, pcr_err=None, closes=None):
    """Build a computed row without touching the network."""
    closes = closes or [300 + 40 * math.sin(i / 9) + i * 0.15 for i in range(100)]
    quote = {
        "close": str(closes[-1]),
        "previous_close": str(closes[-1] / (1 + day_pct / 100)),
        "name": symbol, "low": str(closes[-1] * 0.99), "high": str(closes[-1] * 1.01),
        "volume": "51234567", "fifty_two_week_low": "250", "fifty_two_week_high": "360",
        "extended_price": None,
    }
    series = [{"close": str(c)} for c in reversed(closes)]
    return G.compute(symbol, quote, series, pcr, pcr_err)


class DownsampleKeepsExtremes(unittest.TestCase):
    """The axis labels print min(bars) and max(bars). If downsampling drops
    either extreme, the axis contradicts the price quoted in the card text."""

    def test_random_series_keep_both_extremes(self):
        random.seed(1729)
        for _ in range(400):
            values = [random.uniform(50, 400) for _ in range(random.randint(5, 400))]
            for bars in (12, 20, 26, 40):
                out, _ = G.downsample(values, bars)
                self.assertAlmostEqual(max(out), max(values), places=9)
                self.assertAlmostEqual(min(out), min(values), places=9)

    def test_peak_and_trough_in_the_same_bucket(self):
        # 80 values into 20 bars puts indices 36-39 in one bucket. Placing the
        # spike at 38 and the trough at 39 forces the collision: only one bar can
        # hold a value, so the low must be re-homed rather than dropped.
        # Verify the collision is real before asserting on it — an off-by-one in
        # the bucket maths would otherwise make this test silently vacuous.
        values = [100.0] * 80
        values[38], values[39] = 346.0, 51.0
        self.assertEqual(self._bucket_of(38, 80, 20), self._bucket_of(39, 80, 20),
                         "fixture no longer collides; the test would prove nothing")
        out, mark = G.downsample(values, 20)
        self.assertAlmostEqual(max(out), 346.0)
        self.assertAlmostEqual(min(out), 51.0, msg="the low was dropped by the collision")
        self.assertAlmostEqual(out[mark], 346.0, msg="gold bar must sit on the true peak")

    @staticmethod
    def _bucket_of(index: int, length: int, bars: int) -> int:
        """Mirror of the segmentation inside downsample()."""
        for i in range(bars):
            a = round(i * length / bars)
            b = max(a + 1, round((i + 1) * length / bars))
            if index in (list(range(a, min(b, length))) or [min(a, length - 1)]):
                return i
        raise AssertionError("index outside every bucket")

    def test_series_shorter_than_bar_count_is_untouched(self):
        values = [3.0, 1.0, 4.0, 1.0, 5.0]
        out, mark = G.downsample(values, 20)
        self.assertEqual(out, values)
        self.assertEqual(out[mark], 5.0)

    def test_flat_series_does_not_divide_by_zero(self):
        flat = [100.0] * 60
        self.assertEqual(len(G.sparkline(flat)), 26)
        self.assertIn("bgcolor", G.column_chart(flat, G.GOLD))


class EmailSurvivesIosGmail(unittest.TestCase):
    """iOS Gmail strips CSS `background` while keeping the text colour, which
    renders white-on-white. Colour must ride on bgcolor ATTRIBUTES."""

    def setUp(self):
        self.rows = [_row("SPY", 0.42, 1.31), _row("MU", -5.90, 0.66),
                     _row("BE", 1.05, None, "daily 25-call budget exhausted")]

    def _html(self, url):
        return G.render_email(self.rows, "2026-01-01 20:00 UTC", [], url)[0]

    def test_no_css_background_with_or_without_the_button(self):
        # The CTA only renders when PAGES_URL is set, so the no-URL path alone
        # will not catch a regression here. Production always sets it.
        for url in (None, PAGES_URL):
            with self.subTest(url=url):
                self.assertEqual(re.findall(r"background\s*:", self._html(url)), [])

    def test_colour_rides_on_bgcolor_attributes(self):
        self.assertGreaterEqual(len(re.findall(r'bgcolor="', self._html(PAGES_URL))), 7)

    def test_no_empty_cells(self):
        # Empty table cells get collapsed by several clients.
        self.assertEqual(re.findall(r"<td[^>]*>\s*</td>", self._html(PAGES_URL)), [])

    def test_plain_text_twin_carries_the_same_bars(self):
        text = G.render_email(self.rows, "2026-01-01 20:00 UTC", [], PAGES_URL)[1]
        self.assertTrue(any(c in text for c in "█░"))
        for symbol in ("SPY", "MU", "BE"):
            self.assertIn(symbol, text)


class DegradesHonestly(unittest.TestCase):
    """Alpha Vantage's 25/day cap is the binding constraint. A missing put/call
    must read as missing, never as a stale or invented number."""

    def test_budget_exhaustion_reports_rather_than_guesses(self):
        av = G.AlphaVantage("key", budget=0)
        ratio, expiries, err = av.put_call("BE")
        self.assertIsNone(ratio)
        self.assertEqual(expiries, [])
        self.assertIn("budget", err)

    def test_missing_key_is_named(self):
        ratio, _, err = G.AlphaVantage("").put_call("BE")
        self.assertIsNone(ratio)
        self.assertIn("ALPHAVANTAGE_KEY", err)

    def test_gap_is_visible_on_the_card_and_in_data_health(self):
        note = "BE: put/call missing (daily 25-call budget exhausted)."
        rows = [_row("SPY", 0.42, 1.31),
                _row("BE", 1.05, None, "daily 25-call budget exhausted")]
        html = G.render_dashboard(rows, "2026-01-01 20:00 UTC", [note])
        self.assertIn("daily 25-call budget exhausted", html)  # on the card
        self.assertIn(note, html)                              # in Data health

    def test_trend_is_unknown_without_enough_history(self):
        label, _ = G.classify_trend(100.0, None, None)
        self.assertEqual(label, "Unknown")


class Metrics(unittest.TestCase):
    def test_fib_levels_span_the_swing(self):
        levels = G.fib_levels(200.0, 100.0)
        self.assertEqual([f for f, _ in levels], [0.236, 0.382, 0.5, 0.618, 0.786])
        self.assertAlmostEqual(dict(levels)[0.5], 150.0)

    def test_vol_needs_a_full_window(self):
        self.assertIsNone(G.annualized_vol([100.0] * 10))
        self.assertIsNotNone(G.annualized_vol([100 + i % 7 for i in range(60)]))

    def test_trend_classification(self):
        self.assertEqual(G.classify_trend(110, 100, 105)[0], "Uptrend")
        self.assertEqual(G.classify_trend(90, 100, 105)[0], "Broken")
        self.assertEqual(G.classify_trend(102, 100, 105)[0], "Consolidating")


if __name__ == "__main__":
    unittest.main(verbosity=2)
