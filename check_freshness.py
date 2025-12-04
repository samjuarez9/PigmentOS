import yfinance as yf
import time
from datetime import datetime
import pytz

def check_freshness():
    tickers = ["SPY", "NVDA", "AAPL"]
    print(f"Checking freshness for: {tickers}")
    
    tz_eastern = pytz.timezone('US/Eastern')
    now = datetime.now(tz_eastern)
    print(f"Current Time (ET): {now}")
    
    for symbol in tickers:
        try:
            t = yf.Ticker(symbol)
            price = t.fast_info.last_price
            prev_close = t.fast_info.previous_close
            
            # fast_info doesn't provide a timestamp, so we have to infer or check .info (slower)
            # Let's check .info for 'regularMarketTime' if available, or just print the price
            
            print(f"\n--- {symbol} ---")
            print(f"Fast Info Price: {price}")
            print(f"Prev Close: {prev_close}")
            
            if price and prev_close:
                change = ((price - prev_close) / prev_close) * 100
                print(f"Calculated Change: {change:.2f}%")
            
            # Try to get a timestamp from .info (this is slower but might give us a clue)
            # info = t.info
            # print(f"Market Time: {info.get('regularMarketTime')}")
            # print(f"Post Market Time: {info.get('postMarketTime')}")
            
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")

if __name__ == "__main__":
    check_freshness()
