# Backtest

Does the score say anything about what a stock does next? `backtest.py` scores every trading session of
35 tickers over 10 years, using only data available at that day's close, and compares the score with the
return over the next 20 and 60 sessions relative to SPY. Run `python backtest.py` to reproduce (about a
minute; prices are cached in `data_cache/` for a day).

## Summary (generated 2026-10-06)

**No meaningful edge.** The rank correlation between the score and the next 60 sessions' excess return is
+0.02 (0 = no relationship, 1 = perfect). Sessions scoring +3 or higher beat SPY by 0.97% on average over
the next 60 sessions, against 0.14% for all sessions. But their median excess return was about zero
(-0.03%), and the lower buckets are not ordered. Treat the score as a summary of the chart, not a forecast.

What the backtest settled:

- **52-week position is no longer scored.** The old rule (-1 above 75% of the range, +1 below 25%)
  cancelled the uptrend signal in nearly every rising stock. Sessions near the 52-week high were followed
  by the *best* excess returns (+1.00%, 9 of 11 years above zero). Of the candidate fixes, leaving
  the position out of the score (`baseline`) lined up best with forward returns. A graded scale and an
  "only when momentum fades" rule did not help. The app still shows the position, for context.
- **Trend dead band: 1%.** Trend direction is the one signal that holds up: +1 sessions averaged +0.93%
  excess (against +0.14% for all sessions), positive in 10 of 11 years. Without a band, price was called
  a downtrend 0.01% below its average. At 2% or wider, the downtrend side started pointing the wrong way.
- **Win rate band: 65% / 35%.** No band tried (60/40, 65/35, 70/30) showed an edge in either direction;
  65/35 is kept because it fires less often, so it adds less noise.
- **Momentum lookback: 5 sessions.** Neither 1 nor 5 sessions showed an edge. Five is kept because it
  stops the signal flipping on a single day.

The band comparisons come from one-off runs with the `TREND_DEAD_BAND` and `WIN_RATE_*` constants in
`scorecard.py` changed; the "Raw metrics" tables below show the same pattern.

What it found but did not change (left for a future decision):

- "Weak Momentum" / "Momentum Fading" (-1) sessions were followed by *above*-average excess returns
  (+0.51%, positive in 9 of 11 years), the opposite of what the signal assumes (short-term reversal).
- 50-day performance scored well at both extremes (+1.06% after -1, +1.29% after +1). This more likely
  reflects volatile stocks moving more in a survivorship-biased basket than a real signal.
- Volume trend, volatility and liquidity showed no consistent relationship with forward returns.
- Without a P/E (every backtest row; most ETFs in the app), at most five signals can be positive, so a
  single favorable signal is enough for "BUY / HOLD" (+1.0). 40% of backtest sessions scored +1 or higher.

Limitations: the basket is today's large caps (survivorship bias); non-US tickers are measured in local
currency against SPY in dollars; consecutive sessions share most of their 60-session window, so the
effective sample is far smaller than the row counts suggest.

---

## Generated tables

Generated 2026-10-06 by `backtest.py`.

- Sample: 35 tickers (AAPL, MSFT, AMZN, GOOGL, META, NVDA, JPM, JNJ, V, PG, XOM, UNH, HD, KO, PEP, MRK, CVX, WMT, DIS, CSCO, INTC, IBM, BA, CAT, MMM, GE, T, VZ, PFE, NKE, QQQ, IWM, NESN.SW, SAP.DE, VOD.L), 2016-09-16 to 2026-10-05, 88,348 ticker-sessions.
- Scores use only data up to each session's close; forward returns run from that close. Excess return = ticker return minus SPY return over the same dates.
- Valuation is left out: yfinance has no historical P/E, so every row is scored as if P/E were unavailable.
- Caveats: the basket is today's large caps, so it carries survivorship bias ("all" rows beat SPY on average for that reason; compare buckets with the "all" row, not with zero). Non-US returns are in local currency. Consecutive sessions share most of their forward window, so the effective sample is far smaller than n; "years > 0" counts calendar years in which the bucket's mean was positive, as a rough consistency check.

### Variant comparison

Rank correlation runs from -1 to +1; 0 means the score says nothing about the forward excess return. "Same-day" ranks tickers against each other on each date and averages, so a market-wide rally or crash does not dominate; "years > 0" counts calendar years where that average was positive.

