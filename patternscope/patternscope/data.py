"""Price data: Yahoo Finance (yfinance) with a local CSV cache, or your own CSVs."""
from __future__ import annotations

import os
import time

import numpy as np
import pandas as pd

from .config import YF

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_cache")


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=lambda s: str(s).strip().lower().replace("adj close", "adj_close"))
    keep = [x for x in ["open", "high", "low", "close", "volume"] if x in df.columns]
    df = df[keep].apply(pd.to_numeric, errors="coerce").dropna(subset=["open", "high", "low", "close"])
    if "volume" not in df:
        df["volume"] = 0.0
    df = df[(df.high >= df.low) & (df.close > 0)]
    return df[~df.index.duplicated(keep="last")].sort_index()


CCXT_TF = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "1d": "1d"}
CCXT_DAYS = {"1m": 3, "5m": 60, "15m": 60, "1h": 729, "1d": 4000}


def load_ccxt(ticker: str, tf: str, exchange: str = "coinbase", days: int | None = None) -> pd.DataFrame:
    """Crypto candles straight from an exchange's public API via CCXT (no account or key).
    BTC-USD -> BTC/USD. Weekly bars are built from daily. Use a US-reachable exchange
    (coinbase, kraken) — Binance blocks US IPs, including GitHub's runners."""
    import ccxt  # lazily: only needed for crypto

    ex = getattr(ccxt, exchange)({"enableRateLimit": True})
    sym = ticker.upper().replace("-", "/")
    base_tf = "1d" if tf == "1wk" else tf
    tfx = CCXT_TF[base_tf]
    step_ms = ex.parse_timeframe(tfx) * 1000
    since = ex.milliseconds() - (days or CCXT_DAYS.get(base_tf, 730)) * 86_400_000
    rows, guard = [], 0
    while since < ex.milliseconds() and guard < 400:
        batch = ex.fetch_ohlcv(sym, tfx, since=since, limit=300)
        guard += 1
        if not batch:
            since += 300 * step_ms  # gap (e.g. before listing) — skip ahead
            continue
        rows += batch
        nxt = batch[-1][0] + step_ms
        if nxt <= since:
            break
        since = nxt
    if not rows:
        raise RuntimeError(f"CCXT {exchange} returned no candles for {sym} {tfx}")
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"]).drop_duplicates("ts")
    df.index = pd.DatetimeIndex(pd.to_datetime(df.pop("ts"), unit="ms", utc=True)).tz_convert("America/New_York")
    df = _clean(df)
    if tf == "1wk":
        df = df.resample("W-SUN", label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    return df


def load_prices(ticker: str, tf: str, refresh: bool = False) -> pd.DataFrame:
    """Crypto -> CCXT (exchange data, fresher) with Yahoo as fallback; everything else -> Yahoo."""
    from .config import CRYPTO_SOURCE, is_crypto
    if is_crypto(ticker) and CRYPTO_SOURCE.startswith("ccxt"):
        os.makedirs(CACHE_DIR, exist_ok=True)
        path = os.path.join(CACHE_DIR, f"{ticker}_{tf}_ccxt.csv")
        if not refresh and os.path.exists(path) and (time.time() - os.path.getmtime(path)) < 3600:
            return load_csv(path)
        try:
            df = load_ccxt(ticker, tf, exchange=CRYPTO_SOURCE.split(":", 1)[1] if ":" in CRYPTO_SOURCE else "coinbase")
            df.to_csv(path)
            return df
        except Exception as e:
            print(f"  CCXT failed for {ticker} {tf} ({e}); falling back to Yahoo")
    return load_yahoo(ticker, tf, refresh=refresh)


def load_yahoo(ticker: str, tf: str, refresh: bool = False, max_age_hours: float = 6) -> pd.DataFrame:
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{ticker.replace('^', '_')}_{tf}.csv")
    if not refresh and os.path.exists(path) and (time.time() - os.path.getmtime(path)) < max_age_hours * 3600:
        return load_csv(path)
    import yfinance as yf  # imported lazily so offline/CSV use doesn't need it

    spec = YF[tf]
    last_err = None
    for attempt in range(3):
        try:
            df = yf.download(ticker, interval=spec["interval"], period=spec["period"], auto_adjust=True,
                             progress=False, prepost=False, threads=False)
            if df is not None and len(df):
                df = _clean(df)
                if tf in ("1h", "5m", "15m") and df.index.tz is not None:
                    df.index = df.index.tz_convert("America/New_York")
                df.to_csv(path)
                return df
        except Exception as e:  # network hiccups / rate limits
            last_err = e
        time.sleep(2 * (attempt + 1))
    if os.path.exists(path):  # fall back to stale cache rather than nothing
        return load_csv(path)
    raise RuntimeError(f"No data for {ticker} {tf}: {last_err}")


def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0)
    df.index = pd.to_datetime(df.index, utc=True, errors="coerce")
    df = df[df.index.notna()]
    try:
        df.index = df.index.tz_convert("America/New_York")
    except Exception:
        pass
    return _clean(df)


