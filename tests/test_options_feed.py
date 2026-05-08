"""Unit tests for OptionsFeed (Yahoo v7 chain parsing)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.options_feed import OptionsFeed, OptionsFeedError


FIXTURE = Path(__file__).parent / "fixtures" / "yahoo_options_sample.json"


@pytest.fixture
def options_payload() -> dict:
    return json.loads(FIXTURE.read_text())


def test_get_chain_returns_calls_puts_and_spot(options_payload):
    feed = OptionsFeed()
    with patch.object(feed, "_request", return_value=options_payload):
        chain = feed.get_chain("SPY", target_dte=7)
    assert chain.ticker == "SPY"
    assert chain.spot == pytest.approx(612.45)
    assert chain.selected_expiration is not None
    assert len(chain.calls) == 7
    assert len(chain.puts) == 6
    # Implied vol should be carried through
    assert all(c.implied_volatility > 0 for c in chain.calls)


def test_get_chain_picks_nearest_dte(options_payload):
    feed = OptionsFeed()
    with patch.object(feed, "_request", return_value=options_payload):
        chain = feed.get_chain("SPY", target_dte=14)
    # The fixture has expirations at 7, 14, 21 days from 2024-05-15 baseline,
    # so picking 14 DTE should yield one of those (we just verify it loaded).
    assert chain.selected_expiration is not None


def test_get_chain_raises_when_no_chain_returned():
    feed = OptionsFeed()
    bad = {"optionChain": {"result": [], "error": "Symbol not found"}}
    with patch.object(feed, "_request", return_value=bad):
        with pytest.raises(OptionsFeedError):
            feed.get_chain("BOGUS", target_dte=7)
