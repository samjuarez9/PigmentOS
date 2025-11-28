# PigmentOS

Real-time stock intelligence HUD with market sentiment analysis.

## Quick Start

```bash
./start.sh
```

This will start the backend server and open the dashboard in your browser.

## Architecture

PigmentOS consists of two components:

1. **Frontend** (`index.html` + `app.js`)
   - Real-time dashboard
   - TradingView charts
   - Live data feeds

2. **Backend** (`run.py`)
   - Python server on port 8001
   - Fetches data from multiple APIs:
     - CNN Fear & Greed Index
     - Polymarket odds
     - News feeds (TechCrunch, CNBC, The Verge)
     - Unusual options activity (yfinance)

## Features

- 🐳 **Unusual Whales** - High-value options flow tracker
- 📊 **P/C Ratio** - Put/Call sentiment analysis  
- 📈 **Live Price Action** - TradingView charts
- 🔮 **Polymarket Odds** - Market probabilities
- 😱 **Trader Fear Index** - Real CNN Fear & Greed data
- 📰 **Market Wire** - Curated news feed

## Requirements

```bash
pip install -r requirements.txt
```

Dependencies:
- Python 3.11+
- yfinance
- requests
- feedparser
- pandas

## Health Check

Verify the server is running:

```bash
./check_server.sh
```

## Troubleshooting

See `.agent/workflows/start.md` for detailed troubleshooting steps.

## Server Logs

Server output is logged to `server.log`:

```bash
tail -f server.log
```
