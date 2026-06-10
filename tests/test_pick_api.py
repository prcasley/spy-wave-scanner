"""API tests for the Trade-of-the-Day endpoints and PWA serving."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


def _signal(ticker="SPY", direction="long", score=78.0):
    return {
        "signal_id": f"id-{ticker}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ticker": ticker,
        "direction": direction,
        "wave": {"primary_count": "wave_3_impulse", "primary_probability": 0.65,
                 "current_wave": "3", "degree": "intermediate"},
        "price": {"spot": 100.0, "entry_zone": [99.5, 100.5], "invalidation": 95.0,
                  "targets": [{"price": 110.0, "fib_ratio": 1.618, "probability": 0.55}]},
        "options": {
            "suggested_structure": "long_call", "expiration": "2026-06-19", "dte": 8,
            "legs": [{"action": "buy", "type": "call", "strike": 100.0,
                      "premium": 2.0, "delta": 0.5, "iv": 0.18}],
            "max_loss": 200.0, "max_gain": "unlimited", "breakeven": 102.0,
            "probability_of_profit": 0.48,
        },
        "confluence": {"score": score, "factors": ["wave_3_extension"]},
        "risk": {"suggested_position_size_pct": 1.5, "stop_loss_method": "invalidation_level"},
    }


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DISABLE_SCHEDULER", "1")
    from src import api as api_module
    from src.daily_pick import PickStore
    from src.persistence import SignalStore

    store = SignalStore(jsonl_dir=tmp_path / "signals", db_path=tmp_path / "signals.db")
    pick_store = PickStore(db_path=tmp_path / "picks.db")

    with TestClient(api_module.app) as c:
        api_module._store = store
        api_module._pick_store = pick_store
        yield c


def test_pick_today_returns_best_trade(client):
    signals = [_signal("SPY", score=60), _signal("NVDA", score=88)]
    from src import api as api_module
    from src.daily_pick import get_or_create_pick as real_pick

    def fake_pick(style, force, store):
        return real_pick(
            style, force=force, store=api_module._pick_store,
            scan_fn=lambda *a, **k: signals,
        )

    with patch("src.api.get_or_create_pick", side_effect=fake_pick):
        resp = client.get("/api/pick/today?style=auto")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ticker"] == "NVDA"
    assert body["trade_type"] == "long_call"
    assert body["instrument"] == "options"


def test_pick_today_invalid_style_422(client):
    resp = client.get("/api/pick/today?style=banana")
    assert resp.status_code == 422


def test_pick_today_404_when_no_setups(client):
    from src.daily_pick import NoPickAvailable
    with patch("src.api.get_or_create_pick", side_effect=NoPickAvailable("nothing today")):
        resp = client.get("/api/pick/today?style=short")
    assert resp.status_code == 404
    assert "nothing today" in resp.json()["detail"]


def test_pick_history_endpoint(client):
    from src import api as api_module
    from src.daily_pick import get_or_create_pick
    get_or_create_pick(
        "auto", store=api_module._pick_store,
        scan_fn=lambda *a, **k: [_signal("SPY")],
    )
    resp = client.get("/api/pick/history")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_pwa_index_served(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Wave Trader" in resp.text
    assert "manifest.json" in resp.text


def test_pwa_manifest_and_sw_served(client):
    m = client.get("/manifest.json")
    assert m.status_code == 200
    assert m.json()["display"] == "standalone"

    sw = client.get("/sw.js")
    assert sw.status_code == 200
    assert "service worker" in sw.text.lower() or "addEventListener" in sw.text


def test_pwa_static_assets_served(client):
    for path in ("/static/styles.css", "/static/app.js", "/static/icons/icon-192.png"):
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} not served"
