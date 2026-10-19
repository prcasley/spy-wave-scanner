"""Plain-English pattern guide: a drawing spec + kid-level explanation for every pattern.

Drawing coordinates: x 0..100 left->right, y 0..100 bottom->top (higher = higher price).
  path    price line points
  lines   [x1, y1, x2, y2, style, color, label]   style: solid|dash   color: w|g|r|p|y
  arrow   [x, y, 'up'|'down']                      the breakout / expected move
  candles [[o, h, l, c, focus], ...]               focus=1 marks the pattern candles
  ma      [[points, color, label], ...]            extra moving-average style lines
  panel   {"lines": [[points, color, label], ...], "levels": [[y, label]]}  small indicator box below
"""

G = []


def add(id, title, family, names_bull, names_bear, what, means, trade, draw, flip_note=None):
    G.append(dict(id=id, title=title, family=family, bull=names_bull, bear=names_bear, what=what,
                  means=means, trade=trade, draw=draw,
                  flip=flip_note or ("The bearish version is the same picture flipped upside down." if names_bear and names_bull else None)))


# ============================================================ CHART PATTERNS
add("double-bottom", "Double Bottom / Double Top", "chart", ["Double Bottom"], ["Double Top"],
    "Price falls to a floor, bounces, falls to the same floor again, and bounces again. It looks like the letter W.",
    "It's like a ball hitting the ground twice. The floor held both times, so buyers are guarding that price. When price climbs over the middle bump, sellers have given up.",
    "Buy when price closes above the middle peak (the 'neckline'). Stop goes under the floor. The target is the height of the W added on top.",
    dict(path=[[0, 85], [15, 55], [28, 22], [42, 52], [56, 23], [72, 54], [86, 72]],
         lines=[[24, 21, 60, 21, "dash", "w", "floor"], [36, 52, 80, 52, "dash", "y", "neckline"]], arrow=[78, 58, "up"]))
add("triple-bottom", "Triple Bottom / Triple Top", "chart", ["Triple Bottom"], ["Triple Top"],
    "Like a double bottom, but price tests the same floor three times before breaking up.",
    "Someone knocks on a locked door three times and nobody lets the price go lower. After the third try, sellers run out of steam.",
    "Buy on a close above the highest bump between the three lows. Stop under the floor.",
    dict(path=[[0, 85], [12, 25], [26, 52], [40, 24], [54, 51], [68, 25], [82, 55], [94, 72]],
         lines=[[8, 23, 72, 23, "dash", "w", "floor"], [24, 52, 90, 52, "dash", "y", "neckline"]], arrow=[86, 60, "up"]))
add("inverse-hs", "Inverse Head & Shoulders / Head & Shoulders", "chart",
    ["Inverse Head & Shoulders"], ["Head & Shoulders"],
    "Three dips: a small one (left shoulder), a deeper one (the head), then a small one again (right shoulder). Upside down, it looks like a person.",
    "Each time sellers push down, they get weaker. The last dip couldn't go as low as the head, which means buyers are taking over.",
    "Buy when price breaks above the line connecting the two bounces (the neckline). Stop under the right shoulder. Target = head-to-neckline distance added above.",
    dict(path=[[0, 80], [12, 45], [24, 62], [38, 18], [52, 63], [64, 44], [78, 64], [92, 82]],
         lines=[[20, 62, 90, 64, "dash", "y", "neckline"]], arrow=[84, 70, "up"]))
add("cup-handle", "Cup & Handle / Inverse Cup", "chart", ["Cup & Handle"], ["Inverse Cup & Handle"],
    "Price slides down slowly, rounds out like the bottom of a teacup, climbs back to where it started, dips a little (the handle), then breaks higher.",
    "The round bottom shows sellers slowly getting tired, not a panic. The little handle is the last few nervous people selling before the move up.",
    "Buy on a close above the cup's rim. Stop under the handle. Target = cup depth added above the rim.",
    dict(path=[[0, 78], [8, 62], [18, 38], [30, 26], [42, 24], [54, 30], [66, 50], [74, 76], [80, 66], [86, 70], [94, 88]],
         lines=[[0, 78, 96, 78, "dash", "y", "rim"]], arrow=[90, 82, "up"]))
add("rounding-bottom", "Rounding Bottom / Rounding Top", "chart", ["Rounding Bottom"], ["Rounding Top"],
    "A long, smooth U shape, like a cup without a handle.",
    "It's like a slow turn of a big ship. Things change direction gently instead of suddenly.",
    "Buy when price closes above the rim of the U. Stop around the middle of the bowl.",
    dict(path=[[0, 80], [12, 56], [24, 38], [38, 28], [52, 28], [66, 40], [78, 60], [88, 80], [96, 90]],
         lines=[[0, 80, 98, 80, "dash", "y", "rim"]], arrow=[92, 84, "up"]))
