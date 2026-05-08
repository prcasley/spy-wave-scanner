"""End-to-end test of signal_builder against canned chain + fixture wave count."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from src.data_feed import DataFeed
from src.fib_mapper import FibMapper
from src.options_feed import OptionsFeed
from src.pivot_detector import PivotDetector
from src.signal_builder import SIGNAL_SCHEMA, build_signal, validate
from src.strategy_selector import select_strategy
from src.wave_counter import WaveCounter
from src.models import WaveDirection, WaveLabel


FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def df():
    raw = pd.read_csv(FIXTURE_DIR / "spy_5min_sample.csv", parse_dates=["timestamp"])
    raw.set_index("timestamp", inplace=True)
    feed = DataFeed.__new__(DataFeed)
    return feed.compute_indicators(raw)


@pytest.fixture
def chain():
    payload = json.loads((FIXTURE_DIR / "yahoo_options_sample.json").read_text())
    feed = OptionsFeed()
    with patch.object(feed, "_request", return_value=payload):
        c = feed.get_chain("SPY", target_dte=7)
    c.selected_expiration = datetime.now(timezone.utc) + timedelta(days=8)
    return c


def test_build_signal_validates_against_schema(df, chain):
    pd_ = PivotDetector(sensitivity=5)
    pivots = pd_.find_pivots(df)
    pivots = pd_.filter_significant_pivots(pivots, min_swing_pct=0.3)

    wc = WaveCounter()
    wave_count = wc.count_impulse_best(pivots, direction=WaveDirection.DOWN)
    if wave_count is None:
        wave_count = wc.count_impulse_best(pivots, direction=WaveDirection.UP)
    if wave_count is None:
        wave_count = wc.count_corrective(pivots, direction=WaveDirection.UP)
    if wave_count is None:
        wave_count = wc.count_corrective(pivots, direction=WaveDirection.DOWN)
    assert wave_count is not None, "Fixture should produce some wave structure"

    fm = FibMapper()
    w1 = wave_count.wave_by_label(WaveLabel.W1) or wave_count.waves[0]
    fib_levels = fm.calculate_retracements(
        swing_high=max(w1.start.price, w1.end.price),
        swing_low=min(w1.start.price, w1.end.price),
        direction="down" if wave_count.direction == WaveDirection.DOWN else "up",
    )
    confluence_zones = fm.find_fib_confluence([fib_levels])
    projection = wc.project_targets(wave_count)

    spot = float(df["close"].iloc[-1])
    direction = "long" if wave_count.direction == WaveDirection.UP else "short"
    strategy = select_strategy(
        chain=chain,
        direction=direction,
        invalidation_price=wave_count.invalidation_price,
        target_price=projection.primary_target if projection else None,
    )

    signal = build_signal(
        ticker="SPY",
        spot=spot,
        wave_count=wave_count,
        projection=projection,
        divergences=[],
        confluence_zones=confluence_zones,
        chain=chain,
        strategy=strategy,
    )

    # If we got here, schema validation already passed inside build_signal
    validate(signal)
    assert signal["ticker"] == "SPY"
    assert signal["direction"] in ("long", "short")
    assert "signal_id" in signal
    assert signal["options"]["legs"]
    assert isinstance(signal["confluence"]["score"], (int, float))


def test_validate_rejects_missing_required_fields():
    from jsonschema.exceptions import ValidationError

    bad = {"signal_id": "x"}  # missing everything else
    with pytest.raises(Exception):
        validate(bad)


def test_schema_has_expected_top_level_required_keys():
    assert "options" in SIGNAL_SCHEMA["required"]
    assert "wave" in SIGNAL_SCHEMA["required"]
    assert "confluence" in SIGNAL_SCHEMA["required"]
