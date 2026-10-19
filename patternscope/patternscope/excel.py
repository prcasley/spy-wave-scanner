"""One Excel workbook with every table PatternScope produces."""
from __future__ import annotations

import os
from datetime import datetime

import numpy as np
import pandas as pd

from .config import COST_BPS, OOS_SPLIT
from .guide_content import G

FONT = "Arial"

VERDICT_HELP = {
    "Confirmed": "Profitable after costs on ~500 stocks, held up out-of-sample, and passed the significance test",
    "Promising": "Profitable after costs on the universe and out-of-sample, but not yet statistically proven",
    "Watchlist only": "Looked good on your 11 stocks but not on the broad market — likely hindsight / survivorship",
    "Faded out-of-sample": "Worked in older data but stopped working in recent years",
    "Costs kill it": "Profitable before trading costs, not after",
    "No edge": "Doesn't beat random on the broad market",
    "Too few trades": "Not enough occurrences to judge",
}


def _tz_naive(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            try:
                df[c] = df[c].dt.tz_localize(None)
            except (TypeError, AttributeError):
                pass
        elif df[c].dtype == object and len(df) and isinstance(df[c].dropna().iloc[0] if df[c].notna().any() else None, pd.Timestamp):
            df[c] = pd.to_datetime(df[c], utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None)
    return df.replace([np.inf, -np.inf], np.nan)


def build(path: str, res: dict, verdicts: pd.DataFrame | None = None, meta: dict | None = None,
          universe: pd.DataFrame | None = None):
    wb_dir = os.path.dirname(path)
    if wb_dir:
        os.makedirs(wb_dir, exist_ok=True)
    with pd.ExcelWriter(path, engine="xlsxwriter", datetime_format="yyyy-mm-dd hh:mm",
                        engine_kwargs={"options": {"nan_inf_to_errors": False}}) as xw:
        wb = xw.book
        base = {"font_name": FONT, "font_size": 10}
        F = {
            "hdr": wb.add_format({**base, "bold": True, "font_color": "#FFFFFF", "bg_color": "#18181B",
                                  "border": 1, "border_color": "#3F3F46", "text_wrap": True, "valign": "top"}),
            "title": wb.add_format({**base, "bold": True, "font_size": 18}),
            "bold": wb.add_format({**base, "bold": True}),
            "txt": wb.add_format({**base}),
            "wrap": wb.add_format({**base, "text_wrap": True, "valign": "top"}),
            "note": wb.add_format({**base, "italic": True, "font_color": "#52525B", "text_wrap": True}),
            "int": wb.add_format({**base, "num_format": "#,##0"}),
            "A": wb.add_format({**base, "bold": True, "font_color": "#FFFFFF", "bg_color": "#16A34A"}),
            "B": wb.add_format({**base, "bold": True, "font_color": "#FFFFFF", "bg_color": "#2563EB"}),
            "C": wb.add_format({**base, "bold": True, "font_color": "#FFFFFF", "bg_color": "#A16207"}),
            "F": wb.add_format({**base, "bold": True, "font_color": "#FFFFFF", "bg_color": "#7F1D1D"}),
            "pos": wb.add_format({**base, "font_color": "#15803D"}),
            "neg": wb.add_format({**base, "font_color": "#B91C1C"}),
        }

        def sheet(name, df, widths=None, grade_col=None, pn_cols=(), wrap_cols=()):
            df = _tz_naive(df)
            df.to_excel(xw, sheet_name=name, index=False, startrow=0)
            ws = xw.sheets[name]
            ws.set_column(0, max(0, len(df.columns) - 1), 12, F["txt"])
            for j, c in enumerate(df.columns):
                ws.write(0, j, c, F["hdr"])
                w = (widths or {}).get(c)
                if w is None:
                    sample = df[c].astype(str).head(200).str.len()
                    w = min(42, max(9, len(str(c)) + 2, int(sample.quantile(0.9)) + 2 if len(sample) else 9))
                ws.set_column(j, j, w, F["wrap"] if c in wrap_cols else None)
            ws.freeze_panes(1, 1)
            n = len(df)
            if n:
                ws.autofilter(0, 0, n, len(df.columns) - 1)
                if grade_col and grade_col in df.columns:
                    j = list(df.columns).index(grade_col)
                    for g in "ABCF":
                        ws.conditional_format(1, j, n, j, {"type": "cell", "criteria": "==", "value": f'"{g}"',
                                                           "format": F[g]})
                for c in pn_cols:
                    if c in df.columns:
                        j = list(df.columns).index(c)
                        ws.conditional_format(1, j, n, j, {"type": "cell", "criteria": ">", "value": 0, "format": F["pos"]})
                        ws.conditional_format(1, j, n, j, {"type": "cell", "criteria": "<", "value": 0, "format": F["neg"]})
            return ws

        # ---------- Summary first (formulas fill in once the other sheets exist)
        ws = wb.add_worksheet("Summary")
        ws.set_column(0, 0, 44)
        ws.set_column(1, 1, 18)
        ws.set_column(2, 2, 70)
        ws.write(0, 0, "PatternScope workbook", F["title"])
        ws.write(1, 0, f"Built {datetime.now():%Y-%m-%d %H:%M} · watchlist data from Yahoo Finance", F["note"])
        r = 3
        stats = res["stats"]
        n_stats = len(stats)
        ws.write(r, 0, "Watchlist", F["bold"]); r += 1
        rows = [("Live signals (latest bars)", "=MAX(0,COUNTA('Live Signals'!A:A)-1)", "Patterns that confirmed on the most recent bars"),
                ("Historical detections", "=MAX(0,COUNTA('All Detections'!A:A)-1)", "Every past pattern hit that was scored")]
        for g in ["A", "B", "C", "F"]:
            rows.append((f"Grade {g} patterns (pooled watchlist)",
                         f"=COUNTIFS('Pattern Stats'!A2:A{n_stats + 1},\"ALL\",'Pattern Stats'!X2:X{n_stats + 1},\"{g}\")", ""))
        if verdicts is not None and len(verdicts):
            nv = len(verdicts) + 1
            rows.append(("", "", ""))
            rows.append(("Validation (S&P 500 universe)", "", ""))
            for v in ["Confirmed", "Promising", "Watchlist only", "Faded out-of-sample", "Costs kill it", "No edge", "Too few trades"]:
                rows.append((f"  {v}", f"=COUNTIF(Verdicts!$Z$2:$Z${nv},\"{v}\")", VERDICT_HELP[v]))
        for label, formula, note in rows:
            if label in ("Validation (S&P 500 universe)",):
                ws.write(r, 0, label, F["bold"])
            else:
                ws.write(r, 0, label, F["txt"])
                if formula:
                    ws.write_formula(r, 1, formula, F["int"])
                ws.write(r, 2, note, F["note"])
            r += 1
        r += 1
        ws.write(r, 0, "Assumptions", F["bold"]); r += 1
        notes = [
            ("Entry", "Next bar's open after the pattern confirms (gaps: the gap bar's open)."),
            ("Stop vs target same bar", "Counted as a stop (conservative)."),
            ("Trading costs per side (bps)", ", ".join(f"{k}: {v}" for k, v in COST_BPS.items()) + "  — commission + slippage estimate, set in config.py"),
            ("Out-of-sample split", ", ".join(f"{k}: {v}" for k, v in OOS_SPLIT.items()) + "  — grade on earlier data, test on later"),
            ("Universe", "S&P 500 constituents (datasets/s-and-p-500-companies on GitHub). Signals before a stock joined the index are dropped. Stocks that left the index are not included, so some survivorship bias remains."),
            ("Significance", "One-sided t-test on net R per trade, Benjamini-Hochberg false-discovery rate 10%."),
            ("Grades", "A: n≥30, ≥0.25R, ≥5pp edge, positive in both halves. B: ≥0.10R. C: >0. F: losing. low-n: <20 trades."),
        ]
        if meta:
            notes.append(("Validation run", ", ".join(f"{k}={v}" for k, v in meta.items())))
        for k, v in notes:
            ws.write(r, 0, k, F["txt"]); ws.write(r, 2, v, F["note"]); r += 1

        # ---------- data sheets
        if verdicts is not None and len(verdicts):
            cols = ["tf", "pattern", "direction", "watch_grade", "watch_n", "watch_win", "watch_R", "watch_R_net",
                    "uni_n", "uni_win", "uni_R", "uni_R_net", "uni_t", "uni_p", "uni_sig",
                    "is_n", "is_win", "is_R", "is_R_net", "oos_n", "oos_win", "oos_R", "oos_R_net", "is_p", "oos_p", "verdict"]
            v = verdicts.reindex(columns=cols)
            v["uni_sig"] = v["uni_sig"].map({True: "yes", False: "no"}).fillna("no")
            sheet("Verdicts", v, grade_col="watch_grade",
                  pn_cols=["watch_R", "watch_R_net", "uni_R", "uni_R_net", "is_R_net", "oos_R_net"],
                  widths={"pattern": 34, "verdict": 22})
        st_cols = ["ticker", "tf", "pattern", "category", "direction", "n", "per_1000_bars", "target_pct", "stop_pct",
                   "timeout_pct", "expectancy_R", "profit_factor", "avg_rr_planned", "formation_bars_med",
                   "bars_to_target_med", "bars_held_med", "mfe_R_med", "mae_R_med", "exp_R_first_half",
                   "exp_R_second_half", "last_seen", "hit_mid_pct", "edge_mid_pp", "grade"]
        s = stats.copy()
        mid = {"1h": 7, "1d": 10, "1wk": 13}
        s["hit_mid_pct"] = [r_.get(f"hit{mid.get(r_['tf'], 10)}_pct") for _, r_ in s.iterrows()]
        s["edge_mid_pp"] = [r_.get(f"edge{mid.get(r_['tf'], 10)}_pp") for _, r_ in s.iterrows()]
        sheet("Pattern Stats", s.reindex(columns=st_cols), grade_col="grade",
              pn_cols=["expectancy_R", "exp_R_first_half", "exp_R_second_half", "edge_mid_pp"],
              widths={"pattern": 34})
        fr = res.get("fresh")
        fr = fr if fr is not None and len(fr) else pd.DataFrame(columns=["ticker"])
        sheet("Live Signals", fr.reindex(columns=["ticker", "tf", "pattern", "category", "direction", "signal_time",
                                                  "signal_close", "entry", "stop", "target", "formation_bars", "outcome"]),
              widths={"pattern": 34})
        snaps = pd.DataFrame([{k: v_ for k, v_ in x.items() if k != "dividends"} for x in res.get("snapshots", [])])
        sheet("Watchlist Compare", snaps if len(snaps) else pd.DataFrame(columns=["ticker"]),
              pn_cols=["r1w", "r1m", "r3m", "r1y", "off_high", "vs50", "vs200"])
        div_rows = []
        for x in res.get("snapshots", []):
            d = x.get("dividends") or {}
            for rr in d.get("recent", []):
                div_rows.append(dict(ticker=x["ticker"], name=d.get("name"), frequency=d.get("frequency"),
                                     ex_date=rr["date"], amount=rr["amount"], last_close=x["close"]))
        sheet("Distributions", pd.DataFrame(div_rows) if div_rows else pd.DataFrame(columns=["ticker", "ex_date", "amount"]))
        prof = []
        for p in res.get("profiles", []):
            row = dict(ticker=p["ticker"], tf=p["tf"], last_close=p["last_close"], n_pullbacks=p["n_pullbacks"],
                       n_bounces=p["n_bounces"])
            for key in ["pullback_depth", "pullback_bars", "bounce_depth", "bounce_bars"]:
                for q, val in (p.get(key) or {}).items():
                    row[f"{key}_p{q}"] = val
            for k_, val in (p.get("now") or {}).items():
                row[f"now_{k_}"] = val
            prof.append(row)
        sheet("Pullback Map", pd.DataFrame(prof))
        guide = pd.DataFrame([dict(pattern=g["title"], type=g["family"], bullish_names=", ".join(g["bull"]),
                                   bearish_names=", ".join(g["bear"]), what_you_see=g["what"],
                                   what_it_means=g["means"], how_traders_use_it=g["trade"]) for g in G])
        sheet("Pattern Guide", guide, widths={"pattern": 30, "what_you_see": 50, "what_it_means": 60,
                                             "how_traders_use_it": 50, "bullish_names": 28, "bearish_names": 28},
              wrap_cols=("what_you_see", "what_it_means", "how_traders_use_it", "bullish_names", "bearish_names"))
        if universe is not None and len(universe):
            sheet("Universe", universe.reindex(columns=["Symbol", "Security", "GICS Sector", "GICS Sub-Industry", "Date added"]))
        tr = res["trades"]
        keep = ["ticker", "tf", "pattern", "category", "direction", "start_time", "signal_time", "formation_bars",
                "entry", "stop", "target", "outcome", "exit", "R", "rr_planned", "bars_held", "mfe_R", "mae_R", "ret_pct"]
        tr = tr.reindex(columns=keep)
        for c in ["entry", "stop", "target", "exit"]:
            tr[c] = tr[c].astype(float).round(4)
        for c in ["R", "rr_planned", "mfe_R", "mae_R", "ret_pct"]:
            tr[c] = tr[c].astype(float).round(3)
        sheet("All Detections", tr.head(1_000_000), widths={"pattern": 30}, pn_cols=["R"])
        ws.activate()
