import yfinance as yf
import time

MOVERS_TICKERS = [
    'NVDA', 'AMD', 'INTC', 'TSLA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 
    'NFLX', 'PLTR', 'COIN', 'MSTR', 'MARA', 'RIOT', 'DKNG', 'HOOD', 'ROKU', 
    'SQ', 'PYPL', 'SHOP', 'NET', 'SNOW', 'DDOG', 'CRWD', 'PANW', 'ZS'
]

print(f"Testing fetch for {len(MOVERS_TICKERS)} tickers...")

success_count = 0
for symbol in MOVERS_TICKERS:
    try:
        t = yf.Ticker(symbol)
        # Try fast_info first
        last = t.fast_info.last_price
        prev = t.fast_info.previous_close
        
        if last and prev:
            change = ((last - prev) / prev) * 100
            print(f"✅ {symbol}: ${last:.2f} ({change:+.2f}%)")
            success_count += 1
        else:
            print(f"⚠️ {symbol}: Missing price data (Last: {last}, Prev: {prev})")
            
    except Exception as e:
        print(f"❌ {symbol}: Error - {e}")

print(f"\nSummary: {success_count}/{len(MOVERS_TICKERS)} successful")
