from gevent import monkey
monkey.patch_all()

import yfinance as yf
import time

MOVERS_TICKERS = [
    'NVDA', 'AMD', 'INTC', 'TSLA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 
    'NFLX', 'PLTR', 'COIN', 'MSTR', 'MARA', 'RIOT', 'DKNG', 'HOOD', 'ROKU', 
    'SQ', 'PYPL', 'SHOP', 'NET', 'SNOW', 'DDOG', 'CRWD', 'PANW', 'ZS'
]

print(f"Testing fetch with GEVENT for {len(MOVERS_TICKERS)} tickers...")

try:
    tickers = yf.Tickers(" ".join(MOVERS_TICKERS))
    
    for symbol in MOVERS_TICKERS:
        try:
            t = tickers.tickers[symbol]
            last = t.fast_info.last_price
            print(f"✅ {symbol}: ${last}")
        except Exception as e:
            print(f"❌ {symbol}: Error - {e}")

except Exception as e:
    print(f"CRITICAL ERROR: {e}")
