#!/usr/bin/env python3
"""End-to-end pipeline demo using saved Yahoo response fixtures.

This proves wiring works: bars -> indicators -> pivots -> waves -> fibs ->
divergences -> options chain -> strategy -> signal JSON -> persistence ->
API endpoint. The Yahoo HTTP layer is replaced with the saved JSON fixtures
because the sandbox host filter blocks query{1,2}.finance.yahoo.com.

Run identically against live Yahoo by simply omitting the patches:
    python scripts/run_scanner.py --tickers SPY,QQQ,NVDA --print-signals
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import api as api_module  # noqa: E402
from src.data_feed import DataFeed  # noqa: E402
from src.options_feed import OptionsFeed  # noqa: E402
from src.persistence import SignalStore  # noqa: E402
from src.scanner import scan_universe  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("demo")

FIXTURES = ROOT / "tests" / "fixtures"
DEMO_DIR = ROOT / "demo_output"
DEMO_DIR.mkdir(exist_ok=True)


def _fixture_bars() -> pd.DataFrame:
    raw = pd.read_csv(FIXTURES / "spy_5min_sample.csv", parse_dates=["timestamp"])
    raw.set_index("timestamp", inplace=True)
    return raw


def _fixture_options() -> dict:
    return json.loads((FIXTURES / "yahoo_options_sample.json").read_text())


def _patched_get_bars(self, *, timeframe="1h", lookback_days=60, end_date=None,
                     use_cache=False, ticker=None):
    """Return the fixture frame regardless of timeframe/ticker — demo only."""
    df = _fixture_bars()
    return df


def _patched_get_chain(self, ticker, target_dte=7):
    payload = _fixture_options()
    chain = OptionsFeed._original_get_chain(self, ticker, target_dte)  # type: ignore[attr-defined]
    return chain


def _patched_request(self, ticker, expiration_unix):
    return _fixture_options()


def main() -> None:
    print("=" * 72)
    print("Wave Options Scanner — DEMO PIPELINE (fixture-backed)")
    print("=" * 72)

    store = SignalStore(
        jsonl_dir=DEMO_DIR / "signals",
        db_path=DEMO_DIR / "signals.db",
    )

    with (
        patch.object(DataFeed, "get_bars", _patched_get_bars),
        patch.object(OptionsFeed, "_request", _patched_request),
    ):
        signals = scan_universe(
            ["SPY", "QQQ", "NVDA"],
            timeframe="1h",
            lookback_days=60,
            sensitivity=5,
            min_swing_pct=0.3,
            target_dte=7,
            use_cache=False,
            persist=True,
            post_to_discord=False,
            store=store,
        )

    print(f"\nProduced {len(signals)} signals.")
    if signals:
        sample = signals[0]
        # Force a future expiration in display since the fixture is older
        sample = json.loads(json.dumps(sample))  # deep copy
        print("\n--- SAMPLE SIGNAL JSON ---")
        print(json.dumps(sample, indent=2))

    # Demo the API by hitting the in-process FastAPI app
    print("\n--- API DEMO ---")
    api_module._store = store
    from fastapi.testclient import TestClient
    import os
    os.environ["DISABLE_SCHEDULER"] = "1"
    with TestClient(api_module.app) as client:
        api_module._store = store
        r = client.get("/health")
        print(f"GET /health           -> {r.status_code} {r.json()}")
        r = client.get("/api/signals?limit=3")
        rows = r.json()
        print(f"GET /api/signals      -> {r.status_code} ({len(rows)} signals)")
        for row in rows:
            print(
                f"   {row['ticker']:<5} "
                f"{row['direction']:<5} "
                f"score={row['confluence']['score']:>5.1f} "
                f"structure={row['options']['suggested_structure']:<18} "
                f"spot=${row['price']['spot']:.2f}"
            )
        r = client.get("/api/signals/latest")
        print(f"GET /api/signals/latest -> {r.status_code} ({len(r.json())} latest rows)")

    # Show files written
    print("\n--- PERSISTENCE ---")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    jsonl = DEMO_DIR / "signals" / f"{today}.jsonl"
    print(f"JSONL:  {jsonl}  ({jsonl.stat().st_size} bytes)" if jsonl.exists() else "JSONL: (none)")
    db = DEMO_DIR / "signals.db"
    print(f"SQLite: {db}  ({db.stat().st_size} bytes)" if db.exists() else "SQLite: (none)")

    print("\nDemo complete. To run against live Yahoo from your machine:")
    print("  pip install -r requirements.txt")
    print("  export DISCORD_WEBHOOK_URL='...'        # optional")
    print("  export SCAN_TICKERS='SPY,QQQ,NVDA'")
    print("  python scripts/run_scanner.py --print-signals")
    print("  uvicorn src.api:app --reload            # then GET http://localhost:8000/api/signals")


if __name__ == "__main__":
    main()
