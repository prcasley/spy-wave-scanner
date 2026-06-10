"""Trade-of-the-Day engine — scan a universe, rank signals, recommend ONE trade.

The pick is idempotent per (UTC date, style): the first request of the day
runs a scan and stores the result; subsequent requests return the stored pick
so the recommendation doesn't flip-flop intraday. `force=True` re-scans.

Styles:
    auto    — engine decides instrument: options when confluence is strong,
              stock (buy/hold or short) when conviction is moderate
    options — always express the trade as the selected options structure
    stock   — always express as shares: buy_hold (long) or short_sell (short)
    short   — only consider short-direction setups
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal, Optional

logger = logging.getLogger(__name__)

TradeStyle = Literal["auto", "options", "stock", "short"]
VALID_STYLES: tuple[str, ...] = ("auto", "options", "stock", "short")

# Liquid, optionable names. Override with DAILY_PICK_UNIVERSE env var.
DEFAULT_UNIVERSE = (
    "SPY,QQQ,IWM,DIA,AAPL,MSFT,NVDA,AMZN,GOOGL,META,"
    "TSLA,AMD,NFLX,SMH,XLF,XLE"
)

_DEFAULT_DB = Path(__file__).resolve().parent.parent / "signals.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_picks (
    pick_date TEXT NOT NULL,
    style     TEXT NOT NULL,
    payload   TEXT NOT NULL,
    PRIMARY KEY (pick_date, style)
);
"""


class NoPickAvailable(RuntimeError):
    """Raised when no signal in the universe qualifies for the given style."""


def universe() -> list[str]:
    raw = os.environ.get("DAILY_PICK_UNIVERSE", DEFAULT_UNIVERSE)
    return [t.strip().upper() for t in raw.split(",") if t.strip()]


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class PickStore:
    """SQLite-backed store for daily picks (one row per date+style)."""

    def __init__(self, db_path: Optional[Path | str] = None) -> None:
        self.db_path = Path(db_path) if db_path else _DEFAULT_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(_SCHEMA)

    def get(self, pick_date: str, style: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT payload FROM daily_picks WHERE pick_date = ? AND style = ?",
                (pick_date, style),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, pick: dict) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO daily_picks (pick_date, style, payload) "
                "VALUES (?, ?, ?)",
                (pick["date"], pick["style"], json.dumps(pick, separators=(",", ":"))),
            )
            conn.commit()

    def history(self, limit: int = 30) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT payload FROM daily_picks ORDER BY pick_date DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [json.loads(r[0]) for r in rows]


# ---------------------------------------------------------------------------
# Ranking & trade-type recommendation
# ---------------------------------------------------------------------------

def _rank_score(signal: dict) -> float:
    """Composite ranking: confluence dominates, wave probability and options
    probability-of-profit break ties."""
    score = float(signal["confluence"]["score"])
    prob = float(signal["wave"].get("primary_probability", 0.0))
    pop = float(signal["options"].get("probability_of_profit", 0.0))
    return score + 10.0 * prob + 5.0 * pop


def _eligible(signals: list[dict], style: TradeStyle) -> list[dict]:
    if style == "short":
        return [s for s in signals if s["direction"] == "short"]
    return list(signals)


