"""Backtest: does the scorecard's score say anything about forward returns?

For every ticker and every session after a one-year warm-up, the score is computed from the data available
at that close and compared with the return over the next 20 and 60 sessions, raw and relative to SPY.

    python backtest.py                                  # all variants, default basket, 10 years
    python backtest.py --variant baseline --variant overbought-penalty
    python backtest.py --tickers AAPL MSFT --years 5 --output BACKTEST.md

Prices are cached in data_cache/ for a day. No Streamlit here; the scoring comes straight from scorecard.py.
"""
import argparse
import contextlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

import scorecard
from scorecard import Signal, compute_indicators, metrics_history, normalized_score, prepare_prices

BENCHMARK = 'SPY'
HORIZONS = (20, 60)
CACHE_DIR = Path(__file__).parent / 'data_cache'
CACHE_MAX_AGE = timedelta(days=1)

DEFAULT_TICKERS = [
    # Large US names across sectors, including several that lagged the market over the decade
    'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META', 'NVDA', 'JPM', 'JNJ', 'V', 'PG',
    'XOM', 'UNH', 'HD', 'KO', 'PEP', 'MRK', 'CVX', 'WMT', 'DIS', 'CSCO',
    'INTC', 'IBM', 'BA', 'CAT', 'MMM', 'GE', 'T', 'VZ', 'PFE', 'NKE',
    # Index ETFs (the benchmark itself is left out of the sample)
    'QQQ', 'IWM',
    # Non-US listings, in local currency
    'NESN.SW', 'SAP.DE', 'VOD.L',
]

SIGNAL_NAMES = {
    ('trend', 0): 'Trend direction (price vs MA50 vs MA200)',
    ('trend', 1): 'Momentum (20-day return and its change)',
    ('trend', 2): 'Consistency (20-day win rate)',
    ('breadth', 0): 'Volume trend (20d vs prior 20d)',
    ('sentiment', 0): '50-day performance',
    ('sentiment', 1): '52-week position',
    ('volatility', 0): 'Volatility regime (z-score)',
    ('liquidity', 0): 'Liquidity stress',
}

SCORE_BUCKETS = [  # same cut points as scorecard.recommendation()
    ('-5 to -3', -np.inf, -3), ('-3 to -1', -3, -1), ('-1 to +1', -1, 1), ('+1 to +3', 1, 3), ('+3 to +5', 3, np.inf),
]


# ---------------------------------------------------------------------------------------------------------------
# Data


def load_history(ticker, start, end):
    """Daily auto-adjusted prices for `ticker`, from the cache when it is less than a day old."""
    import yfinance as yf

    path = CACHE_DIR / f"{ticker}.parquet"
    raw = None
    if path.exists() and datetime.now() - datetime.fromtimestamp(path.stat().st_mtime) < CACHE_MAX_AGE:
        raw = pd.read_parquet(path)
        # A cache written by a shorter run does not cover this one (a week of slack for holidays)
        if raw.empty or raw.index.min() > pd.Timestamp(start) + timedelta(days=7):
            raw = None
    if raw is None:
        raw = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
        if raw.empty:
            raise LookupError(f"No price data for {ticker}")
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        CACHE_DIR.mkdir(exist_ok=True)
        raw.to_parquet(path)
    df = prepare_prices(raw)
    return df[(df['date'] >= pd.Timestamp(start)) & (df['date'] < pd.Timestamp(end))].reset_index(drop=True)


def forward_returns(df, horizon):
    return df['close'].shift(-horizon) / df['close'] - 1


def benchmark_forward_returns(dates, bench, horizon):
    """SPY's return from each of `dates` to the date `horizon` of the ticker's own sessions later."""
    bench_close = bench.set_index('date')['close']
    start = bench_close.reindex(dates, method='ffill').to_numpy()
    end_dates = pd.Series(dates).shift(-horizon)
    end = bench_close.reindex(end_dates.fillna(dates.iloc[-1]), method='ffill').to_numpy()
    out = end / start - 1
    out[end_dates.isna().to_numpy()] = np.nan
    return out