add("bull-flag", "Bull Flag / Bear Flag", "chart", ["Bull Flag"], ["Bear Flag"],
    "A fast, straight run up (the flagpole), then a short, gentle drift down in a small box (the flag).",
    "Runners stop to catch their breath before running again. The flag is the market resting after a sprint, then it keeps going the same way.",
    "Buy when price breaks above the top of the flag. Stop under the flag. Target = length of the pole added on.",
    dict(path=[[0, 15], [10, 22], [22, 70], [30, 66], [36, 70], [44, 60], [50, 64], [58, 56], [66, 62], [80, 92]],
         lines=[[24, 72, 66, 63, "dash", "w", ""], [28, 64, 62, 54, "dash", "w", ""]], arrow=[72, 76, "up"]))
add("bull-pennant", "Bull Pennant / Bear Pennant", "chart", ["Bull Pennant"], ["Bear Pennant"],
    "Same as a flag, but the resting part gets squeezed into a tiny triangle instead of a box.",
    "Like a spring being pressed after a big jump, it stores energy and usually pops the same way as the pole.",
    "Buy on a break above the small triangle. Stop under it. Target = pole length.",
    dict(path=[[0, 15], [10, 22], [22, 72], [30, 58], [38, 68], [46, 61], [52, 66], [58, 63], [72, 92]],
         lines=[[22, 72, 62, 64, "dash", "w", ""], [28, 56, 62, 62, "dash", "w", ""]], arrow=[66, 72, "up"]))
add("abcd", "AB=CD", "chart", ["Bullish AB=CD"], ["Bearish AB=CD"],
    "Price drops (A to B), bounces part way (B to C), then drops again the SAME distance as the first drop (C to D).",
    "Markets often move in matching steps, like a staircase with equal steps. When the second step equals the first, the move is often 'done' for now.",
    "Buy near D once it holds. Stop just under D. Target = about 62% of the way back up to C.",
    dict(path=[[0, 88], [28, 44], [46, 64], [76, 20], [92, 40]],
         lines=[[0, 88, 28, 44, "solid", "p", "AB"], [46, 64, 76, 20, "solid", "p", "CD = AB"]], arrow=[84, 30, "up"]))
add("fib", "Fib 50-61.8 Bounce / Rejection", "chart", ["Fib 50-61.8 Bounce"], ["Fib 50-61.8 Rejection"],
    "After a big move up, price slides back about halfway (50% to 61.8%) and then starts going up again.",
    "Traders all over the world watch the 'halfway' area, so lots of them buy there. It works partly because so many people expect it to.",
    "Buy when a candle bounces from the 50-61.8% zone. Stop below the 78.6% line. Target = the old high.",
    dict(path=[[0, 15], [30, 88], [44, 66], [56, 48], [64, 56], [80, 86]],
         lines=[[30, 88, 96, 88, "dash", "w", "high"], [30, 51, 96, 51, "dash", "y", "50%"], [30, 43, 96, 43, "dash", "y", "61.8%"]],
         arrow=[66, 60, "up"]))
add("rsi-div", "RSI Divergence", "chart", ["Bullish RSI Divergence"], ["Bearish RSI Divergence"],
    "Price makes a new lower low, but the RSI meter (a speedometer for price) makes a HIGHER low.",
    "It's like a car going downhill but the gas pedal is easing up. Price is still falling, but the force behind it is getting weaker.",
    "Buy after the second low is confirmed. Stop just under it. Target = 2x the risk.",
    dict(path=[[0, 80], [22, 40], [40, 62], [62, 26], [80, 54], [94, 66]],
         lines=[[22, 40, 62, 26, "solid", "r", "lower low"]], arrow=[74, 46, "up"],
         panel=dict(lines=[[[[0, 60], [22, 18], [40, 52], [62, 36], [80, 64], [94, 70]], "p", "RSI"]],
                    levels=[[30, "30"]], marks=[[22, 18, 62, 36, "g", "higher low"]])))
add("asc-tri", "Ascending Triangle", "chart", ["Ascending Triangle (break ↑)"], ["Ascending Triangle (break ↓)"],
    "A flat ceiling on top, and a floor that keeps rising. Each dip stops higher than the last one.",
    "Buyers keep showing up earlier and earlier, pushing against the same ceiling, like water rising against a dam. Usually the dam breaks upward.",
    "Buy on a close above the flat ceiling. Stop under the last rising low. Target = triangle height added above.",
    dict(path=[[0, 20], [14, 72], [26, 36], [40, 72], [52, 50], [64, 72], [72, 60], [86, 92]],
         lines=[[8, 73, 76, 73, "dash", "y", "ceiling"], [0, 20, 74, 64, "dash", "w", "rising floor"]], arrow=[78, 80, "up"]),
    "The scanner tracks both break directions separately so you can see which way it really breaks more often.")
