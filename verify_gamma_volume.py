import yfinance as yf
import pandas as pd
from datetime import datetime
import pytz

def verify_gamma_volume():
    symbol = "SPY"
    print(f"Fetching option chain for {symbol}...")
    
    try:
        ticker = yf.Ticker(symbol)
        expirations = ticker.options
        if not expirations:
            print("No expirations found.")
            return

        expiry = expirations[0]
        print(f"Using expiration: {expiry}")
        
        opts = ticker.option_chain(expiry)
        calls = opts.calls
        
        print("\n--- SAMPLE CALLS (First 5) ---")
        print(calls[['strike', 'lastPrice', 'volume', 'openInterest', 'lastTradeDate']].head())
        
        # Check timestamps
        tz_eastern = pytz.timezone('US/Eastern')
        now = datetime.now(tz_eastern)
        today_date = now.date()
        
        print(f"\nCurrent Date (ET): {today_date}")
        
        print("\n--- TIMESTAMP CHECK ---")
        for index, row in calls.head().iterrows():
            ts = row['lastTradeDate']
            if ts.tzinfo is None: ts = pytz.utc.localize(ts)
            ts_et = ts.astimezone(tz_eastern)
            is_today = ts_et.date() == today_date
            print(f"Strike: {row['strike']} | Last Trade: {ts_et} | Is Today? {is_today} | Volume: {row['volume']}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify_gamma_volume()
