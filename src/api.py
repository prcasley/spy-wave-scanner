"""FastAPI app exposing GET /api/signals plus a manual scan trigger."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException, Query

from src.persistence import SignalStore
from src.scanner import _env_tickers, scan_universe

logger = logging.getLogger(__name__)

_store: Optional[SignalStore] = None
_scheduler: Optional[BackgroundScheduler] = None


def _market_hours_only() -> bool:
    """Skip scheduled scans outside US market hours.

    9:30am-4:00pm ET == 13:30-20:00 UTC (assuming standard time; the cron is a
    best-effort filter, not a regulatory check).
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    if now.weekday() >= 5:
        return False
    minute_of_day = now.hour * 60 + now.minute
    return 13 * 60 + 30 <= minute_of_day <= 20 * 60


def _scheduled_scan() -> None:
    if not _market_hours_only():
        logger.debug("Outside US market hours — skipping scheduled scan")
        return
    try:
        scan_universe(store=_store)
    except Exception:
        logger.exception("Scheduled scan failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _store, _scheduler
    _store = SignalStore()

    interval_min = int(os.environ.get("SCAN_INTERVAL_MIN", "15"))
    if os.environ.get("DISABLE_SCHEDULER", "").lower() in ("1", "true"):
        logger.info("Scheduler disabled via DISABLE_SCHEDULER env var")
    else:
        _scheduler = BackgroundScheduler(timezone="UTC")
        _scheduler.add_job(
            _scheduled_scan,
            "interval",
            minutes=interval_min,
            id="wave_scan",
            max_instances=1,
            coalesce=True,
        )
        _scheduler.start()
        logger.info(
            "Scheduler started: every %d min, tickers=%s",
            interval_min, ",".join(_env_tickers()),
        )
    try:
        yield
    finally:
        if _scheduler is not None:
            _scheduler.shutdown(wait=False)


app = FastAPI(title="Wave Options Scanner", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "tickers": _env_tickers()}


@app.get("/api/signals")
def get_signals(
    ticker: Optional[str] = Query(None),
    since: Optional[str] = Query(None, description="ISO8601 timestamp"),
    limit: int = Query(100, ge=1, le=500),
) -> list[dict]:
    if _store is None:
        raise HTTPException(503, detail="store not initialised")
    return _store.query(ticker=ticker, since=since, limit=limit)


@app.get("/api/signals/latest")
def get_latest() -> list[dict]:
    if _store is None:
        raise HTTPException(503, detail="store not initialised")
    return _store.latest_per_ticker()


@app.post("/api/scan")
def trigger_scan(
    tickers: Optional[str] = Query(None, description="Comma-separated override"),
) -> dict:
    syms = (
        [t.strip().upper() for t in tickers.split(",") if t.strip()]
        if tickers
        else _env_tickers()
    )
    signals = scan_universe(syms, store=_store)
    return {"scanned": syms, "signals_emitted": len(signals)}
