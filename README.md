# Fosback Market Logic Scorecard Web App

A modern web application implementing Norman Fosback's "Stock Market Logic" framework, adapted for contemporary market conditions including algorithmic trading, options flow, and real-time sentiment analysis.

## Features

- **Ticker-Agnostic Analysis**: Works with any stock or ETF
- **Real-Time Data**: Fetches live market data via Yahoo Finance
- **7 Analysis Blocks**:
  1. Trend & Momentum
  2. Breadth & Quality
  3. Sentiment & Flows
  4. Valuation & Macro
  5. Volatility Regime
  6. Liquidity Conditions
- **Visual Scorecard**: Easy-to-read recommendation system
- **Interactive Charts**: Historical price and moving average visualization

## Live Demo

### Deploy to Streamlit Cloud (Recommended)

1. **Push to GitHub** (see instructions below)
2. **Visit** [streamlit.io/cloud](https://streamlit.io/cloud)
3. **Sign in** with GitHub
4. **Click** "New app"
5. **Select** your repository: `yourusername/fosback-scorecard`
6. **Set** main file path: `app.py`
7. **Click** "Deploy"

Your app will be live at: `https://yourusername-fosback-scorecard.streamlit.app`

### Run Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

## GitHub Setup

### Initialize Repository

```bash
cd /home/macro/Documents/ETF

# Initialize git
git init

# Add files
git add app.py requirements.txt README.md
git commit -m "Initial commit: Fosback scorecard web app"

# Create GitHub repo (on github.com):
# 1. Go to github.com/new
# 2. Name it: fosback-scorecard
# 3. Make it public
# 4. Don't initialize with README

# Link and push
git remote add origin https://github.com/YOUR_USERNAME/fosback-scorecard.git
git branch -M main
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub username.

## Usage

1. Enter a ticker symbol (e.g., GRID, SPY, AAPL)
2. Adjust the historical data range (optional)
3. Click "Run Analysis"
4. Review the scorecard and recommendation

## Methodology

### Updated Framework for Modern Markets

| Original (1976) | Modern Adaptation |
|-----------------|------------------|
| Manual updates | Real-time yfinance data |
| Mutual fund cash | Options flow (0DTE, put/call) |
| Simple volume | Volume trends + algo direction |
| Vol as risk filter | Full regime analysis |
| Advance/decline | Sector rotation + flows |

### Scoring System

- **Raw Score**: Sum of all blocks (-14 to +14)
- **Normalized Score**: Scaled to -5 to +5
- **Recommendations**:
  - **+3 to +5**: Strong Buy
  - **+1 to +3**: Buy/Hold Full
  - **-1 to +1**: Hold/Reduce 50%
  - **-3 to -1**: Reduce/Exit
  - **-5 to -3**: Strong Sell

## Data Sources

- **Price Data**: Yahoo Finance API
- **Technical Indicators**: Pandas/NumPy calculations
- **Fundamentals**: yfinance ticker info

## Disclaimer

This application is for **educational purposes only**. It is **not financial advice**. Always consult with a qualified financial advisor before making investment decisions.

## License

MIT License - See LICENSE file for details

## Credits

Based on Norman Fosback's "Stock Market Logic" (1976), adapted for modern algorithmic and options-driven markets.
