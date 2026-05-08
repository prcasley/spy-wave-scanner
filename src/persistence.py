"""Persist signals to JSONL files (one per day) and a SQLite database.

The trader app polls SQLite for fast queries and reads JSONL for replay.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

_DEFAULT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_JSONL_DIR = _DEFAULT_ROOT / "signals"
_DEFAULT_DB_PATH = _DEFAULT_ROOT / "signals.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    signal_id        TEXT PRIMARY KEY,
    ticker           TEXT NOT NULL,
    timestamp        TEXT NOT NULL,
    direction        TEXT NOT NULL,
    confluence_score REAL NOT NULL,
    structure        TEXT NOT NULL,
    spot             REAL NOT NULL,
    payload          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_signals_ticker ON signals(ticker);
CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(timestamp);
"""


class SignalStore:
    """Combined JSONL + SQLite persistence."""

    def __init__(
        self,
        jsonl_dir: Optional[Path | str] = None,
        db_path: Optional[Path | str] = None,
    ) -> None:
        self.jsonl_dir = Path(jsonl_dir) if jsonl_dir else _DEFAULT_JSONL_DIR
        self.db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        self.jsonl_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(_SCHEMA)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def append(self, signal: dict) -> None:
        """Write the signal to today's JSONL and INSERT (or REPLACE) in SQLite."""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        jsonl_path = self.jsonl_dir / f"{ts}.jsonl"
        with jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(signal, separators=(",", ":")) + "\n")

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO signals
                  (signal_id, ticker, timestamp, direction,
                   confluence_score, structure, spot, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    signal["signal_id"],
                    signal["ticker"],
                    signal["timestamp"],
                    signal["direction"],
                    float(signal["confluence"]["score"]),
                    signal["options"]["suggested_structure"],
                    float(signal["price"]["spot"]),
                    json.dumps(signal, separators=(",", ":")),
                ),
            )
            conn.commit()
        logger.info(
            "Persisted signal %s for %s (%s)",
            signal["signal_id"][:8], signal["ticker"], jsonl_path.name,
        )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def query(
        self,
        ticker: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        clauses: list[str] = []
        args: list = []
        if ticker:
            clauses.append("ticker = ?")
            args.append(ticker.upper())
        if since:
            clauses.append("timestamp >= ?")
            args.append(since)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        args.append(limit)
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                f"SELECT payload FROM signals {where} "
                f"ORDER BY timestamp DESC LIMIT ?",
                args,
            )
            return [json.loads(row[0]) for row in cur.fetchall()]

    def latest_per_ticker(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """
                SELECT payload FROM signals
                WHERE (ticker, timestamp) IN (
                    SELECT ticker, MAX(timestamp) FROM signals GROUP BY ticker
                )
                ORDER BY ticker
                """
            )
            return [json.loads(row[0]) for row in cur.fetchall()]

    def replay_jsonl(self, date: str) -> Iterable[dict]:
        """Yield every signal from `signals/<date>.jsonl`."""
        path = self.jsonl_dir / f"{date}.jsonl"
        if not path.exists():
            return
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)
