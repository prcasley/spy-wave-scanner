"""Unit tests for SignalStore (JSONL + SQLite)."""

import json
from datetime import datetime, timezone


from src.persistence import SignalStore


def _sample_signal(ticker: str = "SPY", score: float = 78.0) -> dict:
    return {
        "signal_id": f"id-{ticker}-{score}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ticker": ticker,
        "direction": "long",
        "wave": {"primary_count": "wave_3_impulse", "primary_probability": 0.65, "current_wave": "3"},
        "price": {
            "spot": 100.0, "entry_zone": [99.5, 100.5], "invalidation": 95.0,
            "targets": [{"price": 110.0, "fib_ratio": 1.618, "probability": 0.55}],
        },
        "options": {
            "suggested_structure": "long_call",
            "expiration": "2026-05-16",
            "dte": 8,
            "legs": [{"action":"buy","type":"call","strike":100.0,"premium":2.0,"delta":0.5,"iv":0.2}],
            "max_loss": 200.0, "max_gain": "unlimited", "breakeven": 102.0,
            "probability_of_profit": 0.5,
        },
        "confluence": {"score": score, "factors": ["wave_3_extension"]},
        "risk": {"suggested_position_size_pct": 1.5, "stop_loss_method": "invalidation_level"},
    }


def test_append_and_query(tmp_path):
    store = SignalStore(jsonl_dir=tmp_path / "signals", db_path=tmp_path / "signals.db")
    store.append(_sample_signal("SPY"))
    store.append(_sample_signal("NVDA"))
    rows = store.query(limit=10)
    assert len(rows) == 2
    only_spy = store.query(ticker="SPY", limit=10)
    assert len(only_spy) == 1
    assert only_spy[0]["ticker"] == "SPY"


def test_jsonl_file_written(tmp_path):
    store = SignalStore(jsonl_dir=tmp_path / "signals", db_path=tmp_path / "signals.db")
    sig = _sample_signal("AAPL")
    store.append(sig)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    files = list((tmp_path / "signals").glob("*.jsonl"))
    assert any(f.name == f"{today}.jsonl" for f in files)
    line = (tmp_path / "signals" / f"{today}.jsonl").read_text().splitlines()[0]
    assert json.loads(line)["ticker"] == "AAPL"


def test_replay_jsonl(tmp_path):
    store = SignalStore(jsonl_dir=tmp_path / "signals", db_path=tmp_path / "signals.db")
    store.append(_sample_signal("AAPL"))
    store.append(_sample_signal("SPY"))
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = list(store.replay_jsonl(today))
    assert len(rows) == 2


def test_latest_per_ticker(tmp_path):
    store = SignalStore(jsonl_dir=tmp_path / "signals", db_path=tmp_path / "signals.db")
    store.append(_sample_signal("SPY", score=70))
    later = _sample_signal("SPY", score=80)
    later["timestamp"] = datetime.now(timezone.utc).isoformat()
    store.append(later)
    store.append(_sample_signal("NVDA", score=72))
    rows = store.latest_per_ticker()
    assert len(rows) == 2
    spy_row = next(r for r in rows if r["ticker"] == "SPY")
    assert spy_row["confluence"]["score"] == 80
