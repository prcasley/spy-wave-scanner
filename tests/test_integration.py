"""Integration test — run the full pipeline against saved SPY fixture data."""

from pathlib import Path

import pandas as pd
import pytest

from src.pivot_detector import PivotDetector
from src.fib_mapper import FibMapper
from src.wave_counter import WaveCounter
from src.divergence import DivergenceDetector
from src.alert_engine import AlertEngine
from src.data_feed import DataFeed
from src.models import WaveDirection, WaveLabel


FIXTURE = Path(__file__).parent / "fixtures" / "spy_5min_sample.csv"


@pytest.fixture
def df():
    """Load the saved SPY 5-min fixture and compute indicators."""
    raw = pd.read_csv(FIXTURE, parse_dates=["timestamp"])
    raw.set_index("timestamp", inplace=True)
    feed = DataFeed.__new__(DataFeed)  # skip __init__ (no API key needed)
    return feed.compute_indicators(raw)


class TestFullPipeline:
    def test_fixture_loads(self, df):
        assert not df.empty
        assert len(df) >= 100
        for col in ("open", "high", "low", "close", "volume"):
            assert col in df.columns

    def test_indicators_computed(self, df):
        assert "rsi_14" in df.columns
        assert "rsi_7" in df.columns
        assert "macd" in df.columns
        assert "macd_signal" in df.columns
        assert "macd_histogram" in df.columns
        assert "volume_sma" in df.columns

    def test_pivots_detected(self, df):
        detector = PivotDetector(sensitivity=5)
        pivots = detector.find_pivots(df)
        assert len(pivots) >= 2, "Should detect at least 2 pivots"
        pivots = detector.filter_significant_pivots(pivots, min_swing_pct=0.3)
        assert len(pivots) >= 2, "Should have at least 2 significant pivots"

    def test_wave_count_returns_result(self, df):
        detector = PivotDetector(sensitivity=5)
        pivots = detector.find_pivots(df)
        pivots = detector.filter_significant_pivots(pivots, min_swing_pct=0.3)

        wc = WaveCounter()
        wave_count = wc.count_impulse_best(pivots, direction=WaveDirection.DOWN)
        if wave_count is None:
            wave_count = wc.count_impulse_best(pivots, direction=WaveDirection.UP)
        if wave_count is None:
            wave_count = wc.count_corrective(pivots)

        assert wave_count is not None, "Should detect at least one wave pattern"
        assert wave_count.confidence >= 0.0
        assert len(wave_count.waves) >= 2

    def test_fib_levels_calculated(self, df):
        detector = PivotDetector(sensitivity=5)
        pivots = detector.find_pivots(df)
        pivots = detector.filter_significant_pivots(pivots, min_swing_pct=0.3)

        wc = WaveCounter()
        wave_count = wc.count_impulse_best(pivots, direction=WaveDirection.DOWN)
        if wave_count is None:
            wave_count = wc.count_impulse_best(pivots, direction=WaveDirection.UP)
        if wave_count is None:
            wave_count = wc.count_corrective(pivots)

        assert wave_count is not None
        w1 = wave_count.wave_by_label(WaveLabel.W1) or wave_count.waves[0]

        fm = FibMapper()
        fib_levels = fm.calculate_retracements(
            swing_high=max(w1.start.price, w1.end.price),
            swing_low=min(w1.start.price, w1.end.price),
            direction="down",
        )
        assert len(fib_levels) >= 6, "Should have standard Fibonacci levels"

    def test_divergence_detection_runs(self, df):
        detector = PivotDetector(sensitivity=5)
        pivots = detector.find_pivots(df)
        pivots = detector.filter_significant_pivots(pivots, min_swing_pct=0.3)

        div_det = DivergenceDetector()
        rsi_divs = div_det.detect_rsi_divergence(df, pivots)
        macd_divs = div_det.detect_macd_divergence(df, pivots)
        # Divergences may or may not be present; just ensure no errors
        assert isinstance(rsi_divs, list)
        assert isinstance(macd_divs, list)

    def test_alert_engine_runs(self, df):
        detector = PivotDetector(sensitivity=5)
        pivots = detector.find_pivots(df)
        pivots = detector.filter_significant_pivots(pivots, min_swing_pct=0.3)

        wc = WaveCounter()
        wave_count = wc.count_impulse_best(pivots, direction=WaveDirection.DOWN)
        if wave_count is None:
            wave_count = wc.count_impulse_best(pivots, direction=WaveDirection.UP)
        if wave_count is None:
            wave_count = wc.count_corrective(pivots)

        fm = FibMapper()
        fib_levels = []
        if wave_count:
            w1 = wave_count.wave_by_label(WaveLabel.W1) or wave_count.waves[0]
            fib_levels = fm.calculate_retracements(
                swing_high=max(w1.start.price, w1.end.price),
                swing_low=min(w1.start.price, w1.end.price),
                direction="down",
            )

        ae = AlertEngine(ticker="SPY")
        last_close = df["close"].iloc[-1]
        alerts = ae.check_proximity_alerts(
            current_price=last_close,
            wave_count=wave_count,
            fib_levels=fib_levels,
        )
        assert isinstance(alerts, list)

    def test_full_pipeline_end_to_end(self, df):
        """Run the complete pipeline: indicators -> pivots -> waves -> fibs -> divergences -> alerts."""
        # Pivots
        detector = PivotDetector(sensitivity=5)
        pivots = detector.find_pivots(df)
        pivots = detector.filter_significant_pivots(pivots, min_swing_pct=0.3)

        # Wave counting
        wc = WaveCounter()
        wave_count = wc.count_impulse_best(pivots, direction=WaveDirection.DOWN)
        if wave_count is None:
            wave_count = wc.count_impulse_best(pivots, direction=WaveDirection.UP)
        if wave_count is None:
            wave_count = wc.count_corrective(pivots)

        # Fibs — use first wave regardless of label (works for both impulse and corrective)
        fm = FibMapper()
        fib_levels = []
        confluence_zones = []
        if wave_count and wave_count.waves:
            first_wave = wave_count.wave_by_label(WaveLabel.W1) or wave_count.waves[0]
            fib_levels = fm.calculate_retracements(
                swing_high=max(first_wave.start.price, first_wave.end.price),
                swing_low=min(first_wave.start.price, first_wave.end.price),
                direction="down" if wave_count.direction == WaveDirection.DOWN else "up",
            )
            second_wave = wave_count.wave_by_label(WaveLabel.W2)
            if second_wave:
                ext_levels = fm.calculate_extensions(
                    first_wave.start.price, first_wave.end.price, second_wave.end.price,
                )
                fib_levels.extend(ext_levels)
            confluence_zones = fm.find_fib_confluence([fib_levels])

        # Divergences
        div_det = DivergenceDetector()
        divergences = div_det.detect_rsi_divergence(df, pivots)
        divergences += div_det.detect_macd_divergence(df, pivots)

        # Projection
        projection = None
        if wave_count:
            projection = wc.project_targets(wave_count)

        # Alerts
        ae = AlertEngine(ticker="SPY")
        last_close = df["close"].iloc[-1]
        alerts = ae.check_proximity_alerts(
            current_price=last_close,
            wave_count=wave_count,
            fib_levels=fib_levels,
            confluence_zones=confluence_zones,
            divergences=divergences,
            projection=projection,
        )

        # Assertions: pipeline completed without errors
        assert wave_count is not None
        assert len(fib_levels) > 0
        assert isinstance(alerts, list)
