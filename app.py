import logging
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
import yfinance as yf

from scorecard import (
    MIN_TRADING_DAYS,
    compute_indicators,
    latest_metrics,
    normalized_score,
    prepare_prices,
    recommendation,
    score_blocks,
)

logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="Fosback Market Logic Scorecard",
    page_icon="📊",
    layout="wide"
)

# Title and description
st.title("📊 Fosback Market Logic Scorecard")
st.markdown("""
### A Simple Tool to Evaluate Any Stock or ETF

Ever wonder if now is a good time to buy, hold, or sell? This app analyzes **6 key factors** that professional
investors look at, then gives you a simple score from **-5 (Sell)** to **+5 (Buy)**.

**What makes this different?**
- ✅ Works for any stock or ETF listed on Yahoo Finance
- ✅ Uses the latest daily market data
- ✅ No complex jargon - clear explanations for each factor
- ✅ Based on Norman Fosback's proven framework from 1976, updated for today's algo-driven markets

**Perfect for:** Long-term investors, DIY portfolio managers, or anyone curious about market timing without the complexity.
""")

with st.expander("📖 How It Works (Click to Learn More)"):
    st.markdown("""
    The app evaluates **6 critical factors** and combines them into a single score:

    1. **Trend & Momentum** - Is the price moving up or down? Is it accelerating?
    2. **Breadth & Quality** - Are investors showing real interest (volume)?
    3. **Sentiment & Flows** - Is it overbought (risky) or oversold (opportunity)?
    4. **Valuation & Macro** - Is it expensive or cheap compared to the market?
    5. **Volatility Regime** - Is the market calm or stressed?
    6. **Liquidity** - Can you easily buy/sell without moving the price?

    Each factor gets scored, then everything combines into your **final recommendation**.

    **Note:** This is educational. Always do your own research and consult a financial advisor before investing.
    """)

BLOCK_ICONS = {
    'trend': "📈",
    'breadth': "📊",
    'sentiment': "🎯",
    'valuation': "💰",
    'volatility': "📉",
    'liquidity': "💧",
}

BLOCK_EXPLAINERS = {
    'trend': """
    **In simple terms:** Is the stock going up or down, and how fast?

    - **Trend**: We compare current price to its 50-day and 200-day averages
    - **Momentum**: How much has it moved in the last 20 days?
    - **Consistency**: Does it have more "up days" than "down days"?

    **Why it matters:** You want to buy stocks moving up with strong momentum, not falling knives.
    """,
    'breadth': """
    **In simple terms:** Are lots of people buying/selling, or is it quiet?

    - **Volume Trend**: Average daily volume over the last 20 days compared with the 20 days before

    **Why it matters:** Price moves with high volume are more reliable. Low volume = weak conviction.
    Think of it like a product going viral vs. one nobody talks about.
    """,
    'sentiment': """
    **In simple terms:** Is this a good deal, or has it already run too far?

    - **Recent Performance**: How has it done over the last 50 days?
    - **52-Week Position**: Is it near its high (expensive) or low (cheap)?

    **Why it matters:** Buying near 52-week highs can be risky (might correct).
    Buying near lows can be an opportunity (if fundamentals are intact).
    """,
    'valuation': """
    **In simple terms:** Is this expensive or cheap compared to the overall market (S&P 500)?

    - **Relative P/E Ratio**: We compare the stock's price-to-earnings to the S&P 500

    **Why it matters:** A stock trading at a big premium needs exceptional growth to justify it.
    A discount might indicate an opportunity (or a problem - needs more research!).
    """,
    'volatility': """
    **In simple terms:** How wild are the price swings? Is the market calm or panicking?

    - **Volatility Z-Score**: Measures if price swings are normal, extreme, or suspiciously calm

    **Why it matters:**
    - High volatility = stress/panic = risky but potential opportunities
    - Too low = complacency = danger (calm before the storm)
    - Normal = healthy market conditions
    """,
    'liquidity': """
    **In simple terms:** How easy is it to buy or sell without affecting the price?

    - **Volume Trends**: Is trading activity stable or drying up?
    - **Price Stability**: Are prices jumping around erratically?

    **Why it matters:** Low liquidity means you might struggle to sell when you want,
    or face big price swings. Good liquidity = smoother trading experience.
    """,
}

TONE_RENDERERS = {
    'success': st.success,
    'error': st.error,
    'info': st.info,
    'warning': st.warning,
}


@st.cache_data(ttl=3600, show_spinner=False)
def load_prices(ticker, days_back):
    start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    # yfinance treats `end` as exclusive, so today's incomplete session is left out
    end_date = datetime.now().strftime('%Y-%m-%d')
    raw = yf.download(ticker, start=start_date, end=end_date, progress=False)
    if raw.empty:
        # Raise instead of returning so an empty (possibly rate-limited) result is not cached
        raise LookupError(f"No price data found for {ticker}. Make sure it is a Yahoo Finance symbol "
                          "(non-US listings need a suffix, e.g. SAP.DE), or try again in a minute "
                          "if Yahoo Finance is busy.")
    return raw


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def load_trailing_pe(ticker):
    return yf.Ticker(ticker).info.get('trailingPE')


