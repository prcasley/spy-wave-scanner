"""Yahoo Finance options chain fetcher (v7 endpoint).

Returns the nearest expiration's full call/put chain. Per the project's hard
rules, this never returns mock data — Yahoo failure raises OptionsFeedError.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_YAHOO_OPTIONS_URL = "https://query2.finance.yahoo.com/v7/finance/options/{symbol}"
_YAHOO_OPTIONS_FALLBACK = "https://query1.finance.yahoo.com/v7/finance/options/{symbol}"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class OptionsFeedError(RuntimeError):
    """Raised when Yahoo refuses to return a usable options chain."""


@dataclass
class OptionContract:
    contract_symbol: str
    strike: float
    last_price: float
    bid: Optional[float]
    ask: Optional[float]
    volume: int
    open_interest: int
    implied_volatility: float  # decimal (0.18 == 18%)
    in_the_money: bool
    expiration: datetime
    contract_type: str  # "call" | "put"


@dataclass
class OptionsChain:
    ticker: str
    spot: float
    expirations_unix: list[int] = field(default_factory=list)
    selected_expiration: Optional[datetime] = None
    calls: list[OptionContract] = field(default_factory=list)
    puts: list[OptionContract] = field(default_factory=list)

    @property
    def dte(self) -> int:
        if not self.selected_expiration:
            return 0
        delta = self.selected_expiration - datetime.now(timezone.utc)
        return max(delta.days, 0)


class OptionsFeed:
    """Fetch a single-expiration options chain from Yahoo."""

    def __init__(self, rate_limit_rpm: int = 60) -> None:
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": _USER_AGENT,
                "Accept": "application/json,text/plain,*/*",
            }
        )

    def _request(self, ticker: str, expiration_unix: Optional[int]) -> dict:
        params = {"date": expiration_unix} if expiration_unix else {}
        last_err: Optional[Exception] = None
        for url_tmpl in (_YAHOO_OPTIONS_URL, _YAHOO_OPTIONS_FALLBACK):
            url = url_tmpl.format(symbol=ticker)
            try:
                resp = self._session.get(url, params=params, timeout=15)
                if resp.status_code == 200:
                    return resp.json()
                last_err = OptionsFeedError(
                    f"Yahoo HTTP {resp.status_code} for {ticker} options: "
                    f"{resp.text[:200]}"
                )
            except (requests.RequestException, ValueError) as exc:
                last_err = exc
        raise OptionsFeedError(
            f"Yahoo options fetch failed for {ticker}: {last_err}"
        )

    @staticmethod
    def _to_contract(raw: dict, expiration: datetime, contract_type: str) -> OptionContract:
        return OptionContract(
            contract_symbol=raw.get("contractSymbol", ""),
            strike=float(raw.get("strike", 0.0)),
            last_price=float(raw.get("lastPrice", 0.0) or 0.0),
            bid=float(raw["bid"]) if raw.get("bid") is not None else None,
            ask=float(raw["ask"]) if raw.get("ask") is not None else None,
            volume=int(raw.get("volume") or 0),
            open_interest=int(raw.get("openInterest") or 0),
            implied_volatility=float(raw.get("impliedVolatility") or 0.0),
            in_the_money=bool(raw.get("inTheMoney", False)),
            expiration=expiration,
            contract_type=contract_type,
        )

    def get_chain(
        self,
        ticker: str,
        target_dte: int = 7,
    ) -> OptionsChain:
        """Return the chain whose expiration is closest to *target_dte* days out.

        Yahoo's first call returns ``expirationDates``; we pick the closest
        match and re-fetch with that ``date`` parameter.
        """
        ticker = ticker.upper()
        first = self._request(ticker, None)
        chain_data = ((first.get("optionChain") or {}).get("result") or [])
        if not chain_data:
            err = ((first.get("optionChain") or {}).get("error"))
            raise OptionsFeedError(f"No option chain returned for {ticker}: {err}")
        head = chain_data[0]
        spot = float(
            ((head.get("quote") or {}).get("regularMarketPrice"))
            or ((head.get("quote") or {}).get("postMarketPrice"))
            or 0.0
        )
        expirations = [int(x) for x in (head.get("expirationDates") or [])]
        if not expirations:
            raise OptionsFeedError(f"No expirations available for {ticker}")

        now_unix = int(datetime.now(timezone.utc).timestamp())
        target_unix = now_unix + target_dte * 86400
        chosen = min(expirations, key=lambda e: abs(e - target_unix))
        chosen_dt = datetime.fromtimestamp(chosen, tz=timezone.utc)

        # Second fetch to lock onto the chosen expiration
        detail = self._request(ticker, chosen)
        result = ((detail.get("optionChain") or {}).get("result") or [])
        if not result:
            raise OptionsFeedError(f"No detail chain returned for {ticker} {chosen_dt}")
        options_block = (result[0].get("options") or [{}])[0]
        calls = [
            self._to_contract(c, chosen_dt, "call")
            for c in (options_block.get("calls") or [])
        ]
        puts = [
            self._to_contract(p, chosen_dt, "put")
            for p in (options_block.get("puts") or [])
        ]
        if not calls and not puts:
            raise OptionsFeedError(
                f"Empty chain for {ticker} at expiration {chosen_dt.isoformat()}"
            )

        return OptionsChain(
            ticker=ticker,
            spot=spot,
            expirations_unix=expirations,
            selected_expiration=chosen_dt,
            calls=calls,
            puts=puts,
        )
