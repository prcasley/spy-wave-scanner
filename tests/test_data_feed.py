"""Unit tests for the Yahoo DataFeed wire-format parser and fail-loud behavior."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.data_feed import DataFeed, DataFeedError


FIXTURE = Path(__file__).parent / "fixtures" / "yahoo_chart_sample.json"


@pytest.fixture
def chart_payload() -> dict:
    return json.loads(FIXTURE.read_text())


def test_payload_to_frame_parses_yahoo_v8(chart_payload):
    df = DataFeed._payload_to_frame(chart_payload)
    assert not df.empty
    assert list(df.columns) == ["open", "high", "low", "close", "volume", "vwap"]
    assert len(df) == 6
    assert df["close"].iloc[-1] == pytest.approx(612.45)


def test_payload_to_frame_handles_empty_results():
    assert DataFeed._payload_to_frame({"chart": {"result": []}}).empty
    assert DataFeed._payload_to_frame({"chart": {"result": [{"timestamp": []}]}}).empty


def test_get_bars_uses_payload_to_frame(chart_payload):
    feed = DataFeed(ticker="SPY")
    with patch.object(feed, "_fetch_chart", return_value=chart_payload):
        df = feed.get_bars(timeframe="5min", lookback_days=1, use_cache=False)
    assert not df.empty
    assert df["close"].iloc[-1] == pytest.approx(612.45)


def test_get_bars_fails_loud_when_yahoo_returns_empty():
    feed = DataFeed(ticker="SPY")
    empty_payload = {"chart": {"result": [], "error": None}}
    with patch.object(feed, "_fetch_chart", return_value=empty_payload):
        with pytest.raises(DataFeedError):
            feed.get_bars(timeframe="5min", lookback_days=1, use_cache=False)


def test_compute_indicators_adds_expected_columns(chart_payload):
    feed = DataFeed(ticker="SPY")
    df = feed._payload_to_frame(chart_payload)
    out = feed.compute_indicators(df)
    for col in ("rsi_7", "rsi_14", "macd", "macd_signal", "macd_histogram", "volume_sma"):
        assert col in out.columns


def test_unknown_timeframe_rejected():
    feed = DataFeed(ticker="SPY")
    with pytest.raises(ValueError):
        feed.get_bars(timeframe="3min", lookback_days=1)
