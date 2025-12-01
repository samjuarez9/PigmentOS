import yfinance as yf
import pandas as pd
from datetime import datetime
import pytz

# Config
WATCHLIST = ['NVDA', 'TSLA', 'AMD', 'PLTR']
MIN_NOTIONAL = 100_000 # $100k (Lower than the $1.5M production limit)

print(f"🔎 Scanning {WATCHLIST} for trades > ${MIN_NOTIONAL/1000:.0f}k...")

for symbol in WATCHLIST:
    try:
        ticker = yf.Ticker(symbol)
        expirations = ticker.options
        if not expirations: continue
        
        # Check next 2 expirations
        for expiry in expirations[:2]:
            opts = ticker.option_chain(expiry)
            chain = pd.concat([opts.calls, opts.puts])
            
            # Basic filters
            unusual = chain[
                (chain['volume'] > 500) & 
                (chain['lastPrice'] > 0.10)
            ]
            
            for _, row in unusual.iterrows():
                notional = row['volume'] * row['lastPrice'] * 100
                
                if notional > MIN_NOTIONAL:
                    print(f"  🐳 {symbol} {expiry} | Vol: {row['volume']} | Prem: ${notional/1000:.1f}k")
                    
    except Exception as e:
        print(f"  Error {symbol}: {e}")

print("✅ Scan Complete")
