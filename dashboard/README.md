# Positioning dashboard

Regenerates `docs/index.html` twice each weekday and emails a mobile-safe summary.
Runs entirely inside GitHub Actions — no server, no local machine.

## Setup

**1. Secrets** — Settings → Secrets and variables → Actions → *Secrets*

| Secret | Required | Notes |
|---|---|---|
| `TWELVEDATA_KEY` | yes | prices. Free tier 800/day, 8/min |
| `ALPHAVANTAGE_KEY` | no | put/call ratios. Free tier **25/day** |
| `SMTP_USER` | no | gmail address; email is skipped if unset |
| `SMTP_PASS` | no | gmail **app password**, not your login password |
| `MAIL_TO` | no | defaults to `SMTP_USER` |

**2. Variables** — same page, *Variables* tab

| Variable | Example |
|---|---|
| `TICKERS` | `SPY,QQQ,NVDA,TSLA,BE,MU,ACN` |
| `PAGES_URL` | `https://prcasley.github.io/spy-wave-scanner/` |

**3. Pages** — Settings → Pages → Source: **GitHub Actions**

**4.** Actions → *Positioning dashboard* → Run workflow.

## Budget

One run costs `2 × tickers` Twelve Data calls and `1 × tickers` Alpha Vantage calls.
Seven tickers, two runs a day:

- Twelve Data — **28 of 800/day**
- Alpha Vantage — **14 of 25/day**

Alpha Vantage is the binding constraint. Past ~12 tickers put/call starts dropping out;
the generator degrades gracefully, marks the gap on the card, and notes it in Data health
rather than silently showing a stale number.

## Daylight saving

Cron is UTC and does not shift. The schedule is correct for **EDT**. When EST begins in
November, change both crons to `29 14` and `59 20`.

That is the only edit needed. The preopen/close slot is chosen from the cron's *minute*
(`29` = morning, `59` = afternoon) precisely because the hour moves and the minute does not —
so shifting the hours cannot relabel a run. Do not reintroduce a comparison against the whole
cron string.

## Design notes

Two decisions that look odd but are deliberate:

**Downsampling keeps the true extremes.** `downsample()` returns each bucket's last value
*except* for the buckets holding the series max and min, which show the real extreme. Without
this the axis label can disagree with the peak quoted in the text — an earlier version showed
an axis top of 329 against a real peak of 346.

The max and the min can fall in the *same* bucket, and only one bar can hold a value. The peak
wins it and the low is re-homed into the neighbouring bar, so both axis labels stay true. Skip
that step and the bottom axis silently under-reports — the identical bug, on the other end of
the scale. It is not hypothetical: a spike adjacent to a trough triggers it, which showed up in
roughly 4% of randomly generated 100-bar series.

**Charts use `bgcolor` attributes, never CSS `background`.** The iOS Gmail app strips
`background` from a `<div>` while keeping the text colour, which renders white-on-white and
makes the chart invisible. Table cells with `bgcolor` survive. Every sized cell also carries
`&nbsp;` because empty cells get collapsed. A unicode block sparkline sits under each chart
as a text fallback that no client can strip.

This applies to the *button* too, not just the charts. The "Open the full dashboard" CTA gets
its colour from a `bgcolor` on a wrapping table cell rather than `background` on the `<a>`, so
it survives the same stripping. This path only renders when `PAGES_URL` is set, which is why
it is easy to miss when testing without one.