| variant | rank corr. 20d | rank corr. 60d | same-day rank corr. 60d | years > 0 | score ≥ +1 minus < -1, 60d | sessions ≥ +1 |
|---|---|---|---|---|---|---|
| `baseline` | +0.009 | +0.018 | +0.018 | 5/11 | +0.27% | 40% |
| `overbought-penalty` | +0.003 | +0.007 | -0.001 | 5/11 | +0.61% | 12% |
| `graded-position` | +0.003 | +0.007 | -0.000 | 5/11 | +0.39% | 17% |
| `fading-overbought` | +0.003 | +0.010 | +0.004 | 5/11 | +0.62% | 18% |
| `high-is-bullish` | +0.013 | +0.026 | +0.028 | 5/11 | +0.55% | 33% |
| `old-bands` | +0.011 | +0.020 | +0.023 | 5/11 | +0.24% | 46% |

### Variant `baseline`

Current scorecard.py rules (52-week position shown for context only, not scored).


#### Score bucket vs 20-session return

Raw:

| score | mean | median | hit rate | years > 0 | n |
|---|---|---|---|---|---|
| -5 to -3 | +2.61% | +3.24% | 66% | 10/11 | 469 |
| -3 to -1 | +2.16% | +1.72% | 60% | 11/11 | 15,860 |
| -1 to +1 | +1.09% | +1.03% | 57% | 10/11 | 36,029 |
| +1 to +3 | +1.05% | +1.21% | 58% | 9/11 | 26,863 |
| +3 to +5 | +1.14% | +1.29% | 58% | 8/11 | 8,427 |
| **all** | +1.28% | +1.24% | 58% | 9/11 | 87,648 |

Excess over SPY:

| score | mean | median | hit rate | years > 0 | n |
|---|---|---|---|---|---|
| -5 to -3 | -0.38% | -0.10% | 49% | 6/11 | 469 |
| -3 to -1 | +0.20% | -0.12% | 49% | 6/11 | 15,860 |
| -1 to +1 | -0.09% | -0.27% | 48% | 5/11 | 36,029 |
| +1 to +3 | +0.03% | -0.02% | 50% | 6/11 | 26,863 |
| +3 to +5 | +0.31% | +0.01% | 50% | 9/11 | 8,427 |
| **all** | +0.04% | -0.13% | 49% | 5/11 | 87,648 |

#### Score bucket vs 60-session return

Raw:

| score | mean | median | hit rate | years > 0 | n |
|---|---|---|---|---|---|
| -5 to -3 | +7.09% | +4.58% | 64% | 10/11 | 458 |
| -3 to -1 | +5.18% | +4.36% | 63% | 11/11 | 15,518 |
| -1 to +1 | +3.59% | +3.35% | 62% | 10/11 | 35,453 |
| +1 to +3 | +3.48% | +3.06% | 62% | 9/11 | 26,497 |
| +3 to +5 | +3.79% | +2.83% | 61% | 10/11 | 8,322 |
| **all** | +3.88% | +3.36% | 62% | 10/11 | 86,248 |

Excess over SPY:

| score | mean | median | hit rate | years > 0 | n |
|---|---|---|---|---|---|
| -5 to -3 | +0.07% | -0.23% | 50% | 5/11 | 458 |
| -3 to -1 | +0.17% | -0.49% | 48% | 6/11 | 15,518 |
| -1 to +1 | -0.15% | -0.56% | 48% | 5/11 | 35,453 |
| +1 to +3 | +0.27% | -0.31% | 49% | 7/11 | 26,497 |
| +3 to +5 | +0.97% | -0.03% | 50% | 8/11 | 8,322 |
| **all** | +0.14% | -0.41% | 48% | 6/11 | 86,248 |

#### Each signal vs 60-session excess return

| signal | value | mean | hit rate | years > 0 | n |
|---|---|---|---|---|---|
| Trend direction (price vs MA50 vs MA200) | -1 | -0.24% | 48% | 6/11 | 11,449 |
| Trend direction (price vs MA50 vs MA200) | 0 | -0.35% | 47% | 4/11 | 42,419 |
| Trend direction (price vs MA50 vs MA200) | +1 | +0.93% | 51% | 10/11 | 32,380 |
| Momentum (20-day return and its change) | -1 | +0.51% | 49% | 9/11 | 33,874 |
| Momentum (20-day return and its change) | 0 | -0.30% | 48% | 5/11 | 37,203 |
| Momentum (20-day return and its change) | +1 | +0.41% | 49% | 7/11 | 15,171 |
| Consistency (20-day win rate) | -1 | +0.35% | 50% | 6/11 | 2,891 |
| Consistency (20-day win rate) | 0 | +0.12% | 48% | 7/11 | 76,237 |
| Consistency (20-day win rate) | +1 | +0.30% | 50% | 4/11 | 7,120 |
| Volume trend (20d vs prior 20d) | -1 | +0.05% | 48% | 5/11 | 28,974 |
| Volume trend (20d vs prior 20d) | 0 | +0.06% | 48% | 6/11 | 21,825 |
| Volume trend (20d vs prior 20d) | +1 | +0.27% | 49% | 7/11 | 35,449 |
| 50-day performance | -1 | +1.06% | 51% | 8/11 | 9,217 |
| 50-day performance | 0 | -0.41% | 48% | 4/11 | 56,875 |
| 50-day performance | +1 | +1.29% | 50% | 8/11 | 20,156 |
| Volatility regime (z-score) | -1 | +0.44% | 50% | 5/11 | 13,245 |
| Volatility regime (z-score) | 0 | +0.09% | 48% | 5/11 | 73,003 |
| Liquidity stress | -1 | +0.72% | 48% | 7/11 | 2,908 |
| Liquidity stress | 0 | +0.12% | 48% | 5/11 | 83,340 |

