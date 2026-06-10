"""Unit tests for the Trade-of-the-Day engine."""

from datetime import datetime, timezone

import pytest

from src.daily_pick import (
    NoPickAvailable,
    PickStore,
    get_or_create_pick,
    recommend_trade_type,
    universe,
)


def _signal(ticker="SPY", direction="long", score=78.0, prob=0.65, pop=0.48, iv=0.18):
    return {
        "signal_id": f"id-{ticker}-{score}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ticker": ticker,
        "direction": direction,
        "wave": {
            "primary_count": "wave_3_impulse",
            "primary_probability": prob,
            "current_wave": "3",
            "degree": "intermediate",
        },
        "price": {
            "spot": 100.0,
            "entry_zone": [99.5, 100.5],
            "invalidation": 95.0,
            "targets": [{"price": 110.0, "fib_ratio": 1.618, "probability": 0.55}],
        },
        "options": {
            "suggested_structure": "long_call" if direction == "long" else "long_put",
            "expiration": "2026-06-19",
            "dte": 8,
            "legs": [{"action": "buy", "type": "call" if direction == "long" else "put",
                      "strike": 100.0, "premium": 2.0, "delta": 0.5, "iv": iv}],
            "max_loss": 200.0,
            "max_gain": "unlimited",
            "breakeven": 102.0,
            "probability_of_profit": pop,
        },
        "confluence": {"score": score, "factors": ["wave_3_extension"]},
        "risk": {"suggested_position_size_pct": 1.5, "stop_loss_method": "invalidation_level"},
    }


@pytest.fixture
def store(tmp_path):
    return PickStore(db_path=tmp_path / "picks.db")


def test_picks_highest_ranked_signal(store):
    signals = [_signal("SPY", score=60), _signal("NVDA", score=85), _signal("QQQ", score=70)]
    pick = get_or_create_pick("auto", store=store, scan_fn=lambda *a, **k: signals)
    assert pick["ticker"] == "NVDA"
    assert pick["score"] == 85


def test_idempotent_same_day(store):
    calls = []

    def scan(*a, **k):
        calls.append(1)
        return [_signal("SPY", score=75)]

    p1 = get_or_create_pick("auto", store=store, scan_fn=scan)
    p2 = get_or_create_pick("auto", store=store, scan_fn=scan)
    assert p1["pick_id"] == p2["pick_id"]
    assert len(calls) == 1, "Second call must come from the store, not a re-scan"


def test_force_rescans(store):
    n = [0]

    def scan(*a, **k):
        n[0] += 1
        return [_signal("SPY", score=75)]

    p1 = get_or_create_pick("auto", store=store, scan_fn=scan)
    p2 = get_or_create_pick("auto", store=store, scan_fn=scan, force=True)
    assert n[0] == 2
    assert p1["pick_id"] != p2["pick_id"]


def test_styles_stored_independently(store):
    pick_auto = get_or_create_pick(
        "auto", store=store, scan_fn=lambda *a, **k: [_signal("SPY", score=80)]
    )
    pick_stock = get_or_create_pick(
        "stock", store=store, scan_fn=lambda *a, **k: [_signal("SPY", score=80)]
    )
    assert pick_auto["pick_id"] != pick_stock["pick_id"]
    assert pick_auto["instrument"] == "options"  # score 80 >= 60
    assert pick_stock["instrument"] == "stock"
    assert pick_stock["trade_type"] == "buy_hold"


def test_short_style_filters_to_short_signals(store):
    signals = [_signal("SPY", direction="long", score=90),
               _signal("QQQ", direction="short", score=55)]
    pick = get_or_create_pick("short", store=store, scan_fn=lambda *a, **k: signals)
    assert pick["ticker"] == "QQQ"
    assert pick["trade_type"] == "short_sell"


def test_short_style_raises_when_no_short_setups(store):
    signals = [_signal("SPY", direction="long", score=90)]
    with pytest.raises(NoPickAvailable):
        get_or_create_pick("short", store=store, scan_fn=lambda *a, **k: signals)


def test_no_signals_raises(store):
    with pytest.raises(NoPickAvailable):
        get_or_create_pick("auto", store=store, scan_fn=lambda *a, **k: [])


def test_invalid_style_rejected(store):
    with pytest.raises(ValueError):
        get_or_create_pick("yolo", store=store, scan_fn=lambda *a, **k: [])


def test_auto_low_score_long_recommends_buy_hold():
    trade_type, instrument, rationale = recommend_trade_type(
        _signal(score=45, direction="long"), "auto"
    )
    assert trade_type == "buy_hold"
    assert instrument == "stock"
    assert rationale


def test_auto_high_score_recommends_options():
    trade_type, instrument, _ = recommend_trade_type(
        _signal(score=82, direction="long"), "auto"
    )
    assert trade_type == "long_call"
    assert instrument == "options"


def test_auto_low_score_short_recommends_short_sell():
    trade_type, instrument, _ = recommend_trade_type(
        _signal(score=45, direction="short"), "auto"
    )
    assert trade_type == "short_sell"
    assert instrument == "stock"


def test_stock_plan_attached_for_stock_trades(store):
    pick = get_or_create_pick(
        "stock", store=store, scan_fn=lambda *a, **k: [_signal("SPY", score=80)]
    )
    plan = pick["stock_plan"]
    assert plan is not None
    assert plan["stop"] == 95.0
    assert plan["target"] == 110.0
    assert plan["reward_risk_ratio"] == pytest.approx(2.0, abs=0.1)


def test_history_returns_recent_picks(store):
    get_or_create_pick("auto", store=store, scan_fn=lambda *a, **k: [_signal("SPY")])
    get_or_create_pick("stock", store=store, scan_fn=lambda *a, **k: [_signal("QQQ")])
    hist = store.history(limit=10)
    assert len(hist) == 2


def test_universe_env_override(monkeypatch):
    monkeypatch.setenv("DAILY_PICK_UNIVERSE", "AAPL, msft ,NVDA")
    assert universe() == ["AAPL", "MSFT", "NVDA"]