add("desc-tri", "Descending Triangle", "chart", ["Descending Triangle (break ↑)"], ["Descending Triangle (break ↓)"],
    "A flat floor underneath, and a ceiling that keeps getting lower.",
    "Sellers keep selling sooner and sooner, pushing on the same floor. Textbooks say it usually breaks down, but on your stocks it has broken UP surprisingly often.",
    "Trade the direction it breaks. Stop on the other side. Target = triangle height.",
    dict(path=[[0, 85], [14, 28], [26, 70], [40, 28], [52, 54], [64, 28], [72, 40], [86, 8]],
         lines=[[8, 27, 76, 27, "dash", "y", "floor"], [0, 85, 74, 36, "dash", "w", "falling ceiling"]], arrow=[78, 18, "down"]),
    "Both directions are tracked — check the stats to see which one actually pays on your tickers.")
add("sym-tri", "Symmetrical Triangle", "chart", ["Symmetrical Triangle (break ↑)"], ["Symmetrical Triangle (break ↓)"],
    "Lower highs AND higher lows. The price swings get smaller and smaller, squeezing into a point.",
    "It's a tug-of-war where both teams are getting tired. Eventually one side lets go and price shoots out that way.",
    "Trade the direction of the breakout. Stop on the other side. Target = widest part of the triangle.",
    dict(path=[[0, 90], [14, 18], [28, 76], [42, 32], [56, 64], [66, 44], [74, 56], [88, 86]],
         lines=[[0, 90, 80, 53, "dash", "w", ""], [10, 16, 80, 49, "dash", "w", ""]], arrow=[80, 66, "up"]))
add("rising-wedge", "Rising Wedge", "chart", ["Rising Wedge (break ↑)"], ["Rising Wedge (break ↓)"],
    "Price climbs, but each push up is smaller than the last. Both lines slope up and get closer together.",
    "Like a car climbing a hill in a higher gear and starting to stall. Textbooks call it bearish, so watch which way it breaks.",
    "Trade the break. Stop on the other side of the wedge.",
    dict(path=[[0, 10], [16, 46], [26, 30], [42, 62], [52, 50], [66, 72], [74, 64], [88, 40]],
         lines=[[0, 10, 80, 66, "dash", "w", ""], [10, 44, 80, 74, "dash", "w", ""]], arrow=[82, 52, "down"]))
add("falling-wedge", "Falling Wedge", "chart", ["Falling Wedge (break ↑)"], ["Falling Wedge (break ↓)"],
    "Price falls, but each drop is smaller than the last. Both lines slope down and get closer together.",
    "Sellers are running out of energy, like a ball bouncing lower and lower. Usually it pops up.",
    "Buy on a break above the top line. Stop under the last low.",
    dict(path=[[0, 92], [16, 52], [26, 70], [42, 38], [52, 50], [66, 30], [74, 38], [88, 64]],
         lines=[[0, 92, 80, 36, "dash", "w", ""], [10, 54, 80, 28, "dash", "w", ""]], arrow=[82, 50, "up"]))
add("rectangle", "Rectangle (trading range)", "chart", ["Rectangle (break ↑)"], ["Rectangle (break ↓)"],
    "Price bounces between a flat ceiling and a flat floor, like a ball in a hallway.",
    "Buyers and sellers agree on a price range for a while. When price escapes the box, a new move often starts.",
    "Trade the direction it escapes. Stop back inside the box. Target = box height.",
    dict(path=[[0, 30], [12, 70], [24, 30], [36, 70], [48, 30], [60, 70], [70, 32], [80, 68], [92, 92]],
         lines=[[4, 71, 86, 71, "dash", "y", "ceiling"], [4, 29, 86, 29, "dash", "y", "floor"]], arrow=[86, 80, "up"]))
add("asc-channel", "Ascending Channel", "chart", ["Ascending Channel (break ↑)"], ["Ascending Channel (break ↓)"],
    "Price moves up between two parallel lines, like a car driving up a highway between two lane lines.",
    "An orderly uptrend. If it falls out the bottom, the trend may be tired. If it breaks out the top, it's speeding up.",
    "Trade the break. Stop back inside the channel.",
    dict(path=[[0, 10], [14, 40], [24, 26], [40, 58], [50, 44], [66, 76], [74, 62], [88, 40]],
         lines=[[0, 10, 80, 60, "dash", "w", ""], [0, 30, 80, 82, "dash", "w", ""]], arrow=[84, 50, "down"]))
add("desc-channel", "Descending Channel", "chart", ["Descending Channel (break ↑)"], ["Descending Channel (break ↓)"],
    "Price moves down between two parallel lines that slope downward.",
    "An orderly downtrend. When price finally jumps out of the top, the downtrend is often over. This is one of the best-scoring patterns on your tickers.",
    "Buy on a close above the top line. Stop under the last low.",
    dict(path=[[0, 90], [14, 60], [24, 74], [40, 42], [50, 56], [66, 24], [74, 38], [88, 66]],
         lines=[[0, 92, 80, 42, "dash", "w", ""], [0, 70, 80, 18, "dash", "w", ""]], arrow=[84, 56, "up"]))