def safe_trailing_pe(ticker):
    try:
        return load_trailing_pe(ticker)
    except Exception:
        logger.warning("Could not load P/E for %s", ticker, exc_info=True)
        return None


def run_analysis(ticker, days_back):
    df = prepare_prices(load_prices(ticker, days_back))
    if len(df) < MIN_TRADING_DAYS:
        st.error(f"Insufficient data for {ticker}. Need at least {MIN_TRADING_DAYS} trading days.")
        return

    df = compute_indicators(df)
    m = latest_metrics(df)
    blocks = score_blocks(m, safe_trailing_pe(ticker), safe_trailing_pe('SPY'))

    # Display current metrics
    st.header(f"{ticker} - Current Metrics")
    st.caption(f"As of the {m['as_of'].strftime('%Y-%m-%d')} close")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Price", f"${m['price']:.2f}")
        st.metric("MA50", f"${m['ma50']:.2f}", f"{((m['price'] - m['ma50']) / m['ma50'] * 100):+.2f}%")
    with col2:
        st.metric("MA200", f"${m['ma200']:.2f}", f"{((m['price'] - m['ma200']) / m['ma200'] * 100):+.2f}%")
        st.metric("20d ROC", f"{m['roc_20']:+.2f}%")
    with col3:
        st.metric("Volatility (20d)", f"{m['volatility']:.2f}%")
        st.metric("Vol Z-Score", f"{m['vol_z_score']:.2f}")
    with col4:
        st.metric("Win Rate", f"{m['win_rate']:.1f}%")
        st.metric("52w Position", f"{m['price_position']:.1f}%")

    for number, block in enumerate(blocks, start=1):
        st.subheader(f"{BLOCK_ICONS[block.key]} Block {number}: {block.title}")
        with st.expander("ℹ️ What does this measure?"):
            st.markdown(BLOCK_EXPLAINERS[block.key])
        for signal in block.signals:
            TONE_RENDERERS[signal.tone](signal.message)
        st.metric(f"Block {number} Score", f"{block.score}/{block.max_score}")

    # FINAL SCORECARD
    st.header("📊 Final Scorecard")

    scorecard_df = pd.DataFrame({
        'Category': [b.title for b in blocks],
        'Score': [f"{b.score}/{b.max_score}" for b in blocks],
        'Status': [('✓ FAVORABLE' if b.score > 0 else ('✗ UNFAVORABLE' if b.score < 0 else '~ NEUTRAL')) for b in blocks]
    })

    st.dataframe(scorecard_df, width="stretch", hide_index=True)

    # Recommendation
    st.subheader("Recommendation")

    score = normalized_score(blocks)
    label, meaning = recommendation(score)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Normalized Score", f"{score:+.2f}", help="Scale: -5 (Strong Sell) to +5 (Strong Buy)")
        st.progress((score + 5) / 10)
        st.caption("Scale: -5 (Sell) ← 0 (Neutral) → +5 (Buy)")
    with col2:
        st.markdown(f"**{label}**")

    st.info(meaning)

    st.markdown("---")
    st.caption("""
    **💡 How to use this score:**
    - **+1 or higher**: Generally bullish - consider buying or holding (+3 or higher is a strong signal)
    - **Between -1 and +1**: Mixed signals - be cautious, wait for clarity
    - **Below -1**: Generally bearish - consider reducing position or staying out (below -3 is a strong signal)

    Remember: This is one tool among many. Always consider your personal financial situation,
    risk tolerance, and investment timeline.
    """)

    # Chart
    st.subheader("Price Chart")
    chart_data = df[['date', 'close', 'MA50', 'MA200']].tail(252).set_index('date')
    st.line_chart(chart_data)

    # Disclaimer
    st.caption("**Disclaimer:** For educational purposes only. Not financial advice. Always consult a qualified advisor.")


# Sidebar for inputs
st.sidebar.header("Configuration")
ticker = st.sidebar.text_input(
    "Enter Ticker Symbol",
    value="GRID",
    help="Use the Yahoo Finance symbol. Non-US listings need an exchange suffix, "
         "e.g. NESN.SW (Zurich), SAP.DE (Xetra), VOD.L (London). Search finance.yahoo.com if unsure.",
).strip().upper()
days_back = st.sidebar.slider("Days of Historical Data", 365, 1095, 730)

if st.sidebar.button("Run Analysis", type="primary") and ticker:
    # Remember the request so the results survive reruns triggered by other widgets
    st.session_state['analysis_request'] = (ticker, days_back)

request = st.session_state.get('analysis_request')
if request:
    with st.spinner(f"Analyzing {request[0]}..."):
        try:
            run_analysis(*request)
        except LookupError as e:
            st.error(str(e))
        except Exception as e:
            logger.exception("Analysis failed for %s", request[0])
            st.error(f"Something went wrong analyzing {request[0]}: {e}. Please try again in a minute.")
else:
    st.info("👈 Enter a ticker symbol and click 'Run Analysis' to begin")
