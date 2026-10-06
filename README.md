[![Buy me a pizza](https://img.shields.io/badge/Sponsor-🍕-8B4513?logo=github&logoColor=white)](https://github.com/sponsors/macromeer)
# 📊 Fosback Market Logic Scorecard

**Should you buy, hold, or sell that stock?** Get a simple answer based on 6 key factors that professional investors use.

[**🚀 Try the Live App**](https://fosback-scorecard.streamlit.app)

[<img width="995" height="531" alt="Raw_App_Screenshot" src="https://github.com/user-attachments/assets/33b80c7e-70fa-4cdc-afa4-fd853c6baa94" />](https://fosback-scorecard.streamlit.app)


---

## What Does This Do?

Ever looked at a stock and wondered: *"Is now a good time to buy?"*

This tool analyzes **any stock or ETF** and gives you a clear score from **-5 (Sell)** to **+5 (Buy)** based on:

- 📈 **Trend & Momentum** - Is it going up or down?
- 📊 **Trading Volume** - Are people actually buying it?
- 🎯 **Recent Performance** - Has it gained or lost a lot over the last 50 days?
- 💰 **Valuation** - Compared to the overall market
- 📉 **Volatility** - Is it stable or all over the place?
- 💧 **Liquidity** - Can you easily trade it?

**No finance degree needed** - everything is explained in plain English.

---

## How to Use It

1. **Go to the app**: [fosback-scorecard.streamlit.app](https://fosback-scorecard.streamlit.app)
2. **Enter a [Yahoo Finance](https://finance.yahoo.com) ticker** (like AAPL, TSLA, SPY)
   - Non-US listings need Yahoo's exchange suffix, e.g. `NESN.SW` (Zurich), `SAP.DE` (Xetra), `VOD.L` (London)
   - Not sure of the symbol? Search the company on [finance.yahoo.com](https://finance.yahoo.com) and copy the ticker shown there
3. **Click "Run Analysis"**
4. **Get your score** and recommendation

That's it! The whole analysis takes ~5 seconds.

---

## What Do The Scores Mean?

| Score | Recommendation | What It Means |
|-------|---------------|---------------|
| **+3 to +5** | 🟢 Strong Buy | Most factors look great - strong opportunity |
| **+1 to +3** | 🟢 Buy/Hold | Generally positive - good time to invest |
| **-1 to +1** | 🟡 Hold/Reduce to 50% | Mixed signals - be patient, scale back |
| **-3 to -1** | 🔴 Reduce/Exit | Warning signs - consider selling |
| **-5 to -3** | 🔴 Strong Sell | Multiple red flags - stay away |

A stock where nothing stands out scores 0. Volatility and liquidity can only pull the score down:
calm, easy-to-trade conditions are normal and are not a reason to buy.
When data is missing (for example, most ETFs have no P/E ratio), that factor is left out of the score
rather than counted as neutral, so the full -5 to +5 range is still possible.

---

## Example: Analyzing Apple (AAPL)

```
Score: +2.5
Recommendation: 🟢 BUY/HOLD

✓ Uptrend confirmed
✓ Strong momentum (+8.2% in 20 days)
✓ High consistency (70% positive days)
~ Volume stable
~ Near 52-week high (82% of range, shown for context)
```

Each factor is explained so you understand *why* the score is what it is.

---

## Why This Tool?

**Traditional approach**: Read 20 articles, check 10 charts, still confused.

**This tool**: 
- ✅ Analyzes multiple factors at once
- ✅ Uses the latest daily market data
- ✅ Gives you a clear answer
- ✅ Works for any stock or ETF listed on Yahoo Finance
- ✅ Completely free

---

## Is This Financial Advice?

**No.** This is an educational tool to help you understand market analysis.

- Always do your own research
- Consider your personal financial situation
- Consult a qualified financial advisor before investing
- Past performance doesn't guarantee future results

---

## Who Made This?

Built by [macromeer](https://github.com/macromeer) as a hobby project.

Based on Norman Fosback's 1976 "Stock Market Logic" framework, updated for today's algo-driven markets.

---

## Tech Stack

- **Frontend**: Streamlit
- **Data**: Yahoo Finance API
- **Analysis**: Python (Pandas, NumPy)
- **Hosting**: Streamlit Cloud (free tier)

To run it yourself: `pip install -r requirements-dev.txt`, then `streamlit run app.py` (app) or `pytest` (tests).

---

## Questions?

Open an [issue on GitHub](https://github.com/macromeer/fosback-scorecard/issues) or check out the code to see how it works.

---

## License

MIT License - Free to use, modify, and share.

**Like this project?** Give it a ⭐ on GitHub!