### Raw metrics vs 60-session excess return

Independent of any variant; shows where thresholds would sit.

**52-week position (%)**

| range | mean | hit rate | years > 0 | n |
|---|---|---|---|---|
| [0.0, 10.0) | -0.47% | 48% | 5/11 | 4,483 |
| [10.0, 25.0) | +0.39% | 49% | 7/11 | 7,429 |
| [25.0, 40.0) | -0.59% | 46% | 3/11 | 7,697 |
| [40.0, 60.0) | -0.44% | 47% | 4/11 | 12,365 |
| [60.0, 75.0) | -0.22% | 46% | 4/11 | 12,826 |
| [75.0, 90.0) | +0.13% | 48% | 6/11 | 19,458 |
| [90.0, 100.01) | +1.00% | 52% | 9/11 | 21,990 |

**Win rate, 20d (%)**

| range | mean | hit rate | years > 0 | n |
|---|---|---|---|---|
| [0.0, 30.0) | +1.39% | 54% | 7/11 | 859 |
| [30.0, 35.0) | -0.09% | 48% | 3/11 | 2,032 |
| [35.0, 40.0) | -0.16% | 45% | 4/11 | 4,632 |
| [40.0, 45.0) | +0.34% | 49% | 7/11 | 8,423 |
| [45.0, 55.0) | +0.07% | 48% | 6/11 | 27,987 |
| [55.0, 60.0) | +0.01% | 47% | 7/11 | 15,078 |
| [60.0, 65.0) | +0.34% | 49% | 6/11 | 11,991 |
| [65.0, 70.0) | +0.12% | 49% | 6/11 | 8,126 |
| [70.0, 100.01) | +0.30% | 50% | 4/11 | 7,120 |

**Trend gap (%, signed; 0 = not stacked)**

| range | mean | hit rate | years > 0 | n |
|---|---|---|---|---|
| [-inf, -5.0) | +1.02% | 50% | 5/11 | 4,044 |
| [-5.0, -2.0) | -0.73% | 48% | 4/11 | 4,780 |
| [-2.0, -1.0) | -1.27% | 45% | 3/11 | 2,625 |
| [-1.0, -0.001) | -1.03% | 44% | 3/11 | 2,991 |
| [-0.001, 0.001) | -0.26% | 47% | 6/11 | 33,441 |
| [0.001, 1.0) | -0.50% | 46% | 4/11 | 5,987 |
| [1.0, 2.0) | -0.52% | 46% | 2/11 | 5,885 |
| [2.0, 5.0) | +0.24% | 50% | 6/11 | 14,509 |
| [5.0, inf) | +2.47% | 54% | 9/11 | 11,986 |

**Momentum change, 5 sessions (pts)**

| range | mean | hit rate | years > 0 | n |
|---|---|---|---|---|
| [-inf, -5.0) | +0.88% | 49% | 8/11 | 12,008 |
| [-5.0, -2.0) | +0.04% | 48% | 6/11 | 15,365 |
| [-2.0, 0.0) | -0.13% | 48% | 5/11 | 16,159 |
| [0.0, 2.0) | -0.09% | 48% | 6/11 | 15,840 |
| [2.0, 5.0) | -0.03% | 48% | 6/11 | 15,016 |
| [5.0, inf) | +0.46% | 48% | 7/11 | 11,860 |

**Momentum change, 1 session (pts)**

| range | mean | hit rate | years > 0 | n |
|---|---|---|---|---|
| [-inf, -2.0) | +0.65% | 49% | 8/11 | 12,880 |
| [-2.0, -0.5) | -0.03% | 48% | 6/11 | 20,491 |
| [-0.5, 0.0) | +0.08% | 49% | 4/11 | 9,848 |
| [0.0, 0.5) | -0.24% | 48% | 5/11 | 9,916 |
| [0.5, 2.0) | -0.04% | 48% | 5/11 | 20,272 |
| [2.0, inf) | +0.55% | 49% | 8/11 | 12,841 |