def recommend_trade_type(signal: dict, style: TradeStyle) -> tuple[str, str, list[str]]:
    """Return (trade_type, instrument, rationale_lines).

    trade_type ∈ {long_call, bull_call_spread, long_put, bear_put_spread,
                  buy_hold, short_sell}
    instrument ∈ {options, stock}
    """
    direction = signal["direction"]
    score = float(signal["confluence"]["score"])
    structure = signal["options"]["suggested_structure"]
    legs = signal["options"].get("legs") or []
    iv = float(legs[0]["iv"]) if legs else 0.0
    rationale: list[str] = []

    if style == "options":
        rationale.append(
            f"Options style locked: {structure} chosen from live chain "
            f"(IV {iv:.0%}, DTE {signal['options']['dte']})"
        )
        return structure, "options", rationale

    if style == "stock":
        if direction == "long":
            rationale.append("Stock style locked: buy and hold toward wave target")
            return "buy_hold", "stock", rationale
        rationale.append("Stock style locked, short setup: sell short with stop at invalidation")
        return "short_sell", "stock", rationale

    if style == "short":
        rationale.append(
            "Short style locked: short the shares (a long put / bear put spread "
            "is the defined-risk alternative)"
        )
        return "short_sell", "stock", rationale

    # auto — engine decides
    if score >= 60:
        rationale.append(
            f"High confluence ({score:.0f}) — leveraged expression via options "
            f"({structure}, IV {iv:.0%})"
        )
        return structure, "options", rationale
    if direction == "long":
        rationale.append(
            f"Moderate confluence ({score:.0f}) — shares over options to avoid "
            "premium decay while the count develops"
        )
        return "buy_hold", "stock", rationale
    rationale.append(
        f"Moderate confluence ({score:.0f}) short setup — short shares with a "
        "hard stop rather than paying put premium"
    )
    return "short_sell", "stock", rationale


def _stock_plan(signal: dict) -> dict:
    """Entry/stop/target plan for share-based trades, derived from wave levels."""
    price = signal["price"]
    entry_low, entry_high = price["entry_zone"]
    entry_mid = (entry_low + entry_high) / 2.0
    stop = float(price["invalidation"])
    targets = price.get("targets") or []
    target = float(targets[0]["price"]) if targets else None
    risk = abs(entry_mid - stop)
    reward = abs(target - entry_mid) if target is not None else None
    return {
        "entry_zone": [round(entry_low, 2), round(entry_high, 2)],
        "stop": round(stop, 2),
        "target": round(target, 2) if target is not None else None,
        "risk_per_share": round(risk, 2),
        "reward_per_share": round(reward, 2) if reward is not None else None,
        "reward_risk_ratio": round(reward / risk, 2) if reward and risk > 0 else None,
    }


def _build_pick(signal: dict, style: TradeStyle, pick_date: str) -> dict:
    trade_type, instrument, rationale = recommend_trade_type(signal, style)

    rationale.insert(
        0,
        f"{signal['ticker']} ranked #1 of universe: {signal['wave']['primary_count']} "
        f"(p={signal['wave']['primary_probability']:.0%}), "
        f"confluence {signal['confluence']['score']:.0f}",
    )
    rationale.extend(f"Factor: {f}" for f in signal["confluence"].get("factors", []))

    return {
        "pick_id": str(uuid.uuid4()),
        "date": pick_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "style": style,
        "ticker": signal["ticker"],
        "direction": signal["direction"],
        "trade_type": trade_type,
        "instrument": instrument,
        "score": float(signal["confluence"]["score"]),
        "rationale": rationale,
        "stock_plan": _stock_plan(signal) if instrument == "stock" else None,
        "signal": signal,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def get_or_create_pick(
    style: TradeStyle = "auto",
    *,
    force: bool = False,
    store: Optional[PickStore] = None,
    scan_fn: Optional[Callable[..., list[dict]]] = None,
    timeframe: str = "1h",
    lookback_days: int = 60,
) -> dict:
    """Return today's pick for *style*, scanning the universe if needed."""
    if style not in VALID_STYLES:
        raise ValueError(f"Unknown style '{style}'. Choose from {VALID_STYLES}")
    store = store or PickStore()
    pick_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if not force:
        existing = store.get(pick_date, style)
        if existing:
            return existing

    if scan_fn is None:
        from src.scanner import scan_universe
        scan_fn = scan_universe

    signals = scan_fn(
        universe(),
        timeframe=timeframe,
        lookback_days=lookback_days,
        use_cache=False,
    )
    candidates = _eligible(signals, style)
    if not candidates:
        detail = (
            f"No {'short-direction ' if style == 'short' else ''}signals found "
            f"across {len(universe())} tickers today"
        )
        raise NoPickAvailable(detail)

    best = max(candidates, key=_rank_score)
    pick = _build_pick(best, style, pick_date)
    store.put(pick)
    logger.info(
        "Daily pick (%s): %s %s via %s, score %.1f",
        style, pick["ticker"], pick["direction"], pick["trade_type"], pick["score"],
    )
    return pick
