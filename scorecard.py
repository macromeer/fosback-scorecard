"""Indicator calculations and scoring for the Fosback Market Logic Scorecard.

Nothing in here touches Streamlit or the network, so the scoring can be unit tested.
"""
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

MIN_TRADING_DAYS = 200
WARMUP_SESSIONS = 252  # a full 52-week window; every other indicator needs fewer rows
DEFAULT_MARKET_PE = 20.0

# Checked against forward returns in BACKTEST.md
TREND_DEAD_BAND = 1.0  # % gap required between price, MA50 and MA200 before calling a trend direction
MOMENTUM_LOOKBACK = 5  # sessions over which a change in the 20-day return counts as fading/accelerating
WIN_RATE_HIGH = 65.0
WIN_RATE_LOW = 35.0

Metrics = dict[str, Any]  # as returned by latest_metrics()


@dataclass
class Signal:
    score: int  # -1, 0 or +1
    message: str
    tone: str = ''  # 'success', 'error', 'info' or 'warning'; derived from score when empty
    max_up: int = 1  # most this signal can ever add; 0 for signals that can only warn
    max_down: int = 1
    available: bool = True  # False when the data behind the signal is missing; it then counts toward no maximum

    def __post_init__(self) -> None:
        if not self.tone:
            self.tone = 'success' if self.score > 0 else ('error' if self.score < 0 else 'info')


@dataclass
class Block:
    key: str
    title: str
    signals: list[Signal] = field(default_factory=list)

    @property
    def score(self) -> int:
        return sum(s.score for s in self.signals)

    @property
    def max_up(self) -> int:
        return sum(s.max_up for s in self.signals if s.available)

    @property
    def max_down(self) -> int:
        return sum(s.max_down for s in self.signals if s.available)

    @property
    def available(self) -> bool:
        return any(s.available for s in self.signals)


def prepare_prices(raw: pd.DataFrame) -> pd.DataFrame:
    """Flatten a yf.download() frame into lower_snake_case columns sorted by date."""
    df = raw.reset_index()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] if col[0] != '' else col[1] for col in df.columns]
    df.columns = [str(col).lower().replace(' ', '_') for col in df.columns]
    # Only a missing close makes a row unusable; dropping rows with a missing volume would shift every price window
    return df.dropna(subset=['close']).sort_values('date').reset_index(drop=True)


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['MA50'] = df['close'].rolling(window=50).mean()
    df['MA200'] = df['close'].rolling(window=200).mean()
    df['Volume_MA20'] = df['volume'].rolling(window=20, min_periods=15).mean()  # tolerates a few missing volumes
    df['Returns'] = df['close'].pct_change()
    df['Volatility_20d'] = df['Returns'].rolling(window=20).std() * np.sqrt(252) * 100
    df['Volatility_MA60'] = df['Volatility_20d'].rolling(window=60).mean()
    df['ROC_20d'] = df['close'].pct_change(20) * 100
    df['ROC_50d'] = df['close'].pct_change(50) * 100
    df['Momentum_Change'] = df['ROC_20d'].diff(MOMENTUM_LOOKBACK)
    df['Daily_Range'] = ((df['high'] - df['low']) / df['close']) * 100
    # Last 20 sessions' average volume vs. the 20 sessions before that
    df['Volume_Trend'] = (df['Volume_MA20'] / df['Volume_MA20'].shift(20) - 1) * 100
    df['Vol_Z_Score'] = (df['Volatility_20d'] - df['Volatility_MA60']) / df['Volatility_20d'].rolling(60).std()
    df['Win_Rate'] = (df['Returns'] > 0).rolling(window=20).sum() / 20 * 100
    return df.replace([np.inf, -np.inf], np.nan)


def latest_metrics(df: pd.DataFrame) -> Metrics:
    last = df.iloc[-1]
    high_52w = df['high'].tail(252).max()
    low_52w = df['low'].tail(252).min()
    price_range = high_52w - low_52w
    return {
        'as_of': last['date'],
        'price': last['close'],
        'ma50': last['MA50'],
        'ma200': last['MA200'],
        'volatility': last['Volatility_20d'],
        'vol_z_score': last['Vol_Z_Score'],
        'roc_20': last['ROC_20d'],
        'roc_50': last['ROC_50d'],
        'momentum_change': last['Momentum_Change'],
        'daily_range': last['Daily_Range'],
        'win_rate': last['Win_Rate'],
        'vol_trend': last['Volume_Trend'],
        'price_position': (last['close'] - low_52w) / price_range * 100 if price_range > 0 else 50.0,
        'vol_5d': df['volume'].tail(5).mean(),
        'vol_50d': df['volume'].tail(50).mean(),
    }


def metrics_history(df: pd.DataFrame, first: int = WARMUP_SESSIONS) -> list[Metrics]:
    """latest_metrics() as of each session from row `first` on. `df` must already have its indicators."""
    return [latest_metrics(df.iloc[:i + 1]) for i in range(first, len(df))]


