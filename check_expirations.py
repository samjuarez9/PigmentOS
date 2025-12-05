import yfinance as yf
from datetime import datetime

tickers = ['SPY', 'NVDA']

print(f"Checking expirations at {datetime.now()}")

for symbol in tickers:
    try:
        t = yf.Ticker(symbol)
        opts = t.options
        print(f"\n--- {symbol} ---")
        print(f"Total Expirations Found: {len(opts)}")
        print(f"First 5 Expirations: {opts[:5]}")
        print(f"What we are currently scraping ([:2]): {opts[:2]}")
    except Exception as e:
        print(f"Error for {symbol}: {e}")