def build_panel(tickers, start, end, verbose=True):
    """One row per ticker and session: the metrics the scorecard sees, plus forward returns."""
    bench = load_history(BENCHMARK, start - timedelta(days=10), end)
    frames = []
    for ticker in tickers:
        try:
            df = load_history(ticker, start, end)
        except Exception as e:  # one bad ticker should not stop the run
            print(f"  skipping {ticker}: {e}")
            continue
        if len(df) <= scorecard.WARMUP_SESSIONS + max(HORIZONS):
            print(f"  skipping {ticker}: only {len(df)} sessions")
            continue
        df = compute_indicators(df)
        # Kept so the old one-session momentum rule can be replayed as a variant
        df['Momentum_Change_1d'] = df['ROC_20d'].diff()
        rows = pd.DataFrame(metrics_history(df))
        idx = slice(scorecard.WARMUP_SESSIONS, None)
        rows['momentum_change_1d'] = df['Momentum_Change_1d'].iloc[idx].to_numpy()
        rows['ticker'] = ticker
        for h in HORIZONS:
            rows[f'fwd_{h}'] = forward_returns(df, h).iloc[idx].to_numpy()
            bench_fwd = benchmark_forward_returns(df['date'], bench, h)[scorecard.WARMUP_SESSIONS:]
            rows[f'excess_{h}'] = rows[f'fwd_{h}'] - bench_fwd
        frames.append(rows)
        if verbose:
            print(f"  {ticker}: {len(rows)} sessions from {rows['as_of'].iloc[0]:%Y-%m-%d}")
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------------------------------------------
# Scoring variants


def overbought_oversold_score(m):
    """The original 52-week position rule: -1 above 75% of the range, +1 below 25%."""
    position = m['price_position']
    return -1 if position > 75 else (1 if position < 25 else 0)


def with_position_signal(rule):
    """A sentiment block whose context-only 52-week position signal is scored by `rule(m)` instead."""
    def sentiment(m):
        block = scorecard.sentiment_block(m)
        block.signals[1] = Signal(rule(m), "scored 52-week position")
        return block
    return sentiment


def graded_position_score(m):
    """Sliding scale: +1 at the 52-week low, 0 in the middle, -1 at the high."""
    return float(np.clip((50 - m['price_position']) / 50, -1, 1))


def overbought_when_fading_score(m):
    """Original rule, but a high position only counts against when 20-day momentum is negative or slipping."""
    score = overbought_oversold_score(m)
    return 0 if score < 0 and m['roc_20'] >= 0 and m['momentum_change'] >= 0 else score


@dataclass
class Variant:
    description: str
    sentiment: Callable = None  # replaces scorecard.sentiment_block
    constants: dict = field(default_factory=dict)  # scorecard module constants to override
    metrics: Callable = None  # rewrites the metrics dict before scoring

    def score(self, m, pe_ratio=None):
        if self.metrics:
            m = self.metrics(m)
        blocks = scorecard.score_blocks(m, pe_ratio)
        if self.sentiment:
            blocks = [self.sentiment(m) if b.key == 'sentiment' else b for b in blocks]
        return blocks

    @contextlib.contextmanager
    def applied(self):
        saved = {k: getattr(scorecard, k) for k in self.constants}
        for k, v in self.constants.items():
            setattr(scorecard, k, v)
        try:
            yield
        finally:
            for k, v in saved.items():
                setattr(scorecard, k, v)


VARIANTS = {
    'baseline': Variant("Current scorecard.py rules (52-week position shown for context only, not scored)"),
    'overbought-penalty': Variant("Original rule: -1 above 75% of the 52-week range, +1 below 25%",
                                  sentiment=with_position_signal(overbought_oversold_score)),
    'graded-position': Variant("52-week position on a sliding scale instead of the 25%/75% cut-offs",
                               sentiment=with_position_signal(graded_position_score)),
    'fading-overbought': Variant("Original rule, but overbought only counts when 20-day momentum is negative or "
                                 "slipping", sentiment=with_position_signal(overbought_when_fading_score)),
    'high-is-bullish': Variant("Original rule reversed: near the 52-week high counts for, near the low against",
                               sentiment=with_position_signal(lambda m: -overbought_oversold_score(m))),
    'old-bands': Variant("Earlier bands: no trend dead band, 60%/40% win rate, one-session momentum change",
                         constants={'TREND_DEAD_BAND': 0.0, 'WIN_RATE_HIGH': 60.0, 'WIN_RATE_LOW': 40.0},
                         metrics=lambda m: {**m, 'momentum_change': m['momentum_change_1d']}),
}


