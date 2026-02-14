#!/usr/bin/env python3
"""Generate a realistic SPY 5-minute OHLCV fixture with clear Elliott Wave patterns.

This creates ~200 bars containing a 5-wave impulse down + partial ABC correction,
with realistic OHLCV relationships (open/close within high/low, volume patterns).
"""

import numpy as np
import pandas as pd

np.random.seed(2025)

n = 200
timestamps = pd.date_range("2025-01-13 09:30", periods=n, freq="5min")

# Build a price path with a clear 5-wave impulse down then ABC correction:
# Wave 1 down: 596 -> 591  (bars 0-25)
# Wave 2 up:   591 -> 595  (bars 25-45)
# Wave 3 down: 595 -> 582  (bars 45-100, longest wave)
# Wave 4 up:   582 -> 589  (bars 100-130, must stay below 591)
# Wave 5 down: 589 -> 580  (bars 130-160)
# ABC up:      580 -> 588  (bars 160-200)

close = np.zeros(n)

# Wave 1 down: 596 -> 591
for i in range(0, 26):
    t = i / 25
    close[i] = 596.0 - 5.0 * t + np.random.randn() * 0.15

# Wave 2 up: 591 -> 595
for i in range(26, 46):
    t = (i - 26) / 19
    close[i] = 591.0 + 4.0 * t + np.random.randn() * 0.12

# Wave 3 down: 595 -> 582 (long, impulsive)
for i in range(46, 101):
    t = (i - 46) / 54
    close[i] = 595.0 - 13.0 * t + np.random.randn() * 0.20

# Wave 4 up: 582 -> 589 (must stay below W1 end of 591)
for i in range(101, 131):
    t = (i - 101) / 29
    close[i] = 582.0 + 7.0 * t + np.random.randn() * 0.12

# Wave 5 down: 589 -> 580
for i in range(131, 161):
    t = (i - 131) / 29
    close[i] = 589.0 - 9.0 * t + np.random.randn() * 0.18

# ABC correction up: 580 -> 588
for i in range(161, n):
    t = (i - 161) / (n - 161 - 1) if i < n - 1 else 1.0
    close[i] = 580.0 + 8.0 * t + np.random.randn() * 0.15

# Generate OHLCV from close
high = close + np.abs(np.random.randn(n)) * 0.4 + 0.1
low = close - np.abs(np.random.randn(n)) * 0.4 - 0.1
open_ = np.roll(close, 1) + np.random.randn(n) * 0.1
open_[0] = 596.0

# Ensure OHLCV consistency
for i in range(n):
    high[i] = max(high[i], open_[i], close[i])
    low[i] = min(low[i], open_[i], close[i])

# Volume: higher on wave 3, lower on wave 4
base_volume = 500000
volume = np.random.randint(300000, 800000, n)
volume[46:101] = np.random.randint(700000, 1500000, 55)  # Wave 3 heavy volume
volume[101:131] = np.random.randint(200000, 500000, 30)  # Wave 4 light volume

df = pd.DataFrame({
    "timestamp": timestamps,
    "open": np.round(open_, 2),
    "high": np.round(high, 2),
    "low": np.round(low, 2),
    "close": np.round(close, 2),
    "volume": volume,
})

df.to_csv("tests/fixtures/spy_5min_sample.csv", index=False)
print(f"Generated {len(df)} bars")
print(f"Price range: ${df['low'].min():.2f} - ${df['high'].max():.2f}")
print(f"Start: {df['timestamp'].iloc[0]}")
print(f"End: {df['timestamp'].iloc[-1]}")