add("broadening", "Broadening Formation (megaphone)", "chart", ["Broadening Formation (break ↑)"], ["Broadening Formation (break ↓)"],
    "The swings get BIGGER: higher highs and lower lows, shaped like a megaphone.",
    "The market is getting more nervous and emotional. It means big, wild moves, so be careful.",
    "Trade the break out of the megaphone, with a wider stop.",
    dict(path=[[0, 52], [12, 62], [22, 42], [36, 72], [48, 32], [62, 82], [74, 22], [88, 6]],
         lines=[[0, 54, 70, 86, "dash", "w", ""], [0, 48, 76, 18, "dash", "w", ""]], arrow=[84, 12, "down"]))

# ============================================================ CANDLESTICKS
# Candle = one bar: body (open->close) + wicks (high/low). Green = closed up, red = closed down.
DOWN_CTX = [[80, 84, 70, 72, 0], [72, 74, 60, 62, 0], [62, 64, 50, 52, 0]]
UP_CTX = [[20, 30, 18, 28, 0], [28, 40, 26, 38, 0], [38, 50, 36, 48, 0]]
add("hammer", "Hammer / Hanging Man", "candle", ["Hammer"], ["Hanging Man"],
    "A candle with a small body at the top and a long tail (wick) hanging down, like a hammer.",
    "During that bar, sellers pushed price way down, but buyers smashed it right back up. After a fall, that's a sign the bottom may be in.",
    "Buy above the hammer. Stop under the tail. The same shape after a rise is a 'Hanging Man', a warning sign.",
    dict(candles=DOWN_CTX + [[48, 50, 28, 50, 1]]),
    "Hanging Man is the same shape but appears after prices have been rising.")
add("inv-hammer", "Inverted Hammer / Shooting Star", "candle", ["Inverted Hammer"], ["Shooting Star"],
    "A small body at the bottom with a long wick sticking UP.",
    "Buyers tried to launch price higher but it fell back. After a fall it hints buyers are waking up. After a rise (Shooting Star) it means the rocket ran out of fuel.",
    "Usually needs another bar to confirm. On your tickers the Inverted Hammer has lost money, so treat it with suspicion.",
    dict(candles=UP_CTX + [[48, 70, 46, 47, 1]]),
    "Shown: the Shooting Star (after a rise). The Inverted Hammer is the same shape after a fall.")
add("engulfing", "Engulfing", "candle", ["Bullish Engulfing"], ["Bearish Engulfing"],
    "A small red candle followed by a big green candle whose body completely swallows the red one.",
    "Like a big wave washing over a small one. Buyers didn't just stop the selling, they overpowered it.",
    "Buy above the green candle. Stop under its low. Target 2x risk.",
    dict(candles=DOWN_CTX + [[52, 53, 46, 47, 1], [45, 60, 44, 58, 1]]))
add("piercing", "Piercing Line / Dark Cloud Cover", "candle", ["Piercing Line"], ["Dark Cloud Cover"],
    "A big red candle, then a green candle that opens lower but closes more than halfway up the red one.",
    "Sellers opened the day strong, but buyers took back more than half of yesterday's loss. That's a punch back.",
    "Buy above the green candle. Stop under its low.",
    dict(candles=DOWN_CTX + [[56, 57, 38, 40, 1], [36, 52, 34, 50, 1]]))
add("morning-star", "Morning Star / Evening Star", "candle", ["Morning Star"], ["Evening Star"],
    "Three candles: a big red one, a tiny one (the 'star'), then a big green one.",
    "Like night turning into morning. First darkness (selling), then a quiet pause, then sunrise (buyers return).",
    "Buy above the third candle. Stop under the star.",
    dict(candles=DOWN_CTX + [[58, 59, 40, 42, 1], [38, 40, 33, 36, 1], [38, 56, 37, 54, 1]]))
add("morning-doji", "Morning Doji Star / Evening Doji Star", "candle", ["Morning Doji Star"], ["Evening Doji Star"],
    "Same as a Morning Star, but the middle candle is a 'doji', a candle with almost no body (open = close).",
    "The doji is a moment of total balance, nobody winning. After a fall, that pause often means sellers are out of gas.",
    "Buy above the third candle. Stop under the doji.",
    dict(candles=DOWN_CTX + [[58, 59, 40, 42, 1], [36, 39, 33, 36.3, 1], [38, 56, 37, 54, 1]]))
