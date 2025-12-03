import yfinance as yf
import pandas as pd
from datetime import datetime
import pytz
import time

def check_dates():
    symbol = "SPY"
    print(f"Checking {symbol}...")
    ticker = yf.Ticker(symbol)
    
    # Check Options
    try:
        expirations = ticker.options
        if not expirations:
            print("No expirations found")
            return
            
        expiry = expirations[0]
        print(f"Fetching expiry: {expiry}")
        
        opts = ticker.option_chain(expiry)
        calls = opts.calls
        
        if calls.empty:
            print("No calls found")
            return
            
        # Get a sample row
        row = calls.iloc[0]
        last_trade_date = row['lastTradeDate']
        
        print(f"Sample Last Trade Date (Raw): {last_trade_date}")
        print(f"Type: {type(last_trade_date)}")
        
        if hasattr(last_trade_date, 'tz'):
            print(f"Timezone: {last_trade_date.tz}")
            
        # Compare with US/Eastern
        eastern = pytz.timezone('US/Eastern')
        now_eastern = datetime.now(eastern)
        today_eastern = now_eastern.date()
        
        print(f"Now (Eastern): {now_eastern}")
        print(f"Today (Eastern): {today_eastern}")
        
        trade_date = last_trade_date.date()
        print(f"Trade Date: {trade_date}")
        
        if trade_date == today_eastern:
            print("MATCH: Trade date matches today (Eastern)")
        else:
            print("MISMATCH: Trade date does NOT match today (Eastern)")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_dates()
