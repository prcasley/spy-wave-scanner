"""Pick an options structure given wave direction, IV rank, and DTE.

The selector returns concrete contracts pulled from the live chain. No
synthetic legs — if the chain doesn't have the strike we want, we widen the
search; if nothing fits, we raise rather than fabricate.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal, Optional

from src.greeks import delta as bs_delta
from src.greeks import probability_above
from src.options_feed import OptionContract, OptionsChain

logger = logging.getLogger(__name__)

Direction = Literal["long", "short"]
Structure = Literal[
    "long_call",
    "bull_call_spread",
    "long_put",
    "bear_put_spread",
    "iron_condor",
]


class StrategySelectorError(RuntimeError):
    """Raised when no usable options structure can be assembled from the chain."""


@dataclass
class Leg:
    action: Literal["buy", "sell"]
    type: Literal["call", "put"]
    strike: float
    premium: float
    delta: float
    iv: float

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "type": self.type,
            "strike": round(self.strike, 2),
            "premium": round(self.premium, 2),
            "delta": round(self.delta, 4),
            "iv": round(self.iv, 4),
        }


@dataclass
class StrategyChoice:
    structure: Structure
    legs: list[Leg] = field(default_factory=list)
    max_loss: float = 0.0
    max_gain: float = 0.0
    breakeven: float = 0.0
    probability_of_profit: float = 0.0


def _atm_iv(chain: OptionsChain) -> float:
    """Mean IV of the two contracts closest to spot — used as IV-rank proxy."""
    contracts = [*chain.calls, *chain.puts]
    if not contracts or chain.spot <= 0:
        return 0.0
    contracts = sorted(contracts, key=lambda c: abs(c.strike - chain.spot))
    near = contracts[: min(4, len(contracts))]
    ivs = [c.implied_volatility for c in near if c.implied_volatility > 0]
    return sum(ivs) / len(ivs) if ivs else 0.0


def _mid_price(c: OptionContract) -> float:
    if c.bid is not None and c.ask is not None and c.ask > 0 and c.bid >= 0:
        return round((c.bid + c.ask) / 2.0, 2)
    return float(c.last_price or 0.0)


def _nearest(contracts: list[OptionContract], target_strike: float) -> Optional[OptionContract]:
    if not contracts:
        return None
    return min(contracts, key=lambda c: abs(c.strike - target_strike))


def _ensure_priced(c: Optional[OptionContract]) -> OptionContract:
    if c is None or _mid_price(c) <= 0:
        raise StrategySelectorError(
            "Required leg has no usable price on the chain"
        )
    return c


def _delta_of(c: OptionContract, spot: float, dte: int) -> float:
    return bs_delta(
        spot=spot,
        strike=c.strike,
        days_to_expiry=dte,
        iv=c.implied_volatility,
        option_type="call" if c.contract_type == "call" else "put",
    )


def _leg_from(c: OptionContract, action: Literal["buy", "sell"], spot: float, dte: int) -> Leg:
    return Leg(
        action=action,
        type="call" if c.contract_type == "call" else "put",
        strike=c.strike,
        premium=_mid_price(c),
        delta=_delta_of(c, spot, dte),
        iv=c.implied_volatility,
    )


def select_strategy(
    chain: OptionsChain,
    direction: Direction,
    invalidation_price: Optional[float] = None,
    target_price: Optional[float] = None,
    high_iv_threshold: float = 0.40,
) -> StrategyChoice:
    """Pick a structure and concrete legs from the chain.

    Heuristic:
      * Direction long, IV low  → long_call (cheap premium, full upside)
      * Direction long, IV high → bull_call_spread (cap premium bleed)
      * Direction short, IV low → long_put
      * Direction short, IV high → bear_put_spread
      * Neutral (no clear direction signal) → iron_condor — not used in this
        selector because the wave engine always produces a direction; left
        callable for future use.
    """
    if not chain.calls or not chain.puts:
        raise StrategySelectorError("Chain has no calls or no puts")
    spot = chain.spot
    dte = chain.dte
    iv = _atm_iv(chain)
    high_iv = iv >= high_iv_threshold

    if direction == "long":
        if high_iv:
            return _build_bull_call_spread(chain, spot, dte, target_price)
        return _build_long_call(chain, spot, dte, target_price)
    if high_iv:
        return _build_bear_put_spread(chain, spot, dte, target_price)
    return _build_long_put(chain, spot, dte, target_price)


# ----------------------------------------------------------------------------
# Builders
# ----------------------------------------------------------------------------

def _build_long_call(
    chain: OptionsChain, spot: float, dte: int, target: Optional[float]
) -> StrategyChoice:
    # Pick a strike ~1 step OTM (closest call above spot)
    above_spot = [c for c in chain.calls if c.strike >= spot]
    target_strike = above_spot[0].strike if above_spot else spot
    contract = _ensure_priced(_nearest(chain.calls, target_strike))
    leg = _leg_from(contract, "buy", spot, dte)
    premium = leg.premium
    breakeven = leg.strike + premium
    pop = probability_above(spot, breakeven, dte, contract.implied_volatility)
    return StrategyChoice(
        structure="long_call",
        legs=[leg],
        max_loss=round(premium * 100, 2),
        max_gain=float("inf") if not target else round(max(target - breakeven, 0) * 100, 2),
        breakeven=round(breakeven, 2),
        probability_of_profit=round(pop, 4),
    )


def _build_long_put(
    chain: OptionsChain, spot: float, dte: int, target: Optional[float]
) -> StrategyChoice:
    below_spot = [p for p in chain.puts if p.strike <= spot]
    target_strike = below_spot[-1].strike if below_spot else spot
    contract = _ensure_priced(_nearest(chain.puts, target_strike))
    leg = _leg_from(contract, "buy", spot, dte)
    premium = leg.premium
    breakeven = leg.strike - premium
    # Probability of finishing below breakeven
    pop = 1.0 - probability_above(spot, breakeven, dte, contract.implied_volatility)
    return StrategyChoice(
        structure="long_put",
        legs=[leg],
        max_loss=round(premium * 100, 2),
        max_gain=float("inf") if not target else round(max(breakeven - target, 0) * 100, 2),
        breakeven=round(breakeven, 2),
        probability_of_profit=round(pop, 4),
    )


def _build_bull_call_spread(
    chain: OptionsChain, spot: float, dte: int, target: Optional[float]
) -> StrategyChoice:
    # Long ATM call, short call ~one target away (or ~2% OTM)
    long_strike = _nearest(chain.calls, spot)
    short_target = target if target and target > spot else spot * 1.02
    short_candidates = [c for c in chain.calls if c.strike > (long_strike.strike if long_strike else spot)]
    short_strike = _nearest(short_candidates, short_target) or _nearest(chain.calls, short_target)
    long_c = _ensure_priced(long_strike)
    short_c = _ensure_priced(short_strike)
    long_leg = _leg_from(long_c, "buy", spot, dte)
    short_leg = _leg_from(short_c, "sell", spot, dte)
    net_debit = max(long_leg.premium - short_leg.premium, 0.01)
    width = short_leg.strike - long_leg.strike
    max_gain = max((width - net_debit) * 100, 0.0)
    breakeven = long_leg.strike + net_debit
    pop = probability_above(spot, breakeven, dte, long_c.implied_volatility)
    return StrategyChoice(
        structure="bull_call_spread",
        legs=[long_leg, short_leg],
        max_loss=round(net_debit * 100, 2),
        max_gain=round(max_gain, 2),
        breakeven=round(breakeven, 2),
        probability_of_profit=round(pop, 4),
    )


def _build_bear_put_spread(
    chain: OptionsChain, spot: float, dte: int, target: Optional[float]
) -> StrategyChoice:
    long_strike = _nearest(chain.puts, spot)
    short_target = target if target and target < spot else spot * 0.98
    short_candidates = [p for p in chain.puts if p.strike < (long_strike.strike if long_strike else spot)]
    short_strike = _nearest(short_candidates, short_target) or _nearest(chain.puts, short_target)
    long_p = _ensure_priced(long_strike)
    short_p = _ensure_priced(short_strike)
    long_leg = _leg_from(long_p, "buy", spot, dte)
    short_leg = _leg_from(short_p, "sell", spot, dte)
    net_debit = max(long_leg.premium - short_leg.premium, 0.01)
    width = long_leg.strike - short_leg.strike
    max_gain = max((width - net_debit) * 100, 0.0)
    breakeven = long_leg.strike - net_debit
    pop = 1.0 - probability_above(spot, breakeven, dte, long_p.implied_volatility)
    return StrategyChoice(
        structure="bear_put_spread",
        legs=[long_leg, short_leg],
        max_loss=round(net_debit * 100, 2),
        max_gain=round(max_gain, 2),
        breakeven=round(breakeven, 2),
        probability_of_profit=round(pop, 4),
    )