add("soldiers", "Three White Soldiers / Three Black Crows", "candle", ["Three White Soldiers"], ["Three Black Crows"],
    "Three strong green candles in a row, each closing higher than the last.",
    "Three soldiers marching up a hill together, steady and strong buying, not just one lucky day.",
    "Momentum signal. Stop under the first soldier.",
    dict(candles=DOWN_CTX[:2] + [[60, 62, 56, 58, 0], [56, 70, 55, 69, 1], [66, 80, 65, 79, 1], [76, 90, 75, 89, 1]]))
add("harami", "Harami (pregnant)", "candle", ["Bullish Harami"], ["Bearish Harami"],
    "A big candle followed by a small candle that fits completely inside the big one's body.",
    "'Harami' means pregnant in Japanese, a big mom candle with a baby inside. The selling suddenly got quiet.",
    "Weak signal on its own. On your tickers the bearish one loses money, so don't short it.",
    dict(candles=DOWN_CTX + [[62, 63, 38, 40, 1], [44, 52, 43, 50, 1]]))
add("harami-cross", "Harami Cross", "candle", ["Bullish Harami Cross"], ["Bearish Harami Cross"],
    "A harami where the baby candle is a doji (a plus sign shape).",
    "Total pause after a big move, like a car slamming the brakes.",
    "Wait for the next candle to confirm direction. Scored poorly on your tickers.",
    dict(candles=DOWN_CTX + [[62, 63, 38, 40, 1], [48, 54, 44, 48.3, 1]]))
add("tweezer", "Tweezer Bottom / Tweezer Top", "candle", ["Tweezer Bottom"], ["Tweezer Top"],
    "Two candles in a row with lows at almost exactly the same price, like the two tips of tweezers.",
    "Price hit the same floor two days in a row and couldn't break it. That floor is being defended.",
    "Buy above the second candle. Stop under the matching lows. Tweezer Top shorts lose money on your tickers.",
    dict(candles=DOWN_CTX + [[52, 53, 38, 41, 1], [41, 50, 38, 48, 1]]))
add("marubozu", "Marubozu", "candle", ["Bullish Marubozu"], ["Bearish Marubozu"],
    "A big candle with NO wicks. It opens at the very low and closes at the very high.",
    "Buyers were in control from the first second to the last. No fight at all.",
    "Momentum signal; continuation is common. Stop under the candle's middle or low.",
    dict(candles=[[30, 34, 28, 32, 0], [32, 36, 30, 34, 0], [34, 36, 31, 33, 0], [33, 70, 33, 70, 1]]))
add("doji-dg", "Dragonfly Doji / Gravestone Doji", "candle", ["Dragonfly Doji"], ["Gravestone Doji"],
    "A doji with a long tail down and no top wick, shaped like a T (a dragonfly). Gravestone is the upside-down T.",
    "Sellers dragged price way down, but buyers pulled it ALL the way back to where it started. A strong rejection of lower prices.",
    "Buy above the dragonfly. Stop under its tail. One of the better candles on the hourly chart.",
    dict(candles=DOWN_CTX + [[48, 48.6, 26, 48.3, 1]]))
add("three-inside", "Three Inside Up / Down", "candle", ["Three Inside Up"], ["Three Inside Down"],
    "A harami (big red, small green inside) plus a third green candle that closes above the big red's open.",
    "The 'baby' hinted at a turn, and the third candle confirms it, like a second witness.",
    "Buy above candle three. Strong on the weekly chart.",
    dict(candles=DOWN_CTX + [[62, 63, 40, 42, 1], [44, 54, 43, 52, 1], [52, 68, 51, 66, 1]]))
add("three-outside", "Three Outside Up / Down", "candle", ["Three Outside Up"], ["Three Outside Down"],
    "An engulfing pattern plus a third candle that closes even higher.",
    "Buyers won the fight and then won again the next day. Confirmation.",
    "Buy above candle three. Stop under the pattern's low.",
    dict(candles=DOWN_CTX + [[52, 53, 46, 47, 1], [45, 60, 44, 58, 1], [58, 68, 57, 67, 1]]))
add("three-methods", "Rising / Falling Three Methods", "candle", ["Rising Three Methods"], ["Falling Three Methods"],
    "A big green candle, three small candles drifting down inside its range, then another big green candle to a new high.",
    "A quick rest in the middle of a trip. The three small candles are the 'pit stop', then the trend continues.",
    "Buy above the last candle. Stop under the small candles.",
    dict(candles=[[20, 24, 18, 22, 0], [22, 50, 21, 49, 1], [48, 50, 42, 44, 1], [44, 46, 38, 40, 1],
                  [40, 44, 34, 37, 1], [38, 62, 37, 60, 1]]))
add("kicker", "Kicker", "candle", ["Bullish Kicker"], ["Bearish Kicker"],
    "A red candle, then the next candle opens ABOVE where the red one opened (a gap) and runs up green.",
    "Something big changed overnight (often news). The market 'kicked' into the other direction.",
    "Strong but rare. Stop under the gap.",
    dict(candles=DOWN_CTX[:2] + [[60, 62, 44, 46, 1], [64, 82, 63, 80, 1]]))