def _as_positive_float(value: Any) -> float | None:
    """Return value as a finite positive float, or None (yfinance sometimes returns None or 'Infinity')."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value > 0 else None


def trend_momentum_block(m: Metrics) -> Block:
    block = Block('trend', 'Trend & Momentum')

    up, down = 1 + TREND_DEAD_BAND / 100, 1 - TREND_DEAD_BAND / 100
    if m['price'] > m['ma50'] * up and m['ma50'] > m['ma200'] * up:
        block.signals.append(Signal(1, "✓ **Uptrend Confirmed** - Price is clearly above both moving averages"))
    elif m['price'] < m['ma50'] * down and m['ma50'] < m['ma200'] * down:
        block.signals.append(Signal(-1, "✗ **Downtrend** - Price is clearly below both moving averages"))
    else:
        block.signals.append(Signal(0, f"~ **Mixed Trend** - No clear direction (price and averages are not stacked "
                                       f"at least {TREND_DEAD_BAND:g}% apart)"))

    roc_20, momentum_change = m['roc_20'], m['momentum_change']
    if roc_20 > 5 and momentum_change > 0:
        block.signals.append(Signal(1, f"✓ **Strong Momentum** - Up {roc_20:.1f}% in 20 days and accelerating"))
    elif roc_20 < -5:
        block.signals.append(Signal(-1, f"✗ **Weak Momentum** - Down {abs(roc_20):.1f}% in 20 days"))
    elif momentum_change < -2:
        block.signals.append(Signal(-1, f"✗ **Momentum Fading** - 20-day change slipped {abs(momentum_change):.1f} points "
                                        f"over the last {MOMENTUM_LOOKBACK} sessions (now {roc_20:+.1f}%)"))
    else:
        block.signals.append(Signal(0, f"~ **Neutral Momentum** - Sideways movement ({roc_20:+.1f}%)"))

    win_rate = m['win_rate']
    if win_rate > WIN_RATE_HIGH:
        block.signals.append(Signal(1, f"✓ **High Consistency** - {win_rate:.1f}% of days are positive (reliable uptrend)"))
    elif win_rate < WIN_RATE_LOW:
        block.signals.append(Signal(-1, f"✗ **Low Consistency** - Only {win_rate:.1f}% of days are positive (choppy/weak)"))
    else:
        block.signals.append(Signal(0, f"~ **Moderate Consistency** - {win_rate:.1f}% positive days"))

    return block


def breadth_block(m: Metrics) -> Block:
    block = Block('breadth', 'Breadth & Quality')
    vol_trend = m['vol_trend']
    if pd.isna(vol_trend):
        block.signals.append(Signal(0, "~ **Volume Unavailable** - No reliable volume data for this ticker", available=False))
    elif vol_trend > 5:
        block.signals.append(Signal(1, f"✓ **Volume Expanding** - Average daily volume up {vol_trend:.1f}% vs. the prior 20 days (strong interest)"))
    elif vol_trend < -10:
        block.signals.append(Signal(-1, f"✗ **Volume Drying Up** - Average daily volume down {abs(vol_trend):.1f}% vs. the prior 20 days (losing interest)"))
    else:
        block.signals.append(Signal(0, f"~ **Stable Volume** - Normal activity ({vol_trend:+.1f}% vs. the prior 20 days)"))
    return block


def sentiment_block(m: Metrics) -> Block:
    block = Block('sentiment', 'Sentiment & Flows')

    roc_50 = m['roc_50']
    if roc_50 > 10:
        block.signals.append(Signal(1, f"✓ **Strong Performance** - Up {roc_50:.1f}% over 50 days"))
    elif roc_50 < -10:
        block.signals.append(Signal(-1, f"✗ **Weak Performance** - Down {abs(roc_50):.1f}% over 50 days"))
    else:
        block.signals.append(Signal(0, f"~ **Neutral Performance** - Flat over 50 days ({roc_50:+.1f}%)"))

    # Shown for context only. Scoring a high position as overbought cancelled the uptrend signal in nearly every
    # bullish case, and in the backtest stocks near their 52-week high went on to do better, not worse (BACKTEST.md)
    position = m['price_position']
    zone = 'Near 52-Week High' if position > 75 else ('Near 52-Week Low' if position < 25 else 'Mid-Range')
    block.signals.append(Signal(0, f"~ **{zone}** - At {position:.0f}% of 52-week range (for context, not scored)",
                                max_up=0, max_down=0))

    return block


def valuation_block(pe_ratio: Any, market_pe: Any) -> Block:
    block = Block('valuation', 'Valuation & Macro')
    pe_ratio = _as_positive_float(pe_ratio)
    market_pe = _as_positive_float(market_pe) or DEFAULT_MARKET_PE

    if pe_ratio is None:
        block.signals.append(Signal(0, "~ **Valuation Unknown** - P/E not available, so valuation is left out of the score",
                                    available=False))
        return block

    relative_pe = (pe_ratio / market_pe - 1) * 100
    if relative_pe < -15:
        block.signals.append(Signal(1, f"✓ **Attractive Valuation** - Trading {abs(relative_pe):.0f}% cheaper than S&P 500"))
    elif relative_pe > 25:
        block.signals.append(Signal(-1, f"✗ **Expensive** - Trading {relative_pe:.0f}% more expensive than S&P 500"))
    else:
        block.signals.append(Signal(0, f"~ **Fair Value** - Trading {abs(relative_pe):.0f}% "
                                       f"{'above' if relative_pe > 0 else 'below'} S&P 500 (reasonable)"))
    return block


def volatility_block(m: Metrics) -> Block:
    block = Block('volatility', 'Volatility Regime')
    z = m['vol_z_score']
    # Calm volatility is the normal state, not a reason to buy, so this signal can only subtract
    if pd.isna(z):
        block.signals.append(Signal(0, "~ **Volatility Unavailable** - Not enough price movement to measure a regime",
                                    max_up=0, available=False))
    elif z > 1.5:
        block.signals.append(Signal(-1, f"✗ **High Stress** - Volatility {z:.1f} standard deviations above its recent norm "
                                        "(market fear/uncertainty)", max_up=0))
    elif z < -1.0:
        block.signals.append(Signal(0, f"~ **Complacency Warning** - Volatility unusually low (Z-score: {z:.2f}, "
                                       "risk of sudden reversal)", tone='warning', max_up=0))
    else:
        block.signals.append(Signal(0, f"~ **Normal Regime** - Volatility at its usual level (Z-score: {z:.2f})", max_up=0))
    return block


def liquidity_block(m: Metrics) -> Block:
    block = Block('liquidity', 'Liquidity Conditions')
    vol_5d, vol_50d = m['vol_5d'], m['vol_50d']
    # The 20-day volume trend is already scored in the breadth block, so liquidity looks at the last week instead
    volume_known = pd.notna(vol_5d) and pd.notna(vol_50d) and vol_50d > 0
    # Being easy to trade is the normal state, not a reason to buy, so this signal can only subtract
    if volume_known and vol_5d < vol_50d * 0.5:
        block.signals.append(Signal(-1, f"✗ **Liquidity Stress** - Volume over the last 5 days is {vol_5d / vol_50d * 100:.0f}% "
                                        "of its 50-day average (thin trading)", max_up=0))
    elif m['daily_range'] > 2.5 and m['win_rate'] < 40:
        block.signals.append(Signal(-1, f"✗ **Liquidity Stress** - Erratic prices: {m['daily_range']:.1f}% daily range "
                                        "with mostly down days (be cautious)", max_up=0))
    elif volume_known:
        block.signals.append(Signal(0, "~ **Normal Liquidity** - Recent volume in line with its 50-day average", max_up=0))
    else:
        block.signals.append(Signal(0, "~ **Normal Liquidity** - Prices orderly (no reliable volume data)", max_up=0))
    return block


def score_blocks(m: Metrics, pe_ratio: Any = None, market_pe: Any = None) -> list[Block]:
    return [
        trend_momentum_block(m),
        breadth_block(m),
        sentiment_block(m),
        valuation_block(pe_ratio, market_pe),
        volatility_block(m),
        liquidity_block(m),
    ]


def normalized_score(blocks: list[Block]) -> float:
    """Scale the raw total onto -5..+5.

    Some signals can only subtract, so the best and worst possible totals differ in size. Positive totals are
    scaled by the best possible total and negative ones by the worst, so both ends of the scale stay reachable
    and an all-neutral reading lands exactly on 0.
    """
    total = sum(b.score for b in blocks)
    limit = sum(b.max_up for b in blocks) if total > 0 else sum(b.max_down for b in blocks)
    return total / limit * 5 if limit else 0.0


def recommendation(score: float) -> tuple[str, str]:
    if score >= 3:
        return "🟢 STRONG BUY", "Favorable across most indicators. Technicals + flows suggest upside."
    if score >= 1:
        return "🟢 BUY / HOLD FULL POSITION", "Generally positive setup. Macro support outweighs near-term weakness."
    if score >= -1:
        return "🟡 HOLD / REDUCE TO 50%", "Mixed signals. Scale back pending clarity on momentum/flows."
    if score >= -3:
        return "🔴 REDUCE / CONSIDER EXIT", "Unfavorable conditions. Risk-reward tilted down. Preserve capital."
    return "🔴 STRONG SELL", "Major headwinds across blocks. Wait for capitulation signals."


def score_history(df: pd.DataFrame, sessions: int = 252, pe_ratio: Any = None, market_pe: Any = None) -> pd.Series:
    """Normalized score as of each of the last `sessions` sessions that have a full warm-up behind them.

    `df` must already have its indicators. Historical P/E is not available, so callers normally leave
    `pe_ratio` out and valuation drops out of the score.
    """
    history = metrics_history(df, max(len(df) - sessions, WARMUP_SESSIONS))
    return pd.Series([normalized_score(score_blocks(m, pe_ratio, market_pe)) for m in history],
                     index=pd.DatetimeIndex([m['as_of'] for m in history], name='date'), name='score', dtype=float)
