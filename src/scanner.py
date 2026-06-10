"""Multi-ticker Wave Options Scanner orchestrator.

`scan_universe(...)` is the single entry point used by the CLI, the FastAPI
worker, and the APScheduler loop. It consumes the existing wave-detection
modules unchanged and emits canonical signal JSON.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Iterable, Optional

from src.data_feed import DataFeed, DataFeedError
from src.discord_webhook import DiscordWebhook
from src.divergence import DivergenceDetector
from src.fib_mapper import FibMapper
from src.models import WaveDirection, WaveLabel
from src.options_feed import OptionsFeed, OptionsFeedError
from src.persistence import SignalStore
from src.pivot_detector import PivotDetector
from src.signal_builder import build_signal
from src.strategy_selector import StrategySelectorError, select_strategy
from src.wave_counter import WaveCounter

logger = logging.getLogger(__name__)


def _env_tickers(default: str = "SPY,QQQ,IWM,DIA") -> list[str]:
    raw = os.environ.get("SCAN_TICKERS", default)
    return [t.strip().upper() for t in raw.split(",") if t.strip()]


def _direction_label(wave_count) -> str:
    return "long" if wave_count.direction == WaveDirection.UP else "short"


def _trade_plan(wave_count) -> tuple[str, Optional[float]]:
    """Return (trade_direction, stop_price) for the count.

    A *completed* ABC correction is traded as a reversal: short the end of an
    up-correction / buy the end of a down-correction, with the stop beyond the
    C-wave extreme. Everything else trades with the wave direction and uses
    the count's own invalidation level.
    """
    if wave_count.pattern_type == "corrective" and wave_count.is_complete:
        c_end = wave_count.waves[-1].end.price
        if wave_count.direction == WaveDirection.UP:
            return "short", c_end
        return "long", c_end
    return _direction_label(wave_count), wave_count.invalidation_price


def _scan_single(
    ticker: str,
    *,
    feed: DataFeed,
    options_feed: OptionsFeed,
    timeframe: str,
    lookback_days: int,
    sensitivity: int,
    min_swing_pct: float,
    target_dte: int,
    use_cache: bool,
) -> Optional[dict]:
    """Run the full pipeline for one ticker. Returns a signal dict or None."""
    df = feed.get_bars(
        timeframe=timeframe,
        lookback_days=lookback_days,
        use_cache=use_cache,
        ticker=ticker,
    )
    df = feed.compute_indicators(df)
    if df.empty or len(df) < 30:
        logger.warning("%s: too few bars (%d) — skipping", ticker, len(df))
        return None

    detector = PivotDetector(sensitivity=sensitivity)
    pivots = detector.find_pivots(df)
    pivots = detector.filter_significant_pivots(pivots, min_swing_pct=min_swing_pct)

    wc = WaveCounter()
    wave_count = wc.count_impulse_best(pivots, direction=WaveDirection.DOWN)
    if wave_count is None:
        wave_count = wc.count_impulse_best(pivots, direction=WaveDirection.UP)
    if wave_count is None:
        # Pick corrective direction from sequence classification
        wave_count = wc.count_corrective(pivots, direction=WaveDirection.UP)
    if wave_count is None:
        logger.info("%s: no clear wave count — skipping", ticker)
        return None

    fm = FibMapper()
    fib_levels: list = []
    confluence_zones: list = []
    w1 = wave_count.wave_by_label(WaveLabel.W1) or wave_count.waves[0]
    fib_levels = fm.calculate_retracements(
        swing_high=max(w1.start.price, w1.end.price),
        swing_low=min(w1.start.price, w1.end.price),
        direction="down" if wave_count.direction == WaveDirection.DOWN else "up",
    )
    w2 = wave_count.wave_by_label(WaveLabel.W2)
    if w2:
        fib_levels.extend(
            fm.calculate_extensions(w1.start.price, w1.end.price, w2.end.price)
        )
        confluence_zones = fm.find_fib_confluence([fib_levels])

    div_det = DivergenceDetector()
    divergences = div_det.detect_rsi_divergence(df, pivots)
    divergences += div_det.detect_macd_divergence(df, pivots)

    direction, stop_price = _trade_plan(wave_count)
    # Keep the count's invalidation consistent with the tradeable stop so the
    # signal JSON, options strategy, and app all show the same level.
    if stop_price is not None:
        wave_count.invalidation_price = stop_price

    projection = wc.project_targets(wave_count)
    spot = float(df["close"].iloc[-1])

    chain = options_feed.get_chain(ticker, target_dte=target_dte)
    target_price = projection.primary_target if projection else None

    strategy = select_strategy(
        chain=chain,
        direction=direction,  # type: ignore[arg-type]
        invalidation_price=wave_count.invalidation_price,
        target_price=target_price,
    )

    signal = build_signal(
        ticker=ticker,
        spot=spot,
        wave_count=wave_count,
        projection=projection,
        divergences=divergences,
        confluence_zones=confluence_zones,
        chain=chain,
        strategy=strategy,
        direction=direction,
    )
    return signal


def scan_universe(
    tickers: Optional[Iterable[str]] = None,
    *,
    timeframe: str = "1h",
    lookback_days: int = 60,
    sensitivity: int = 5,
    min_swing_pct: float = 0.5,
    target_dte: int = 7,
    use_cache: bool = False,
    persist: bool = True,
    post_to_discord: bool = True,
    store: Optional[SignalStore] = None,
    feed: Optional[DataFeed] = None,
    options_feed: Optional[OptionsFeed] = None,
) -> list[dict]:
    """Scan every ticker in *tickers* and return the list of signals built.

    On per-ticker failures we log and continue — one bad symbol doesn't kill
    the whole scan. Per the project rules, data-fetch errors raise *up to*
    the caller via DataFeedError if every host fails for that ticker; the
    multi-ticker loop catches it so we still emit signals for the others.
    """
    syms = list(tickers) if tickers else _env_tickers()
    feed = feed or DataFeed()
    options_feed = options_feed or OptionsFeed()
    store = store or SignalStore() if persist else None
    discord = DiscordWebhook() if post_to_discord else None

    out: list[dict] = []
    for ticker in syms:
        try:
            signal = _scan_single(
                ticker,
                feed=feed,
                options_feed=options_feed,
                timeframe=timeframe,
                lookback_days=lookback_days,
                sensitivity=sensitivity,
                min_swing_pct=min_swing_pct,
                target_dte=target_dte,
                use_cache=use_cache,
            )
        except DataFeedError as exc:
            logger.error("%s: data fetch failed — %s", ticker, exc)
            continue
        except OptionsFeedError as exc:
            logger.error("%s: options chain unavailable — %s", ticker, exc)
            continue
        except StrategySelectorError as exc:
            logger.error("%s: strategy build failed — %s", ticker, exc)
            continue
        except Exception:  # pragma: no cover -- belt & braces; logs full trace
            logger.exception("%s: unexpected error during scan", ticker)
            continue

        if signal is None:
            continue
        if store is not None:
            store.append(signal)
        if discord is not None:
            discord.post(signal)
        out.append(signal)

    logger.info(
        "Scanned %d tickers, produced %d signals at %s",
        len(syms), len(out), datetime.now(timezone.utc).isoformat(),
    )
    return out