def synthetic(tf: str, bars: int = 3000, seed: int = 7) -> pd.DataFrame:
    """Demo prices (regime-switching random walk). For testing the plumbing only."""
    rng = np.random.default_rng(seed)
    drift = np.repeat(rng.normal(0.0004, 0.002, bars // 60 + 1), 60)[:bars]
    vol = np.repeat(rng.uniform(0.006, 0.02, bars // 40 + 1), 40)[:bars]
    r = rng.normal(drift, vol)
    close = 100 * np.exp(np.cumsum(r))
    open_ = np.r_[100, close[:-1]] * np.exp(rng.normal(0, vol * 0.3))
    hi = np.maximum(open_, close) * np.exp(np.abs(rng.normal(0, vol * 0.6)))
    lo = np.minimum(open_, close) * np.exp(-np.abs(rng.normal(0, vol * 0.6)))
    if tf == "1h":
        days = pd.bdate_range("2024-11-01", periods=bars // 7 + 1, tz="America/New_York")
        idx = [d + pd.Timedelta(hours=9, minutes=30) + pd.Timedelta(hours=k) for d in days for k in range(7)][:bars]
    elif tf == "1wk":
        idx = pd.date_range(end="2026-10-16", periods=bars, freq="W-FRI", tz="America/New_York")
    else:
        idx = pd.bdate_range(end="2026-10-16", periods=bars, tz="America/New_York")
    vol_ = rng.integers(1_000_000, 5_000_000, bars).astype(float)
    return pd.DataFrame({"open": open_, "high": hi, "low": lo, "close": close, "volume": vol_},
                        index=pd.DatetimeIndex(idx))


def load_dividends(ticker: str, days: int = 120) -> dict:
    """Recent cash distributions (weekly/monthly payers) from Yahoo. Empty dict if none/unavailable."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        d = t.dividends
        info = {}
        try:
            info = t.get_info() or {}
        except Exception:
            pass
        name = info.get("longName") or info.get("shortName") or ""
        if d is None or not len(d):
            return {"name": name} if name else {}
        d = d[d.index >= d.index.max() - pd.Timedelta(days=days)]
        rows = [dict(date=str(i)[:10], amount=round(float(v), 4)) for i, v in d.items()][::-1]
        gaps = pd.Series(d.index).diff().dt.days.dropna()
        med = gaps.median() if len(gaps) else 999
        freq = "weekly" if med <= 8 else "monthly" if med <= 35 else "quarterly" if med <= 100 else "other"
        return dict(name=name, last_date=rows[0]["date"], last_amount=rows[0]["amount"], frequency=freq,
                    recent=rows[:8], trailing_sum=round(float(d.sum()), 4))
    except Exception as e:  # never let dividends break the scan
        return {"error": str(e)[:120]}
