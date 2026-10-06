"""Indicator calculations and scoring for the Fosback Market Logic Scorecard.

Nothing in here touches Streamlit or the network, so the scoring can be unit tested.
"""
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

MIN_TRADING_DAYS = 200
DEFAULT_MARKET_PE = 20.0


@dataclass
class Signal:
    score: int  # -1, 0 or +1
    message: str
    tone: str = ''  # 'success', 'error', 'info' or 'warning'; derived from score when empty

    def __post_init__(self):
        if not self.tone:
            self.tone = 'success' if self.score > 0 else ('error' if self.score < 0 else 'info')


@dataclass
class Block:
    key: str
    title: str
    signals: list = field(default_factory=list)

    @property
    def score(self):
        return sum(s.score for s in self.signals)

    @property
    def max_score(self):
        return len(self.signals)


def prepare_prices(raw):
    """Flatten a yf.download() frame into lower_snake_case columns sorted by date."""
    df = raw.reset_index()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] if col[0] != '' else col[1] for col in df.columns]
    df.columns = [str(col).lower().replace(' ', '_') for col in df.columns]
    return df.dropna().sort_values('date').reset_index(drop=True)


def compute_indicators(df):
    df = df.copy()
    df['MA50'] = df['close'].rolling(window=50).mean()
    df['MA200'] = df['close'].rolling(window=200).mean()
    df['Volume_MA20'] = df['volume'].rolling(window=20).mean()
    df['Returns'] = df['close'].pct_change()
    df['Volatility_20d'] = df['Returns'].rolling(window=20).std() * np.sqrt(252) * 100
    df['Volatility_MA60'] = df['Volatility_20d'].rolling(window=60).mean()
    df['ROC_20d'] = df['close'].pct_change(20) * 100
    df['ROC_50d'] = df['close'].pct_change(50) * 100
    df['Momentum_Change'] = df['ROC_20d'].diff()
    df['Daily_Range'] = ((df['high'] - df['low']) / df['close']) * 100
    # Last 20 sessions' average volume vs. the 20 sessions before that
    df['Volume_Trend'] = (df['Volume_MA20'] / df['Volume_MA20'].shift(20) - 1) * 100
    df['Vol_Z_Score'] = (df['Volatility_20d'] - df['Volatility_MA60']) / df['Volatility_20d'].rolling(60).std()
    df['Win_Rate'] = (df['Returns'] > 0).rolling(window=20).sum() / 20 * 100
    return df.replace([np.inf, -np.inf], np.nan)


def latest_metrics(df):
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


