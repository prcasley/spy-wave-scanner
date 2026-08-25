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

## Design notes

Two decisions that look odd but are deliberate:

**Downsampling keeps the true extremes.** `downsample()` returns each bucket's last value
*except* for the buckets holding the series max and min, which show the real extreme. Without
this the axis label can disagree with the peak quoted in the text — an earlier version showed
an axis top of 329 against a real peak of 346.

**Charts use `bgcolor` attributes, never CSS `background`.** The iOS Gmail app strips
`background` from a `<div>` while keeping the text colour, which renders white-on-white and
makes the chart invisible. Table cells with `bgcolor` survive. Every sized cell also carries
`&nbsp;` because empty cells get collapsed. A unicode block sparkline sits under each chart
as a text fallback that no client can strip.
