"""Unit tests for strategy selection across long/short and IV regimes."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from src.options_feed import OptionsFeed
from src.strategy_selector import StrategySelectorError, select_strategy


FIXTURE = Path(__file__).parent / "fixtures" / "yahoo_options_sample.json"


@pytest.fixture
def chain():
    payload = json.loads(FIXTURE.read_text())
    feed = OptionsFeed()
    with patch.object(feed, "_request", return_value=payload):
        c = feed.get_chain("SPY", target_dte=7)
    # Force a meaningful DTE (the fixture's unix dates may be in the past)
    c.selected_expiration = datetime.now(timezone.utc) + timedelta(days=8)
    return c


def test_long_low_iv_yields_long_call(chain):
    choice = select_strategy(chain=chain, direction="long", high_iv_threshold=0.40)
    assert choice.structure == "long_call"
    assert len(choice.legs) == 1
    assert choice.legs[0].action == "buy"
    assert choice.legs[0].type == "call"
    assert choice.max_loss > 0


def test_long_high_iv_yields_bull_call_spread(chain):
    choice = select_strategy(chain=chain, direction="long", high_iv_threshold=0.10)
    assert choice.structure == "bull_call_spread"
    assert len(choice.legs) == 2
    actions = {l.action for l in choice.legs}
    assert actions == {"buy", "sell"}


def test_short_low_iv_yields_long_put(chain):
    choice = select_strategy(chain=chain, direction="short", high_iv_threshold=0.40)
    assert choice.structure == "long_put"
    assert choice.legs[0].type == "put"


def test_short_high_iv_yields_bear_put_spread(chain):
    choice = select_strategy(chain=chain, direction="short", high_iv_threshold=0.10)
    assert choice.structure == "bear_put_spread"
    assert len(choice.legs) == 2


def test_breakeven_within_chain_range(chain):
    choice = select_strategy(chain=chain, direction="long", high_iv_threshold=0.40)
    strikes = sorted(c.strike for c in chain.calls)
    assert strikes[0] - 5 <= choice.breakeven <= strikes[-1] + 5
