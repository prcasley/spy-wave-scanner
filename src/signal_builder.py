"""Build and validate canonical Wave Options Scanner signal JSON."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from jsonschema import Draft202012Validator

from src.models import (
    ConfluenceZone,
    Divergence,
    DivergenceType,
    WaveCount,
    WaveDirection,
    WaveLabel,
    WaveProjection,
)
from src.options_feed import OptionsChain
from src.strategy_selector import StrategyChoice

logger = logging.getLogger(__name__)


SIGNAL_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": [
        "signal_id", "timestamp", "ticker", "direction",
        "wave", "price", "options", "confluence", "risk",
    ],
    "properties": {
        "signal_id": {"type": "string"},
        "timestamp": {"type": "string"},
        "ticker": {"type": "string"},
        "direction": {"enum": ["long", "short"]},
        "wave": {
            "type": "object",
            "required": ["primary_count", "primary_probability", "current_wave"],
            "properties": {
                "primary_count": {"type": "string"},
                "alternate_count": {"type": ["string", "null"]},
                "primary_probability": {"type": "number"},
                "degree": {"type": "string"},
                "current_wave": {"type": ["string", "integer"]},
            },
        },
        "price": {
            "type": "object",
            "required": ["spot", "entry_zone", "invalidation", "targets"],
            "properties": {
                "spot": {"type": "number"},
                "entry_zone": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 2, "maxItems": 2,
                },
                "invalidation": {"type": "number"},
                "targets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["price", "fib_ratio", "probability"],
                        "properties": {
                            "price": {"type": "number"},
                            "fib_ratio": {"type": "number"},
                            "probability": {"type": "number"},
                        },
                    },
                },
            },
        },
        "options": {
            "type": "object",
            "required": [
                "suggested_structure", "expiration", "dte", "legs",
                "max_loss", "breakeven", "probability_of_profit",
            ],
            "properties": {
                "suggested_structure": {"type": "string"},
                "expiration": {"type": "string"},
                "dte": {"type": "integer"},
                "legs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["action", "type", "strike", "premium", "delta", "iv"],
                        "properties": {
                            "action": {"enum": ["buy", "sell"]},
                            "type": {"enum": ["call", "put"]},
                            "strike": {"type": "number"},
                            "premium": {"type": "number"},
                            "delta": {"type": "number"},
                            "iv": {"type": "number"},
                        },
                    },
                    "minItems": 1,
                },
                "max_loss": {"type": "number"},
                "max_gain": {"type": ["number", "string"]},
                "breakeven": {"type": "number"},
                "probability_of_profit": {"type": "number"},
            },
        },
        "confluence": {
            "type": "object",
            "required": ["score", "factors"],
            "properties": {
                "score": {"type": "number"},
                "factors": {"type": "array", "items": {"type": "string"}},
            },
        },
        "risk": {
            "type": "object",
            "required": ["suggested_position_size_pct", "stop_loss_method"],
            "properties": {
                "suggested_position_size_pct": {"type": "number"},
                "max_loss_at_account_pct_1": {"type": "number"},
                "stop_loss_method": {"type": "string"},
            },
        },
    },
}

_VALIDATOR = Draft202012Validator(SIGNAL_SCHEMA)


class SignalValidationError(ValueError):
    """Raised when a built signal fails schema validation."""


def _wave_direction(wave_count: WaveCount) -> str:
    return "long" if wave_count.direction == WaveDirection.UP else "short"


def _primary_count_label(wave_count: WaveCount) -> str:
    if wave_count.pattern_type == "impulse":
        last = wave_count.current_wave_label
        return f"wave_{last.value}_impulse" if last else "impulse"
    sub = wave_count.corrective_subtype.value if wave_count.corrective_subtype else "abc"
    last = wave_count.current_wave_label
    return f"wave_{last.value}_{sub}" if last else sub


def _current_wave_number(wave_count: WaveCount) -> str:
    last = wave_count.current_wave_label
    return last.value if last else "?"


def _build_targets(
    projection: Optional[WaveProjection],
    base_confidence: float,
) -> list[dict]:
    if not projection or not projection.primary_target:
        return []
    targets = [
        {
            "price": round(float(projection.primary_target), 2),
            "fib_ratio": 1.618,
            "probability": round(min(base_confidence + 0.10, 0.95), 4),
        }
    ]
    for i, alt in enumerate(projection.alt_targets[:2]):
        targets.append(
            {
                "price": round(float(alt), 2),
                "fib_ratio": 1.0 if i == 0 else 2.618,
                "probability": round(max(base_confidence - 0.10 - 0.05 * i, 0.05), 4),
            }
        )
    return targets


def _confluence_factors(
    wave_count: WaveCount,
    divergences: list[Divergence],
    confluence_zones: list[ConfluenceZone],
    chain_iv: float,
) -> tuple[float, list[str]]:
    factors: list[str] = []
    score = wave_count.confidence * 70.0  # base 0..70 from wave confidence

    last_label = wave_count.current_wave_label
    if last_label == WaveLabel.W3:
        factors.append("wave_3_extension")
        score += 5
    elif last_label == WaveLabel.W5:
        factors.append("wave_5_completion")
        score += 4

    for div in divergences:
        if div.type == DivergenceType.BULLISH:
            factors.append("rsi_or_macd_bullish_divergence")
        else:
            factors.append("rsi_or_macd_bearish_divergence")
        score += 6
        break  # only count once

    if confluence_zones:
        factors.append(f"fib_confluence_x{confluence_zones[0].strength}")
        score += 5

    if 0 < chain_iv < 0.30:
        factors.append("iv_rank_below_30")
        score += 4
    elif chain_iv >= 0.50:
        factors.append("iv_rank_high")
        # high IV makes premiums expensive — treat as a small drag
        score -= 2

    return round(min(score, 100.0), 2), factors


def build_signal(
    *,
    ticker: str,
    spot: float,
    wave_count: WaveCount,
    projection: Optional[WaveProjection],
    divergences: list[Divergence],
    confluence_zones: list[ConfluenceZone],
    chain: OptionsChain,
    strategy: StrategyChoice,
    timestamp: Optional[datetime] = None,
    direction: Optional[str] = None,
) -> dict:
    """Assemble the canonical signal dict and validate it against the schema.

    *direction* overrides the raw wave direction — used when a completed
    correction is traded as a reversal. It must match the direction the
    *strategy* legs were built for.
    """
    direction = direction or _wave_direction(wave_count)
    chain_iv = strategy.legs[0].iv if strategy.legs else 0.0
    score, factors = _confluence_factors(
        wave_count, divergences, confluence_zones, chain_iv
    )

    invalidation = (
        wave_count.invalidation_price
        if wave_count.invalidation_price is not None
        else spot * (0.98 if direction == "long" else 1.02)
    )
    entry_low = round(spot * 0.999, 2)
    entry_high = round(spot * 1.001, 2)
    targets = _build_targets(projection, wave_count.confidence)

    max_gain_value: float | str
    if strategy.max_gain == float("inf"):
        max_gain_value = "unlimited"
    else:
        max_gain_value = round(strategy.max_gain, 2)

    expiration_dt = chain.selected_expiration or datetime.now(timezone.utc)
    signal: dict = {
        "signal_id": str(uuid.uuid4()),
        "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
        "ticker": ticker,
        "direction": direction,
        "wave": {
            "primary_count": _primary_count_label(wave_count),
            "alternate_count": None,
            "primary_probability": round(wave_count.confidence, 4),
            "degree": wave_count.degree.value,
            "current_wave": _current_wave_number(wave_count),
        },
        "price": {
            "spot": round(spot, 2),
            "entry_zone": [entry_low, entry_high],
            "invalidation": round(float(invalidation), 2),
            "targets": targets,
        },
        "options": {
            "suggested_structure": strategy.structure,
            "expiration": expiration_dt.date().isoformat(),
            "dte": int(chain.dte),
            "legs": [leg.to_dict() for leg in strategy.legs],
            "max_loss": round(strategy.max_loss, 2),
            "max_gain": max_gain_value,
            "breakeven": round(strategy.breakeven, 2),
            "probability_of_profit": round(strategy.probability_of_profit, 4),
        },
        "confluence": {"score": score, "factors": factors},
        "risk": {
            "suggested_position_size_pct": 1.5,
            "max_loss_at_account_pct_1": 100.0,
            "stop_loss_method": "invalidation_level",
        },
    }
    validate(signal)
    return signal


def validate(signal: dict) -> None:
    errors = sorted(_VALIDATOR.iter_errors(signal), key=lambda e: e.path)
    if errors:
        msgs = "; ".join(f"{list(e.path)}: {e.message}" for e in errors[:5])
        raise SignalValidationError(f"Signal failed schema: {msgs}")
