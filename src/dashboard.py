"""Module 7: Dashboard — Streamlit real-time wave scanner UI.

Visual style modelled after a professional trading-platform dark chart:
  * Black background with subtle grid
  * Candlestick chart with coloured wave labels (1–5 / A-B-C)
  * Horizontal Fibonacci lines with price + ratio annotations
  * Wave connector lines between pivots
  * RSI and MACD sub-panels
  * Live price badge on the right axis
  * Alert history log in a sidebar table
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from src.models import (
    Alert,
    ConfluenceZone,
    Divergence,
    DivergenceType,
    FibLevel,
    Pivot,
    PivotType,
    WaveCount,
    WaveDirection,
    WaveLabel,
    WaveProjection,
)

# ── Colour palette (matches the dark trading-platform screenshot) ──────────
BG_COLOR = "#0e0e0e"
GRID_COLOR = "#1a1a1a"
CANDLE_UP = "#26a69a"       # green
CANDLE_DOWN = "#ef5350"     # red
FIB_LINE_COLOR = "#b8860b"  # dark-gold for retracement lines
FIB_EXT_COLOR = "#ff6347"   # tomato-red dashed for extensions
WAVE_UP_COLOR = "#00e676"   # bright green connector
WAVE_DOWN_COLOR = "#ff1744" # bright red connector
WAVE_LABEL_COLORS = {
    "1": "#ffeb3b",  # yellow
    "2": "#ffeb3b",
    "3": "#f44336",  # red
    "4": "#00e676",  # green
    "5": "#2196f3",  # blue
    "A": "#ff9800",  # orange
    "B": "#ff9800",
    "C": "#ff9800",
}
RSI_COLOR = "#fdd835"
MACD_LINE_COLOR = "#42a5f5"
MACD_SIGNAL_COLOR = "#ef5350"
MACD_HIST_POS = "#26a69a"
MACD_HIST_NEG = "#ef5350"
TEXT_COLOR = "#e0e0e0"
PRICE_BADGE_UP = "#26a69a"
PRICE_BADGE_DN = "#ef5350"


# ═══════════════════════════════════════════════════════════════════════════
# Chart builder
# ═══════════════════════════════════════════════════════════════════════════

def build_chart(
    df: pd.DataFrame,
    wave_count: Optional[WaveCount] = None,
    fib_levels: Optional[list[FibLevel]] = None,
    confluence_zones: Optional[list[ConfluenceZone]] = None,
    divergences: Optional[list[Divergence]] = None,
    projection: Optional[WaveProjection] = None,
    ticker: str = "SPY",
) -> go.Figure:
    """Build the full multi-panel Plotly figure."""

    has_rsi = "rsi_14" in df.columns
    has_macd = "macd" in df.columns

    row_heights = [0.6]
    rows = 1
    if has_rsi:
        row_heights.append(0.2)
        rows += 1
    if has_macd:
        row_heights.append(0.2)
        rows += 1

    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
    )

    x_vals = df.index

    # ── 1. Candlestick ─────────────────────────────────────────────────
    fig.add_trace(
        go.Candlestick(
            x=x_vals,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            increasing_line_color=CANDLE_UP,
            increasing_fillcolor=CANDLE_UP,
            decreasing_line_color=CANDLE_DOWN,
            decreasing_fillcolor=CANDLE_DOWN,
            name="Price",
            showlegend=False,
        ),
        row=1, col=1,
    )

    # ── 2. Fibonacci lines ─────────────────────────────────────────────
    if fib_levels:
        for lv in fib_levels:
            is_ext = "extension" in lv.label
            color = FIB_EXT_COLOR if is_ext else FIB_LINE_COLOR
            dash = "dash" if is_ext else "solid"
            fig.add_hline(
                y=lv.price,
                line_color=color,
                line_dash=dash,
                line_width=1,
                opacity=0.7,
                annotation_text=f"{lv.price:.2f}({lv.label.replace(' retracement','').replace(' extension','')})",
                annotation_position="left",
                annotation_font_size=10,
                annotation_font_color=color,
                row=1, col=1,
            )

    # ── 3. Confluence zones (shaded bands) ─────────────────────────────
    if confluence_zones:
        for zone in confluence_zones:
            lo, hi = zone.price_range
            fig.add_hrect(
                y0=lo, y1=hi,
                fillcolor="rgba(255,215,0,0.08)",
                line_width=0,
                row=1, col=1,
            )

    # ── 4. Wave labels + connector lines ───────────────────────────────
    if wave_count and wave_count.waves:
        # Connector polyline through all wave pivots
        pts_x = [wave_count.waves[0].start.timestamp]
        pts_y = [wave_count.waves[0].start.price]
        for w in wave_count.waves:
            pts_x.append(w.end.timestamp)
            pts_y.append(w.end.price)

        connector_color = (
            WAVE_DOWN_COLOR
            if wave_count.direction == WaveDirection.DOWN
            else WAVE_UP_COLOR
        )
        fig.add_trace(
            go.Scatter(
                x=pts_x,
                y=pts_y,
                mode="lines",
                line=dict(color=connector_color, width=2),
                showlegend=False,
                hoverinfo="skip",
            ),
            row=1, col=1,
        )

        # Wave number annotations
        # Label the START of wave 1 as origin, then each wave END
        for w in wave_count.waves:
            label_text = w.label.value
            color = WAVE_LABEL_COLORS.get(label_text, "#ffffff")
            # Place label at wave end
            y_offset = 1.5 if w.end.type == PivotType.LOW else -1.5
            fig.add_annotation(
                x=w.end.timestamp,
                y=w.end.price + y_offset,
                text=f"<b>{label_text}</b>",
                showarrow=False,
                font=dict(size=18, color=color, family="Arial Black"),
                row=1, col=1,
            )
            # Large price label next to wave end
            fig.add_annotation(
                x=w.end.timestamp,
                y=w.end.price + (y_offset * 2.2),
                text=f"<b>{w.end.price:.0f}</b>",
                showarrow=False,
                font=dict(size=24, color=color, family="Arial Black"),
                row=1, col=1,
            )

    # ── 5. Current price badge ─────────────────────────────────────────
    if not df.empty:
        last_close = df["close"].iloc[-1]
        prev_close = df["close"].iloc[-2] if len(df) > 1 else last_close
        badge_color = PRICE_BADGE_UP if last_close >= prev_close else PRICE_BADGE_DN
        fig.add_annotation(
            x=x_vals[-1],
            y=last_close,
            text=f"  ${last_close:.2f}",
            showarrow=True,
            arrowhead=0,
            ax=60, ay=0,
            font=dict(size=12, color="white", family="monospace"),
            bgcolor=badge_color,
            borderpad=4,
            row=1, col=1,
        )

    # ── 6. Projection target arrow ─────────────────────────────────────
    if projection and not df.empty:
        fig.add_annotation(
            x=x_vals[-1],
            y=projection.primary_target,
            text=f"  Target ${projection.primary_target:.2f}",
            showarrow=True,
            arrowhead=2,
            arrowcolor="#fdd835",
            ax=80, ay=0,
            font=dict(size=11, color="#fdd835", family="monospace"),
            bordercolor="#fdd835",
            borderwidth=1,
            borderpad=3,
            bgcolor="rgba(0,0,0,0.6)",
            row=1, col=1,
        )

    # ── 7. RSI panel ───────────────────────────────────────────────────
    current_row = 2
    if has_rsi:
        for col_name, dash_style in [("rsi_14", "solid"), ("rsi_7", "dot")]:
            if col_name in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=x_vals,
                        y=df[col_name],
                        mode="lines",
                        line=dict(color=RSI_COLOR, width=1.5, dash=dash_style),
                        name=col_name.upper().replace("_", "(") + ")",
                        showlegend=False,
                    ),
                    row=current_row, col=1,
                )
        # Overbought / oversold lines
        for level in [30, 70]:
            fig.add_hline(
                y=level, line_dash="dot", line_color="#555555",
                line_width=1, row=current_row, col=1,
            )
        fig.update_yaxes(title_text="RSI", row=current_row, col=1)
        current_row += 1

    # ── 8. MACD panel ──────────────────────────────────────────────────
    if has_macd:
        fig.add_trace(
            go.Scatter(
                x=x_vals, y=df["macd"], mode="lines",
                line=dict(color=MACD_LINE_COLOR, width=1.5),
                name="MACD", showlegend=False,
            ),
            row=current_row, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=x_vals, y=df["macd_signal"], mode="lines",
                line=dict(color=MACD_SIGNAL_COLOR, width=1.5),
                name="Signal", showlegend=False,
            ),
            row=current_row, col=1,
        )
        if "macd_histogram" in df.columns:
            hist = df["macd_histogram"]
            colors = [MACD_HIST_POS if v >= 0 else MACD_HIST_NEG for v in hist]
            fig.add_trace(
                go.Bar(
                    x=x_vals, y=hist,
                    marker_color=colors,
                    name="Histogram", showlegend=False,
                ),
                row=current_row, col=1,
            )
        fig.update_yaxes(title_text="MACD", row=current_row, col=1)

    # ── 9. Divergence markers ──────────────────────────────────────────
    if divergences:
        for div in divergences:
            symbol = "triangle-down" if div.type == DivergenceType.BEARISH else "triangle-up"
            color = "#ef5350" if div.type == DivergenceType.BEARISH else "#26a69a"
            fig.add_trace(
                go.Scatter(
                    x=[div.price_pivot_2.timestamp],
                    y=[div.price_pivot_2.price],
                    mode="markers",
                    marker=dict(symbol=symbol, size=14, color=color, line_width=1, line_color="white"),
                    name=f"{div.type.value} div",
                    showlegend=False,
                    hovertext=f"{div.type.value} divergence ({div.indicator})",
                ),
                row=1, col=1,
            )

    # ── 10. Global layout (dark theme) ─────────────────────────────────
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=BG_COLOR,
        plot_bgcolor=BG_COLOR,
        font=dict(family="monospace", color=TEXT_COLOR, size=12),
        title=dict(
            text=f"<b>{ticker}</b> Elliott Wave Scanner",
            font=dict(size=18, color=TEXT_COLOR),
            x=0.5,
        ),
        xaxis_rangeslider_visible=False,
        margin=dict(l=60, r=80, t=50, b=30),
        height=900,
    )

    # Grid styling for all axes
    for i in range(1, rows + 1):
        fig.update_xaxes(
            gridcolor=GRID_COLOR, zeroline=False, row=i, col=1,
        )
        fig.update_yaxes(
            gridcolor=GRID_COLOR, zeroline=False, side="right", row=i, col=1,
        )

    return fig


# ═══════════════════════════════════════════════════════════════════════════
# Streamlit app
# ═══════════════════════════════════════════════════════════════════════════

def run_dashboard() -> None:
    """Launch the Streamlit dashboard."""

    st.set_page_config(
        page_title="SPY Wave Scanner",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Dark theme CSS overrides
    st.markdown(
        """
        <style>
        /* Main background */
        .stApp, [data-testid="stAppViewContainer"] {
            background-color: #0e0e0e;
            color: #e0e0e0;
        }
        /* Sidebar */
        [data-testid="stSidebar"] {
            background-color: #141414;
        }
        /* Headers */
        h1, h2, h3, h4, h5, h6, .stMarkdown {
            color: #e0e0e0 !important;
        }
        /* Metric cards */
        [data-testid="stMetric"] {
            background-color: #1a1a1a;
            border: 1px solid #2a2a2a;
            border-radius: 8px;
            padding: 12px;
        }
        [data-testid="stMetricValue"] {
            color: #fdd835 !important;
            font-family: monospace;
        }
        /* Alert boxes */
        .alert-high { background-color: #3d0000; border-left: 4px solid #ef5350; padding: 10px; margin: 4px 0; border-radius: 4px; }
        .alert-medium { background-color: #3d3000; border-left: 4px solid #fdd835; padding: 10px; margin: 4px 0; border-radius: 4px; }
        .alert-low { background-color: #1a1a2e; border-left: 4px solid #42a5f5; padding: 10px; margin: 4px 0; border-radius: 4px; }
        /* Bid/Ask bar */
        .bid-ask-bar {
            display: flex; justify-content: space-between; align-items: center;
            padding: 8px 16px; border-radius: 6px; margin-top: 4px;
            font-family: monospace; font-size: 16px; font-weight: bold;
        }
        .bid-side { background-color: #1b5e20; color: #a5d6a7; flex: 1; text-align: center; padding: 6px; border-radius: 4px 0 0 4px; }
        .ask-side { background-color: #b71c1c; color: #ef9a9a; flex: 1; text-align: center; padding: 6px; border-radius: 0 4px 4px 0; }
        .price-mid { background-color: #1a1a1a; color: #fdd835; padding: 6px 16px; font-size: 18px; }
        /* Table overrides */
        .stDataFrame { font-family: monospace; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── Sidebar controls ───────────────────────────────────────────────
    with st.sidebar:
        st.title("Wave Scanner")
        ticker = st.text_input("Ticker", value="SPY")
        timeframe = st.selectbox("Timeframe", ["5min", "15min", "1h", "1day"], index=0)
        lookback = st.slider("Lookback (days)", 1, 30, 5)
        sensitivity = st.slider("Pivot sensitivity", 3, 10, 5)
        min_swing = st.slider("Min swing %", 0.1, 1.0, 0.3, 0.05)
        st.divider()
        auto_refresh = st.checkbox("Auto-refresh (30s)", value=False)
        run_btn = st.button("Scan Now", type="primary", use_container_width=True)

    # ── Main area ──────────────────────────────────────────────────────
    # Header row with live metrics
    header_cols = st.columns([2, 1, 1, 1, 1, 1])
    with header_cols[0]:
        st.markdown(f"### {ticker} Elliott Wave Scanner")

    if not run_btn and not auto_refresh:
        st.info("Configure settings in the sidebar and click **Scan Now** to start.")
        _show_demo_chart(ticker)
        return

    # When the user clicks Scan or auto-refresh is on, run the pipeline
    _run_scan_pipeline(
        ticker=ticker,
        timeframe=timeframe,
        lookback_days=lookback,
        sensitivity=sensitivity,
        min_swing_pct=min_swing,
    )


def _run_scan_pipeline(
    ticker: str,
    timeframe: str,
    lookback_days: int,
    sensitivity: int,
    min_swing_pct: float,
) -> None:
    """Execute the full scan pipeline and render results."""
    from src.data_feed import DataFeed
    from src.pivot_detector import PivotDetector
    from src.fib_mapper import FibMapper
    from src.wave_counter import WaveCounter
    from src.divergence import DivergenceDetector

    api_key = os.environ.get("POLYGON_API_KEY", "")
    if not api_key:
        st.error("Set the **POLYGON_API_KEY** environment variable to fetch live data.")
        _show_demo_chart(ticker)
        return

    with st.spinner("Fetching data..."):
        feed = DataFeed(api_key=api_key, ticker=ticker)
        df = feed.get_bars(timeframe=timeframe, lookback_days=lookback_days)
        if df.empty:
            st.warning("No data returned from Polygon.io")
            return
        df = feed.compute_indicators(df)

    with st.spinner("Detecting pivots & waves..."):
        pd_det = PivotDetector(sensitivity=sensitivity)
        pivots = pd_det.find_pivots(df)
        pivots = pd_det.filter_significant_pivots(pivots, min_swing_pct=min_swing_pct)
        seq = pd_det.classify_pivot_sequence(pivots)

        wc = WaveCounter()
        wave_count = wc.count_impulse_best(pivots, direction=WaveDirection.DOWN)
        if wave_count is None:
            wave_count = wc.count_impulse_best(pivots, direction=WaveDirection.UP)
        if wave_count is None:
            wave_count = wc.count_corrective(pivots)

        fib_levels: list[FibLevel] = []
        confluence_zones: list[ConfluenceZone] = []
        projection = None

        fm = FibMapper()
        if wave_count and wave_count.waves:
            w1 = wave_count.wave_by_label(WaveLabel.W1)
            if w1:
                fib_levels = fm.calculate_retracements(
                    swing_high=max(w1.start.price, w1.end.price),
                    swing_low=min(w1.start.price, w1.end.price),
                    direction="down" if wave_count.direction == WaveDirection.DOWN else "up",
                )
            w2 = wave_count.wave_by_label(WaveLabel.W2)
            if w1 and w2:
                ext_levels = fm.calculate_extensions(w1.start.price, w1.end.price, w2.end.price)
                fib_levels.extend(ext_levels)
                confluence_zones = fm.find_fib_confluence([fib_levels])

            projection = wc.project_targets(wave_count)

        div_det = DivergenceDetector()
        divergences = div_det.detect_rsi_divergence(df, pivots)
        divergences += div_det.detect_macd_divergence(df, pivots)

    # ── Metrics row ────────────────────────────────────────────────────
    last_close = df["close"].iloc[-1]
    prev_close = df["close"].iloc[-2] if len(df) > 1 else last_close
    change = last_close - prev_close
    change_pct = change / prev_close * 100

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Price", f"${last_close:.2f}", f"{change:+.2f} ({change_pct:+.2f}%)")
    if wave_count:
        m2.metric("Wave", wave_count.current_wave_label.value if wave_count.current_wave_label else "—")
        m3.metric("Confidence", f"{wave_count.confidence:.0%}")
        m4.metric("Direction", wave_count.direction.value.upper())
        if wave_count.invalidation_price:
            m5.metric("Invalidation", f"${wave_count.invalidation_price:.2f}")

    # ── Bid / Ask bar ──────────────────────────────────────────────────
    bid_price = last_close - 0.01
    ask_price = last_close + 0.01
    st.markdown(
        f"""
        <div class="bid-ask-bar">
            <div class="bid-side">Bid &nbsp; ${bid_price:.2f}</div>
            <div class="price-mid">${last_close:.2f}</div>
            <div class="ask-side">${ask_price:.2f} &nbsp; Ask</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Chart ──────────────────────────────────────────────────────────
    fig = build_chart(
        df=df,
        wave_count=wave_count,
        fib_levels=fib_levels,
        confluence_zones=confluence_zones,
        divergences=divergences,
        projection=projection,
        ticker=ticker,
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── RSI / MACD text readout (matches screenshot bottom bar) ────────
    rsi14 = df["rsi_14"].iloc[-1] if "rsi_14" in df.columns else None
    rsi7 = df["rsi_7"].iloc[-1] if "rsi_7" in df.columns else None
    macd_val = df["macd"].iloc[-1] if "macd" in df.columns else None
    sig_val = df["macd_signal"].iloc[-1] if "macd_signal" in df.columns else None
    hist_val = df["macd_histogram"].iloc[-1] if "macd_histogram" in df.columns else None

    indicator_parts = []
    if rsi14 is not None:
        indicator_parts.append(f"RSI(14): {rsi14:.2f}")
    if rsi7 is not None:
        indicator_parts.append(f"RSI(7): {rsi7:.2f}")
    if macd_val is not None:
        indicator_parts.append(f"MACD: {macd_val:.2f}")
    if sig_val is not None:
        indicator_parts.append(f"Signal: {sig_val:.2f}")
    if hist_val is not None:
        indicator_parts.append(f"Hist: {hist_val:.2f}")
    if indicator_parts:
        st.caption(" | ".join(indicator_parts))

    # ── Fib levels table ───────────────────────────────────────────────
    if fib_levels:
        with st.expander("Fibonacci Levels", expanded=False):
            fib_df = pd.DataFrame([
                {"Level": lv.label, "Price": f"${lv.price:.2f}", "Source": lv.source}
                for lv in sorted(fib_levels, key=lambda l: l.price, reverse=True)
            ])
            st.dataframe(fib_df, use_container_width=True, hide_index=True)

    # ── Projection ─────────────────────────────────────────────────────
    if projection:
        st.subheader("Wave Projection")
        pc1, pc2, pc3 = st.columns(3)
        pc1.metric("Next Wave", projection.next_wave)
        pc2.metric("Primary Target", f"${projection.primary_target:.2f}")
        pc3.metric("Invalidation", f"${projection.invalidation:.2f}")
        if projection.alt_targets:
            st.caption("Alt targets: " + ", ".join(f"${t:.2f}" for t in projection.alt_targets))

    # ── Alert log ──────────────────────────────────────────────────────
    from src.alert_engine import AlertEngine
    ae = AlertEngine(ticker=ticker)
    alerts = ae.check_proximity_alerts(
        current_price=last_close,
        wave_count=wave_count,
        fib_levels=fib_levels,
        confluence_zones=confluence_zones,
        divergences=divergences,
        projection=projection,
    )
    if alerts:
        st.subheader("Alerts")
        for a in alerts:
            css_class = f"alert-{a.priority.value}"
            st.markdown(
                f'<div class="{css_class}">'
                f"<b>[{a.priority.value.upper()}]</b> {a.alert_type.value.replace('_',' ').title()} — "
                f"{a.message}</div>",
                unsafe_allow_html=True,
            )


def _show_demo_chart(ticker: str = "SPY") -> None:
    """Render a demo chart with saved SPY fixture data (or synthetic fallback)."""
    from pathlib import Path

    fixture_path = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "spy_5min_sample.csv"

    if fixture_path.exists():
        df = pd.read_csv(fixture_path, parse_dates=["timestamp"])
        df.set_index("timestamp", inplace=True)
    else:
        # Fallback to synthetic data if fixture is missing
        np.random.seed(42)
        n = 200
        base = 690.0
        noise = np.random.randn(n).cumsum() * 0.3
        close = base + noise
        high = close + np.abs(np.random.randn(n)) * 0.5
        low = close - np.abs(np.random.randn(n)) * 0.5
        open_ = close + np.random.randn(n) * 0.2
        idx = pd.date_range("2025-01-10 09:30", periods=n, freq="5min")
        df = pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": np.random.randint(1000, 50000, n)},
            index=idx,
        )

    fig = build_chart(df, ticker=ticker)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Demo data (saved SPY fixture) — connect Polygon.io API key and click Scan Now for live results.")


# ═══════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    run_dashboard()
