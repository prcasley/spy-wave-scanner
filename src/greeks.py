"""Black-Scholes Greeks for filling in delta where Yahoo doesn't provide it.

Yahoo's options endpoint returns ``impliedVolatility`` but not delta.
We compute delta and a probability-of-profit estimate so the canonical signal
JSON can be assembled without re-fetching.
"""

from __future__ import annotations

import math
from typing import Literal

# Use scipy if available for the highest-precision norm CDF; fall back to
# math.erf for environments where scipy import is heavy or unavailable.
try:
    from scipy.stats import norm  # type: ignore[import-untyped]

    def _norm_cdf(x: float) -> float:
        return float(norm.cdf(x))
except ImportError:  # pragma: no cover
    def _norm_cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


OptionType = Literal["call", "put"]


def _d1(spot: float, strike: float, t: float, vol: float, r: float) -> float:
    if t <= 0 or vol <= 0 or spot <= 0 or strike <= 0:
        return 0.0
    return (math.log(spot / strike) + (r + 0.5 * vol * vol) * t) / (vol * math.sqrt(t))


def delta(
    spot: float,
    strike: float,
    days_to_expiry: int,
    iv: float,
    option_type: OptionType,
    risk_free_rate: float = 0.04,
) -> float:
    """Black-Scholes delta. Returns 0..1 for calls, -1..0 for puts."""
    t = max(days_to_expiry, 0) / 365.0
    if t <= 0 or iv <= 0:
        # At expiry: delta is 1.0 (ITM call) / -1.0 (ITM put) / 0 otherwise
        if option_type == "call":
            return 1.0 if spot > strike else 0.0
        return -1.0 if spot < strike else 0.0
    d1 = _d1(spot, strike, t, iv, risk_free_rate)
    if option_type == "call":
        return _norm_cdf(d1)
    return _norm_cdf(d1) - 1.0


def probability_itm(
    spot: float,
    strike: float,
    days_to_expiry: int,
    iv: float,
    option_type: OptionType,
    risk_free_rate: float = 0.04,
) -> float:
    """Risk-neutral probability the option finishes in the money."""
    t = max(days_to_expiry, 0) / 365.0
    if t <= 0 or iv <= 0:
        return 1.0 if (
            (option_type == "call" and spot > strike)
            or (option_type == "put" and spot < strike)
        ) else 0.0
    d1 = _d1(spot, strike, t, iv, risk_free_rate)
    d2 = d1 - iv * math.sqrt(t)
    if option_type == "call":
        return _norm_cdf(d2)
    return _norm_cdf(-d2)


def probability_above(
    spot: float, target: float, days_to_expiry: int, iv: float,
    risk_free_rate: float = 0.04,
) -> float:
    """Probability spot finishes above *target* — used for breakeven analysis."""
    return probability_itm(spot, target, days_to_expiry, iv, "call", risk_free_rate)
