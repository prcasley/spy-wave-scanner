"""JSON serialization helpers for scanner dataclasses."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from dataclasses import asdict, is_dataclass
from typing import Any


class ScanEncoder(json.JSONEncoder):
    """Custom JSON encoder for scanner dataclasses, enums, and datetimes."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Enum):
            return obj.value
        if is_dataclass(obj) and not isinstance(obj, type):
            return asdict(obj)
        return super().default(obj)


def scan_result_to_json(
    ticker: str,
    timestamp: datetime,
    current_price: float,
    timeframe: str,
    bar_count: int,
    ohlcv_records: list[dict],
    pivots: list,
    wave_count: Any | None,
    fib_levels: list,
    confluence_zones: list,
    divergences: list,
    alerts: list,
    projection: Any | None,
    market_status: str = "open",
) -> dict:
    """Build a JSON-serializable dict from pipeline results."""
    result: dict[str, Any] = {
        "ticker": ticker,
        "timestamp": timestamp.isoformat(),
        "current_price": current_price,
        "timeframe": timeframe,
        "bar_count": bar_count,
        "market_status": market_status,
        "ohlcv": ohlcv_records,
    }

    # Pivots
    result["pivots"] = [
        {
            "type": p.type.value,
            "price": p.price,
            "bar_index": p.bar_index,
            "timestamp": p.timestamp.isoformat(),
            "strength": p.strength,
        }
        for p in pivots
    ]

    # Wave count
    if wave_count:
        result["wave_count"] = {
            "pattern": wave_count.pattern_type,
            "direction": wave_count.direction.value,
            "confidence": round(wave_count.confidence, 3),
            "invalidation_price": wave_count.invalidation_price,
            "is_complete": wave_count.is_complete,
            "waves": [
                {
                    "label": w.label.value,
                    "start_price": w.start.price,
                    "end_price": w.end.price,
                    "start_time": w.start.timestamp.isoformat(),
                    "end_time": w.end.timestamp.isoformat(),
                    "start_bar": w.start.bar_index,
                    "end_bar": w.end.bar_index,
                }
                for w in wave_count.waves
            ],
        }
    else:
        result["wave_count"] = None

    # Fib levels
    result["fib_levels"] = [
        {"ratio": lv.ratio, "price": lv.price, "label": lv.label, "source": lv.source}
        for lv in fib_levels
    ]

    # Confluence zones
    result["confluence_zones"] = [
        {
            "center_price": z.center_price,
            "strength": z.strength,
            "price_range": list(z.price_range),
        }
        for z in confluence_zones
    ]

    # Divergences
    result["divergences"] = [
        {
            "type": d.type.value,
            "indicator": d.indicator,
            "price_1": d.price_pivot_1.price,
            "price_2": d.price_pivot_2.price,
            "indicator_value_1": d.indicator_value_1,
            "indicator_value_2": d.indicator_value_2,
            "bar_start": d.bar_index_start,
            "bar_end": d.bar_index_end,
        }
        for d in divergences
    ]

    # Alerts
    result["alerts"] = [
        {
            "type": a.alert_type.value,
            "priority": a.priority.value,
            "message": a.message,
            "current_price": a.current_price,
            "target_price": a.target_price,
        }
        for a in alerts
    ]

    # Projection
    if projection:
        result["projection"] = {
            "next_wave": projection.next_wave,
            "primary_target": projection.primary_target,
            "alt_targets": projection.alt_targets,
            "invalidation": projection.invalidation,
            "confidence": projection.confidence,
        }
    else:
        result["projection"] = None

    return result