def _as_positive_float(value):
    """Return value as a finite positive float, or None (yfinance sometimes returns None or 'Infinity')."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value > 0 else None


def trend_momentum_block(m):
    block = Block('trend', 'Trend & Momentum')

    if m['price'] > m['ma50'] and m['ma50'] > m['ma200']:
        block.signals.append(Signal(1, "✓ **Uptrend Confirmed** - Price is above both moving averages"))
    elif m['price'] < m['ma50'] and m['ma50'] < m['ma200']:
        block.signals.append(Signal(-1, "✗ **Downtrend** - Price is below moving averages"))
    else:
        block.signals.append(Signal(0, "~ **Mixed Trend** - No clear direction"))

    roc_20, momentum_change = m['roc_20'], m['momentum_change']
    if roc_20 > 5 and momentum_change > 0:
        block.signals.append(Signal(1, f"✓ **Strong Momentum** - Up {roc_20:.1f}% in 20 days and accelerating"))
    elif roc_20 < -5:
        block.signals.append(Signal(-1, f"✗ **Weak Momentum** - Down {abs(roc_20):.1f}% in 20 days"))
    elif momentum_change < -2:
        block.signals.append(Signal(-1, f"✗ **Momentum Fading** - 20-day change slipped {abs(momentum_change):.1f} points "
                                        f"in the last session (now {roc_20:+.1f}%)"))
    else:
        block.signals.append(Signal(0, f"~ **Neutral Momentum** - Sideways movement ({roc_20:+.1f}%)"))

    win_rate = m['win_rate']
    if win_rate > 60:
        block.signals.append(Signal(1, f"✓ **High Consistency** - {win_rate:.1f}% of days are positive (reliable uptrend)"))
    elif win_rate < 40:
        block.signals.append(Signal(-1, f"✗ **Low Consistency** - Only {win_rate:.1f}% of days are positive (choppy/weak)"))
    else:
        block.signals.append(Signal(0, f"~ **Moderate Consistency** - {win_rate:.1f}% positive days"))

    return block


def breadth_block(m):
    block = Block('breadth', 'Breadth & Quality')
    vol_trend = m['vol_trend']
    if pd.isna(vol_trend):
        block.signals.append(Signal(0, "~ **Volume Unavailable** - No reliable volume data for this ticker"))
    elif vol_trend > 5:
        block.signals.append(Signal(1, f"✓ **Volume Expanding** - Average daily volume up {vol_trend:.1f}% vs. the prior 20 days (strong interest)"))
    elif vol_trend < -10:
        block.signals.append(Signal(-1, f"✗ **Volume Drying Up** - Average daily volume down {abs(vol_trend):.1f}% vs. the prior 20 days (losing interest)"))
    else:
        block.signals.append(Signal(0, f"~ **Stable Volume** - Normal activity ({vol_trend:+.1f}% vs. the prior 20 days)"))
    return block


def sentiment_block(m):
    block = Block('sentiment', 'Sentiment & Flows')

    roc_50 = m['roc_50']
    if roc_50 > 10:
        block.signals.append(Signal(1, f"✓ **Strong Performance** - Up {roc_50:.1f}% over 50 days"))
    elif roc_50 < -10:
        block.signals.append(Signal(-1, f"✗ **Weak Performance** - Down {abs(roc_50):.1f}% over 50 days"))
    else:
        block.signals.append(Signal(0, f"~ **Neutral Performance** - Flat over 50 days ({roc_50:+.1f}%)"))

    position = m['price_position']
    if position > 75:
        block.signals.append(Signal(-1, f"✗ **Overbought** - At {position:.0f}% of 52-week range (limited upside)"))
    elif position < 25:
        block.signals.append(Signal(1, f"✓ **Oversold** - At {position:.0f}% of 52-week range (potential opportunity)"))
    else:
        block.signals.append(Signal(0, f"~ **Fair Value** - At {position:.0f}% of 52-week range"))

    return block


def valuation_block(pe_ratio, market_pe):
    block = Block('valuation', 'Valuation & Macro')
    pe_ratio = _as_positive_float(pe_ratio)
    market_pe = _as_positive_float(market_pe) or DEFAULT_MARKET_PE

    if pe_ratio is None:
        block.signals.append(Signal(0, "~ **Fair Value Assumed** - P/E not available"))
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


def volatility_block(m):
    block = Block('volatility', 'Volatility Regime')
    z = m['vol_z_score']
    if z > 1.5:
        block.signals.append(Signal(-1, f"✗ **High Stress** - Volatility {z:.1f} standard deviations above its recent norm "
                                        "(market fear/uncertainty)"))
    elif z < -1.0:
        block.signals.append(Signal(0, f"~ **Complacency Warning** - Volatility unusually low (Z-score: {z:.2f}, "
                                       "risk of sudden reversal)", tone='warning'))
    else:
        block.signals.append(Signal(1, f"✓ **Normal Regime** - Volatility at healthy levels (Z-score: {z:.2f})"))
    return block


def liquidity_block(m):
    block = Block('liquidity', 'Liquidity Conditions')
    vol_trend = m['vol_trend']
    if vol_trend > -3 and m['vol_5d'] > m['vol_50d'] * 0.9:
        block.signals.append(Signal(1, "✓ **Healthy Liquidity** - Easy to trade, stable volume"))
    elif vol_trend < -10 or (m['daily_range'] > 2.5 and m['win_rate'] < 40):
        block.signals.append(Signal(-1, "✗ **Liquidity Stress** - Low volume or erratic prices (be cautious)"))
    else:
        block.signals.append(Signal(0, "~ **Normal Liquidity** - Standard trading conditions"))
    return block


def score_blocks(m, pe_ratio=None, market_pe=None):
    return [
        trend_momentum_block(m),
        breadth_block(m),
        sentiment_block(m),
        valuation_block(pe_ratio, market_pe),
        volatility_block(m),
        liquidity_block(m),
    ]


def normalized_score(blocks):
    """Scale the raw total onto -5..+5 using the real maximum of the scored signals."""
    total_max = sum(b.max_score for b in blocks)
    return sum(b.score for b in blocks) / total_max * 5 if total_max else 0.0


def recommendation(score):
    if score >= 3:
        return "🟢 STRONG BUY", "Favorable across most indicators. Technicals + flows suggest upside."
    if score >= 1:
        return "🟢 BUY / HOLD FULL POSITION", "Generally positive setup. Macro support outweighs near-term weakness."
    if score >= -1:
        return "🟡 HOLD / REDUCE TO 50%", "Mixed signals. Scale back pending clarity on momentum/flows."
    if score >= -3:
        return "🔴 REDUCE / CONSIDER EXIT", "Unfavorable conditions. Risk-reward tilted down. Preserve capital."
    return "🔴 STRONG SELL", "Major headwinds across blocks. Wait for capitulation signals."
