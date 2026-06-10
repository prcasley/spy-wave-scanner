"""FastAPI app — signals API, Trade-of-the-Day API, and the PWA frontend."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.daily_pick import (
    NoPickAvailable,
    PickStore,
    VALID_STYLES,
    get_or_create_pick,
)
from src.persistence import SignalStore
from src.scanner import _env_tickers, scan_universe

logger = logging.getLogger(__name__)

_WEB_DIR = Path(__file__).resolve().parent.parent / "web"

_store: Optional[SignalStore] = None
_pick_store: Optional[PickStore] = None
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
    global _store, _pick_store, _scheduler
    _store = SignalStore()
    _pick_store = PickStore()

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


# ---------------------------------------------------------------------------
# Trade of the Day
# ---------------------------------------------------------------------------

def _pick_or_404(style: str, force: bool) -> dict:
    if style not in VALID_STYLES:
        raise HTTPException(422, detail=f"style must be one of {VALID_STYLES}")
    try:
        return get_or_create_pick(style, force=force, store=_pick_store)  # type: ignore[arg-type]
    except NoPickAvailable as exc:
        raise HTTPException(404, detail=str(exc))


@app.get("/api/pick/today")
def pick_today(style: str = Query("auto")) -> dict:
    return _pick_or_404(style, force=False)


@app.post("/api/pick/refresh")
def pick_refresh(style: str = Query("auto")) -> dict:
    return _pick_or_404(style, force=True)


@app.get("/api/pick/history")
def pick_history(limit: int = Query(30, ge=1, le=365)) -> list[dict]:
    if _pick_store is None:
        raise HTTPException(503, detail="pick store not initialised")
    return _pick_store.history(limit=limit)


# ---------------------------------------------------------------------------
# PWA frontend (served only if the web/ directory exists)
# ---------------------------------------------------------------------------

if _WEB_DIR.exists():
    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(_WEB_DIR / "index.html")

    @app.get("/manifest.json", include_in_schema=False)
    def manifest() -> FileResponse:
        return FileResponse(_WEB_DIR / "manifest.json")

    @app.get("/sw.js", include_in_schema=False)
    def service_worker() -> FileResponse:
        # Served from root so the service worker scope covers the whole app
        return FileResponse(_WEB_DIR / "sw.js", media_type="application/javascript")

    app.mount("/static", StaticFiles(directory=_WEB_DIR / "static"), name="static")