add("abandoned-baby", "Abandoned Baby", "candle", ["Bullish Abandoned Baby"], ["Bearish Abandoned Baby"],
    "A big red candle, then a doji that gaps down all by itself, then a green candle that gaps back up.",
    "The doji is left alone on an island, 'abandoned'. Sellers had one last panic, then buyers rushed in. Very rare.",
    "Buy above candle three. Stop under the doji.",
    dict(candles=DOWN_CTX + [[56, 57, 40, 42, 1], [34, 36, 31, 34.3, 1], [40, 56, 39, 54, 1]]))
add("belt-hold", "Belt Hold", "candle", ["Bullish Belt Hold"], ["Bearish Belt Hold"],
    "After a fall, a long green candle that opens at its very low and climbs all day.",
    "Buyers grabbed the market by the belt at the open and never let go.",
    "Buy above it. Stop under its low.",
    dict(candles=DOWN_CTX + [[44, 64, 44, 62, 1]]))
add("tasuki", "Tasuki Gap", "candle", ["Upside Tasuki Gap"], ["Downside Tasuki Gap"],
    "Two green candles with a gap between them, then a red candle that partly fills the gap but doesn't close it.",
    "A small pullback that couldn't fill the hole, so the uptrend is still in charge.",
    "Buy above the red candle. Stop under the gap.",
    dict(candles=[[20, 24, 18, 22, 0], [22, 40, 21, 39, 1], [46, 62, 45, 60, 1], [56, 57, 42, 44, 1]]))
add("counterattack", "Counterattack", "candle", ["Bullish Counterattack"], ["Bearish Counterattack"],
    "A big red candle, then a big green candle that opens much lower but closes right at the red candle's close.",
    "Sellers attacked, buyers counterattacked and fought all the way back to even.",
    "Buy above the green candle. Stop under it.",
    dict(candles=DOWN_CTX + [[58, 59, 42, 44, 1], [30, 46, 29, 44, 1]]))

# ============================================================ SETUPS (indicators & price action)
P_UP = [[0, 40], [10, 34], [20, 30], [30, 32], [40, 40], [50, 46], [60, 56], [70, 62], [80, 72], [90, 78], [100, 86]]
add("golden-cross", "Golden Cross / Death Cross", "setup", ["Golden Cross (50/200)"], ["Death Cross (50/200)"],
    "The 50-day average price line crosses ABOVE the 200-day average price line.",
    "The 50-day line is the recent mood; the 200-day line is the long-term mood. When recent mood beats long-term mood, a new uptrend may be starting.",
    "Long-term buy signal. On your daily charts it's one of the best (A grade). Stop 2 ATR under price.",
    dict(path=P_UP, ma=[[[[0, 50], [20, 42], [40, 40], [55, 47], [70, 56], [100, 72]], "g", "50-day"],
                        [[[0, 58], [30, 52], [55, 48], [80, 52], [100, 58]], "y", "200-day"]], arrow=[58, 54, "up"]))
add("ema-cross", "EMA 9/21 Cross", "setup", ["EMA 9/21 Bull Cross"], ["EMA 9/21 Bear Cross"],
    "A fast average line (9 bars) crosses above a slower one (21 bars).",
    "Like a fast runner passing a slower runner. Short-term momentum just turned up.",
    "Short-term buy. Stop under the last few lows.",
    dict(path=P_UP, ma=[[[[0, 44], [25, 32], [45, 40], [70, 60], [100, 82]], "g", "9 EMA"],
                        [[[0, 50], [30, 40], [50, 42], [75, 54], [100, 72]], "y", "21 EMA"]], arrow=[46, 46, "up"]))
add("macd-cross", "MACD Signal Cross", "setup", ["MACD Bull Cross (below 0)"], ["MACD Bear Cross (above 0)"],
    "The MACD line (momentum) crosses above its signal line while both are below zero.",
    "Momentum was negative but just turned the corner, like a swing reaching the bottom and starting back up.",
    "Buy signal; best on the weekly chart. Stop 2 ATR below.",
    dict(path=P_UP, arrow=[42, 46, "up"],
         panel=dict(lines=[[[[0, 50], [20, 20], [40, 30], [60, 50], [100, 70]], "g", "MACD"],
                           [[[0, 56], [20, 30], [40, 26], [60, 40], [100, 62]], "y", "signal"]], levels=[[50, "0"]])))
