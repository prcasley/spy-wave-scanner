"""PatternScope smoke + lookahead tests (synthetic data, no network)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "patternscope"))

from patternscope.config import TIMEFRAMES
from patternscope.core import Ctx
from patternscope.data import synthetic
from patternscope.pipeline import analyze, combine

from patternscope import candles, chart, setups


def _sigs(df, tf):
    c = Ctx(df, tf, TIMEFRAMES[tf], "X")
    return {(s.pattern, s.end, round(s.stop, 4)) for s in candles.detect(c) + chart.detect(c) + setups.detect(c)}


def test_pipeline_runs_all_timeframes():
    res = combine([analyze(synthetic(tf, 1500, seed=3), "X", tf, TIMEFRAMES[tf]) for tf in TIMEFRAMES], TIMEFRAMES)
    assert len(res["trades"]) > 500 and len(res["stats"]) > 50


def test_no_material_lookahead():
    df = synthetic("1d", 1500, seed=5)
    full = _sigs(df, "1d")
    past = [s for s in full if s[1] < 1000]
    trunc = _sigs(df.iloc[:1000], "1d")
    missing = [s for s in past if s not in trunc]
    assert len(missing) <= 0.01 * len(past)


def test_validation_and_excel(tmp_path):
    from patternscope.validation import verdicts

    from patternscope import excel

    res = combine([analyze(synthetic(tf, 1500, seed=4), "W", tf, TIMEFRAMES[tf]) for tf in TIMEFRAMES], TIMEFRAMES)
    uni = analyze(synthetic("1d", 2500, seed=9), "U", "1d", TIMEFRAMES["1d"])["trades"]
    tbl = verdicts(res["trades"], uni, res["stats"])
    assert {"verdict", "uni_R_net", "oos_R_net"} <= set(tbl.columns)
    out = tmp_path / "t.xlsx"
    excel.build(str(out), res, tbl)
    assert out.stat().st_size > 10_000


def test_cockpit_renders():
    from patternscope import cockpit

    res = combine([analyze(synthetic("1d", 1500, seed=6), "X", "1d", TIMEFRAMES["1d"])], TIMEFRAMES)
    html = cockpit.build(res, TIMEFRAMES)
    assert "Flight display" in html and "/*__DATA__*/" not in html


def test_feed_schema():
    from patternscope import feed

    res = combine([analyze(synthetic("1d", 1500, seed=8), "BTC-USD", "1d", TIMEFRAMES["1d"])], TIMEFRAMES)
    d = feed.build(res)
    assert d["schema_version"] == 1
    for s in d["signals"]:
        assert s["market"] == "crypto" and len(s["id"]) == 16 and s["entry_rule"] == "next bar open"