def score_panel(panel, variant):
    """Normalized score and each signal's score for every row of the panel."""
    records = panel.to_dict('records')
    scores, signals = [], []
    with variant.applied():
        for m in records:
            blocks = variant.score(m)
            scores.append(normalized_score(blocks))
            signals.append({SIGNAL_NAMES.get((b.key, i), f"{b.key} {i}"): s.score
                            for b in blocks for i, s in enumerate(b.signals)
                            if s.available and (s.max_up or s.max_down)})  # skip context-only signals
    out = pd.DataFrame(signals, index=panel.index)
    out['score'] = scores
    return out


# ---------------------------------------------------------------------------------------------------------------
# Reporting


def pct(x):
    return "" if pd.isna(x) else f"{x * 100:+.2f}%"


def summarize(returns, years):
    returns = returns.dropna()
    by_year = returns.groupby(years.loc[returns.index]).mean()
    return {
        'mean': pct(returns.mean()),
        'median': pct(returns.median()),
        'hit rate': f"{(returns > 0).mean() * 100:.0f}%" if len(returns) else "",
        'years > 0': f"{(by_year > 0).sum()}/{len(by_year)}" if len(by_year) else "",
        'n': f"{len(returns):,}",
    }


def rank_corr(a, b):
    return a.rank().corr(b.rank())


def variant_summary(panel, scores):
    """How well a variant's score lines up with forward excess returns, in one row."""
    row = {}
    for h in HORIZONS:
        col = panel[f'excess_{h}']
        ok = col.notna()
        row[f'rank corr. {h}d'] = f"{rank_corr(scores.loc[ok, 'score'], col[ok]):+.3f}"
    # Rank correlation across tickers on each date, so market-wide swings do not dominate
    ok = panel['excess_60'].notna()
    daily = pd.DataFrame({'date': panel.loc[ok, 'as_of'], 'score': scores.loc[ok, 'score'], 'ret': panel.loc[ok, 'excess_60']})
    daily[['score', 'ret']] = daily.groupby('date')[['score', 'ret']].rank()
    per_date = daily.groupby('date')[['score', 'ret']].corr().xs('score', level=1)['ret']
    per_year = per_date.groupby(per_date.index.year).mean()
    row['same-day rank corr. 60d'] = f"{per_date.mean():+.3f}"
    row['years > 0'] = f"{(per_year > 0).sum()}/{len(per_year)}"
    high, low = scores['score'] >= 1, scores['score'] < -1
    row['score ≥ +1 minus < -1, 60d'] = pct(panel.loc[high, 'excess_60'].mean() - panel.loc[low, 'excess_60'].mean())
    row['sessions ≥ +1'] = f"{high.mean() * 100:.0f}%"
    return row


def markdown_table(rows, columns):
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
    lines += ["| " + " | ".join(str(r.get(c, "")) for c in columns) + " |" for r in rows]
    return "\n".join(lines)


def score_bucket_table(panel, scores, column):
    years = panel['as_of'].dt.year
    rows = []
    for label, lo, hi in SCORE_BUCKETS:
        mask = (scores['score'] >= lo) & (scores['score'] < hi)
        rows.append({'score': label, **summarize(panel.loc[mask, column], years)})
    rows.append({'score': '**all**', **summarize(panel[column], years)})
    return markdown_table(rows, ['score', 'mean', 'median', 'hit rate', 'years > 0', 'n'])


def signal_table(panel, scores, column):
    years = panel['as_of'].dt.year
    rows = []
    for name in [c for c in scores.columns if c != 'score']:
        for value in sorted(scores[name].dropna().unique()):
            if isinstance(value, float) and not value.is_integer():
                continue  # graded signals are summarized by the bucket tables instead
            mask = scores[name] == value
            rows.append({'signal': name, 'value': f"{int(value):+d}" if value else "0",
                         **summarize(panel.loc[mask, column], years)})
    return markdown_table(rows, ['signal', 'value', 'mean', 'hit rate', 'years > 0', 'n'])