add("macd-zero", "MACD Zero-Line Cross", "setup", ["MACD Zero-Line Cross ↑"], ["MACD Zero-Line Cross ↓"],
    "The MACD line crosses from below zero to above zero.",
    "The short-term average just moved above the longer one. Momentum officially flipped to positive.",
    "Trend-confirmation buy. Strong on weekly charts.",
    dict(path=P_UP, arrow=[56, 52, "up"],
         panel=dict(lines=[[[[0, 30], [20, 20], [40, 35], [55, 50], [80, 66], [100, 74]], "g", "MACD"]], levels=[[50, "0"]])))
add("rsi-levels", "RSI Oversold Reclaim / Overbought Rejection", "setup",
    ["RSI Oversold Reclaim (30)"], ["RSI Overbought Rejection (70)"],
    "RSI (a 0-100 score of how fast price moved) dips below 30, then climbs back above 30.",
    "Below 30 means price fell too fast, like a rubber band stretched too far. Climbing back over 30 means it's snapping back.",
    "Buy on the cross back above 30. Stop under recent lows.",
    dict(path=[[0, 80], [20, 60], [40, 32], [52, 24], [62, 34], [80, 52], [100, 64]], arrow=[64, 38, "up"],
         panel=dict(lines=[[[[0, 60], [20, 44], [40, 22], [52, 14], [62, 34], [80, 52], [100, 60]], "p", "RSI"]],
                    levels=[[30, "30"], [70, "70"]])))
add("bb-squeeze", "Bollinger Squeeze Breakout", "setup", ["Bollinger Squeeze Breakout ↑"], ["Bollinger Squeeze Breakdown ↓"],
    "The Bollinger Bands (lines that hug price) pinch very tight, then price bursts outside them.",
    "Calm before the storm. When the market gets super quiet, a big move usually follows.",
    "Buy when price closes above the upper band after a squeeze. Stop at the middle band. Great on the weekly chart.",
    dict(path=[[0, 50], [10, 62], [20, 40], [30, 54], [40, 48], [50, 52], [60, 50], [70, 54], [80, 72], [92, 88]],
         ma=[[[[0, 76], [20, 68], [40, 58], [60, 56], [76, 60], [92, 92]], "y", "upper"],
             [[[0, 24], [20, 32], [40, 42], [60, 45], [76, 44], [92, 46]], "y", "lower"]], arrow=[82, 76, "up"]))
add("ttm", "TTM Squeeze Fire", "setup", ["TTM Squeeze Fire ↑"], ["TTM Squeeze Fire ↓"],
    "The same idea as the Bollinger squeeze, using a second set of bands (Keltner). When the squeeze ends, it 'fires'.",
    "A coiled spring being let go. The direction of momentum tells you which way it's likely to jump.",
    "Trade in the momentum direction. Stop under the last few lows. You already use this on Webull.",
    dict(path=[[0, 50], [15, 56], [30, 48], [45, 52], [55, 50], [65, 54], [80, 74], [94, 88]], arrow=[70, 62, "up"],
         panel=dict(lines=[[[[0, 46], [30, 48], [55, 50], [65, 58], [80, 74], [100, 84]], "g", "momentum"]], levels=[[50, "0"]])))
add("nr7", "NR7 Breakout", "setup", ["NR7 Breakout ↑"], ["NR7 Breakdown ↓"],
    "NR7 = the Narrowest Range of the last 7 bars. The smallest, quietest candle in a week.",
    "Like the hush in a classroom right before the bell rings. A big move often comes next.",
    "Buy if the next bar closes above the quiet bar's high. Stop under its low.",
    dict(candles=[[40, 60, 36, 56, 0], [56, 62, 44, 48, 0], [48, 58, 40, 54, 0], [54, 60, 46, 50, 0],
                  [50, 56, 44, 52, 0], [52, 55, 47, 49, 0], [49, 51, 48, 50, 1], [50, 66, 49, 64, 1]]))
add("inside-bar", "Inside Bar Breakout", "setup", ["Inside Bar Breakout ↑"], ["Inside Bar Breakdown ↓"],
    "A candle whose whole range fits inside the candle before it, then price breaks out of it.",
    "A pause where nobody wants to commit. Whoever breaks the tiny range first usually wins the next move.",
    "Buy on a close above the inside bar's high. Stop under its low.",
    dict(candles=[[30, 40, 28, 38, 0], [38, 60, 34, 56, 0], [54, 56, 44, 48, 1], [48, 64, 47, 62, 1]]))
add("52w", "52-Week (or 20-Day) High Breakout", "setup",
    ["52-Week High Breakout", "20-Day High Breakout"], ["52-Week Low Breakdown", "20-Day Low Breakdown"],
    "Price closes at its highest point in a whole year (20 days on the hourly chart).",
    "Everyone who bought in the last year is now making money, so nobody is desperate to sell. Strong things tend to stay strong.",
    "Buy the breakout. Stop 2 ATR under. Strong on daily AND weekly charts.",
    dict(path=[[0, 40], [12, 66], [24, 44], [36, 68], [48, 50], [60, 67], [72, 56], [84, 82], [96, 90]],
         lines=[[8, 68, 92, 68, "dash", "y", "52-week high"]], arrow=[84, 74, "up"]))
