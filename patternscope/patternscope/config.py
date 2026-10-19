"""Tunable settings. Edit freely."""

WATCHLIST = ["SPY", "QQQ", "NVDA", "TSLA", "MU", "GOOGL", "NBIS", "DELL", "BE", "CLSK", "TSLW"]

# Per timeframe:
#   k              bars each side that define a swing pivot (bigger = fewer, larger swings)
#   min_swing_atr  ignore swings smaller than this many ATRs
#   wait           bars allowed between a pattern completing and its breakout
#   max_hold       time stop for the trade outcome (bars)
#   horizons       forward-return checkpoints (bars) for the "tendency" stats
#   fresh          a signal counts as "live now" if it confirmed in the last N bars
TIMEFRAMES = {
    # day-trading lens: ~2 trading days of hold, horizons 1h / 3h / 1 day / 2 days
    "1h": dict(k=4, min_swing_atr=1.5, wait=20, max_hold=14, horizons=[1, 3, 7, 14], fresh=3),
    # swing lens: hold up to a month, horizons 1d / 1w / 2w / 1m
    "1d": dict(k=3, min_swing_atr=1.25, wait=15, max_hold=20, horizons=[1, 5, 10, 20], fresh=2),
    # buy-and-hold lens: hold up to 6 months, horizons 1w / 1m / 1q / 6m
    "1wk": dict(k=2, min_swing_atr=1.0, wait=10, max_hold=26, horizons=[1, 4, 13, 26], fresh=1),
}

# Yahoo Finance limits: 1h history is ~730 days; 1d / 1wk go back to listing.
YF = {
    "5m": dict(interval="5m", period="60d"),
    "15m": dict(interval="15m", period="60d"),
    "1h": dict(interval="60m", period="729d"),
    "1d": dict(interval="1d", period="max"),
    "1wk": dict(interval="1wk", period="max"),
}

# ---- validation settings
# Round-trip trading cost per side in basis points (commission + slippage). 3 bps = 0.03%.
COST_BPS = {"1h": 5, "1d": 3, "1wk": 3}
# Out-of-sample split: grade on signals before this date, test on signals after it.
OOS_SPLIT = {"1h": "2025-05-01", "1d": "2019-01-01", "1wk": "2016-01-01"}