def metric_bucket_table(panel, column):
    """Forward excess return by raw metric range, to judge where a threshold belongs."""
    years = panel['as_of'].dt.year
    gap50 = (panel['price'] / panel['ma50'] - 1) * 100
    gap200 = (panel['ma50'] / panel['ma200'] - 1) * 100
    trend_gap = pd.Series(np.where(np.sign(gap50) == np.sign(gap200),
                                   np.sign(gap50) * np.minimum(gap50.abs(), gap200.abs()), 0.0), index=panel.index)
    specs = [
        ('52-week position (%)', panel['price_position'], [0, 10, 25, 40, 60, 75, 90, 100.01]),
        ('Win rate, 20d (%)', panel['win_rate'], [0, 30, 35, 40, 45, 55, 60, 65, 70, 100.01]),
        ('Trend gap (%, signed; 0 = not stacked)', trend_gap, [-np.inf, -5, -2, -1, -0.001, 0.001, 1, 2, 5, np.inf]),
        ('Momentum change, 5 sessions (pts)', panel['momentum_change'], [-np.inf, -5, -2, 0, 2, 5, np.inf]),
        ('Momentum change, 1 session (pts)', panel['momentum_change_1d'], [-np.inf, -2, -0.5, 0, 0.5, 2, np.inf]),
    ]
    out = []
    for title, values, edges in specs:
        buckets = pd.cut(values, edges, right=False)
        rows = [{'range': str(b), **summarize(panel.loc[buckets == b, column], years)} for b in buckets.cat.categories]
        out.append(f"**{title}**\n\n" + markdown_table(rows, ['range', 'mean', 'hit rate', 'years > 0', 'n']))
    return "\n\n".join(out)


def report(panel, variants):
    tickers = panel['ticker'].unique()
    parts = [
        f"# Backtest results\n\nGenerated {datetime.now():%Y-%m-%d} by `backtest.py`.\n",
        f"- Sample: {len(tickers)} tickers ({', '.join(tickers)}), "
        f"{panel['as_of'].min():%Y-%m-%d} to {panel['as_of'].max():%Y-%m-%d}, {len(panel):,} ticker-sessions.",
        f"- Scores use only data up to each session's close; forward returns run from that close. "
        f"Excess return = ticker return minus {BENCHMARK} return over the same dates.",
        "- Valuation is left out: yfinance has no historical P/E, so every row is scored as if P/E were unavailable.",
        "- Caveats: the basket is today's large caps, so it carries survivorship bias (\"all\" rows beat SPY on "
        "average for that reason; compare buckets with the \"all\" row, not with zero). Non-US returns are in local "
        "currency. Consecutive sessions share most of their forward window, so the effective sample is far smaller "
        "than n; \"years > 0\" counts calendar years in which the bucket's mean was positive, as a rough "
        "consistency check.",
    ]
    all_scores = {name: score_panel(panel, VARIANTS[name]) for name in variants}
    summary = [{'variant': f"`{name}`", **variant_summary(panel, scores)} for name, scores in all_scores.items()]
    parts.append("\n## Variant comparison\n\n"
                 "Rank correlation runs from -1 to +1; 0 means the score says nothing about the forward excess "
                 "return. \"Same-day\" ranks tickers against each other on each date and averages, so a market-wide "
                 "rally or crash does not dominate; \"years > 0\" counts calendar years where that average was "
                 "positive.\n\n"
                 + markdown_table(summary, list(summary[0])))
    for name, scores in all_scores.items():
        variant = VARIANTS[name]
        parts.append(f"\n## Variant `{name}`\n\n{variant.description}.\n")
        for h in HORIZONS:
            parts.append(f"\n### Score bucket vs {h}-session return\n\nRaw:\n\n"
                         + score_bucket_table(panel, scores, f'fwd_{h}')
                         + f"\n\nExcess over {BENCHMARK}:\n\n" + score_bucket_table(panel, scores, f'excess_{h}'))
        parts.append(f"\n### Each signal vs 60-session excess return\n\n" + signal_table(panel, scores, 'excess_60'))
    parts.append("\n## Raw metrics vs 60-session excess return\n\n"
                 "Independent of any variant; shows where thresholds would sit.\n\n" + metric_bucket_table(panel, 'excess_60'))
    return "\n".join(parts) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--tickers', nargs='+', default=DEFAULT_TICKERS)
    parser.add_argument('--years', type=float, default=10)
    parser.add_argument('--variant', action='append', choices=list(VARIANTS),
                        help="repeat to compare several; default: all")
    parser.add_argument('--output', help="write the markdown report here instead of stdout")
    args = parser.parse_args()

    end = pd.Timestamp(datetime.now().date())  # today's unfinished session is left out
    # The warm-up year comes before the scored period
    start = end - timedelta(days=int(args.years * 365.25) + 380)
    tickers = [t.upper() for t in args.tickers if t.upper() != BENCHMARK]
    print(f"Loading {len(tickers)} tickers...")
    panel = build_panel(tickers, start, end)
    text = report(panel, args.variant or list(VARIANTS))
    if args.output:
        Path(args.output).write_text(text)
        print(f"Wrote {args.output}")
    else:
        print(text)


if __name__ == '__main__':
    main()
