"""Smoke tests for the FastAPI app."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


def _signal(ticker: str = "SPY") -> dict:
    return {
        "signal_id": f"id-{ticker}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ticker": ticker,
        "direction": "long",
        "wave": {"primary_count": "wave_3_impulse", "primary_probability": 0.6, "current_wave": "3", "degree": "intermediate"},
        "price": {"spot": 100.0, "entry_zone": [99, 101], "invalidation": 95.0, "targets": []},
        "options": {
            "suggested_structure": "long_call", "expiration": "2026-05-16",
            "dte": 8, "legs": [{"action":"buy","type":"call","strike":100,"premium":2,"delta":0.5,"iv":0.2}],
            "max_loss": 200, "max_gain": "unlimited", "breakeven": 102, "probability_of_profit": 0.5,
        },
        "confluence": {"score": 75, "factors": ["wave_3_extension"]},
        "risk": {"suggested_position_size_pct": 1.5, "stop_loss_method": "invalidation_level"},
    }


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Disable scheduler so test setup is fast and deterministic
    monkeypatch.setenv("DISABLE_SCHEDULER", "1")
    monkeypatch.chdir(tmp_path)
    from src import api as api_module
    from src.persistence import SignalStore

    # Use a temp store path for the test
    store = SignalStore(jsonl_dir=tmp_path / "signals", db_path=tmp_path / "signals.db")
    api_module._store = store

    with TestClient(api_module.app) as c:
        # The lifespan resets _store; restore the temp one
        api_module._store = store
        yield c, store


def test_health_endpoint(client):
    c, _ = client
    resp = c.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert isinstance(body["tickers"], list)


def test_signals_endpoint_empty(client):
    c, _ = client
    resp = c.get("/api/signals")
    assert resp.status_code == 200
    assert resp.json() == []


def test_signals_endpoint_returns_persisted(client):
    c, store = client
    store.append(_signal("SPY"))
    store.append(_signal("NVDA"))
    resp = c.get("/api/signals")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 2

    only_spy = c.get("/api/signals?ticker=SPY").json()
    assert len(only_spy) == 1
    assert only_spy[0]["ticker"] == "SPY"


def test_trigger_scan_endpoint_calls_scanner(client):
    c, store = client
    with patch("src.api.scan_universe", return_value=[_signal("AAPL")]) as mock_scan:
        resp = c.post("/api/scan?tickers=AAPL")
    assert resp.status_code == 200
    body = resp.json()
    assert body["scanned"] == ["AAPL"]
    assert body["signals_emitted"] == 1
    mock_scan.assert_called_once()