add("pullback-50", "Pullback to 50 SMA (uptrend) / Rally to 50 SMA (downtrend)", "setup",
    ["Pullback to 50 SMA (uptrend)"], ["Rally to 50 SMA (downtrend)"],
    "In an uptrend, price dips down to touch the 50-day average line and bounces off it.",
    "The 50-day line acts like a trampoline in a healthy uptrend. Big investors often buy there.",
    "Buy the bounce. Stop 1 ATR under the low. One of the better buy-and-hold entries on weekly charts.",
    dict(path=[[0, 30], [14, 50], [28, 66], [40, 74], [52, 62], [60, 56], [68, 66], [84, 84], [96, 92]],
         ma=[[[[0, 22], [30, 40], [60, 55], [100, 72]], "y", "50 SMA"]], arrow=[62, 60, "up"]))
add("ema20", "20 EMA Pullback / Rejection (trend)", "setup", ["20 EMA Pullback (trend)"], ["20 EMA Rejection (trend)"],
    "In a strong uptrend (9 above 20 above 50 EMA), price dips to the 20 EMA and closes back above it.",
    "Same trampoline idea but faster. The 20 EMA is where short-term traders 'buy the dip'.",
    "Buy above the bounce bar. Stop just under its low.",
    dict(path=[[0, 20], [20, 40], [36, 60], [46, 54], [52, 50], [60, 60], [80, 80], [96, 90]],
         ma=[[[[0, 14], [30, 40], [52, 50], [100, 80]], "y", "20 EMA"]], arrow=[56, 54, "up"]))
add("lost50", "Lost 50 SMA after 20+ bars above", "setup", [], ["Lost 50 SMA after 20+ bars above"],
    "After a long time above the 50-day line, price finally closes below it.",
    "The trampoline broke. It can be the start of a bigger pullback, but on your tickers shorting it has lost money, so use it as a warning, not a short.",
    "Warning sign for longs. Tighten stops or take some profit.",
    dict(path=[[0, 30], [20, 56], [40, 72], [55, 76], [65, 66], [75, 52], [90, 44]],
         ma=[[[[0, 26], [40, 52], [70, 60], [100, 64]], "y", "50 SMA"]], arrow=[76, 50, "down"]))
add("gaps", "Gap Fill vs. Gap & Go", "setup", ["Gap Down → Fill", "Gap Up → Go"], ["Gap Up → Fill", "Gap Down → Go"],
    "Price opens much higher (or lower) than where it closed the day before, leaving a 'gap' on the chart.",
    "Some gaps get 'filled' (price comes back to yesterday's close) and some keep running. The scanner tests both so you can see which one wins on each stock.",
    "Fill trade: aim for yesterday's close. Go trade: ride the gap direction with a stop at yesterday's close.",
    dict(candles=[[40, 46, 38, 44, 0], [44, 48, 40, 42, 0], [42, 46, 39, 45, 0], [58, 62, 50, 52, 1], [52, 54, 44, 46, 1]],
         lines=[[0, 45, 100, 45, "dash", "y", "yesterday's close"]]),
    "Gap Down → Fill (buy, expect it to close the gap up) has been the winner on your daily charts.")
add("orb", "Opening Range Breakout (hourly)", "setup", ["Opening Range Breakout ↑"], ["Opening Range Breakdown ↓"],
    "The first hour of the trading day sets a high and a low (the 'opening range'). Later, price breaks out of it.",
    "The first hour is everyone arguing about the price. Once one side wins the argument, price often keeps going that way for the rest of the day.",
    "Day trade. Buy the break above the first-hour high. Stop at the first-hour low. Exit by the close.",
    dict(candles=[[50, 60, 42, 56, 1], [56, 58, 48, 52, 0], [52, 58, 50, 56, 0], [56, 68, 55, 66, 1], [66, 76, 64, 74, 0]],
         lines=[[0, 60, 100, 60, "dash", "y", "first-hour high"], [0, 42, 100, 42, "dash", "w", "first-hour low"]]))
add("vwap", "VWAP Reclaim / Rejection (hourly)", "setup", ["VWAP Reclaim"], ["VWAP Rejection"],
    "VWAP is the average price everyone paid today, weighted by how many shares traded. A reclaim is when price closes back above it after 3+ bars below.",
    "VWAP is like the day's 'fair price'. Getting back above it means buyers are winning the day again.",
    "Day trade. Buy the reclaim, stop under the recent lows, exit by the close.",
    dict(path=[[0, 60], [15, 48], [30, 40], [45, 38], [58, 46], [66, 56], [80, 64], [96, 70]],
         ma=[[[[0, 56], [50, 50], [100, 52]], "p", "VWAP"]], arrow=[66, 58, "up"]))
