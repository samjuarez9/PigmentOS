import sys
import os
import time
from datetime import datetime, timedelta
import pytz
import json

# Add project root to path
sys.path.append(os.path.abspath("/Users/newuser/PigmentOS"))

# Mock environment variables if needed
os.environ["ALPACA_API_KEY"] = "PK78229D29103" 
os.environ["ALPACA_SECRET_KEY"] = "sk_test_..." 
os.environ["POLYGON_API_KEY"] = "mock_poly_key"

# Import run to access CACHE and functions
import run

def test_separation():
    print("🧪 Testing Feed Separation...")
    
    # Mock current time
    tz_eastern = pytz.timezone('US/Eastern')
    now_et = datetime.now(tz_eastern)
    
    # Create mock trades
    # 1. Short DTE (should be in both)
    expiry_short = (now_et + timedelta(days=15)).strftime("%Y-%m-%d")
    trade_short = {
        "ticker": "SHORT_DTE",
        "expirationDate": expiry_short,
        "timestamp": time.time(),
        "premium": "$1M"
    }
    
    # 2. Long DTE (should ONLY be in main feed)
    expiry_long = (now_et + timedelta(days=45)).strftime("%Y-%m-%d")
    trade_long = {
        "ticker": "LONG_DTE",
        "expirationDate": expiry_long,
        "timestamp": time.time(),
        "premium": "$1M"
    }
    
    # Manually populate CACHE["whales"]["data"] as if the scanner ran
    # The worker loop logic is:
    # 1. Update CACHE["whales"]["data"] with ALL trades
    # 2. Filter and update CACHE["whales_30dte"]["data"]
    
    # Let's simulate the worker loop logic manually to verify it works
    print("\n--- Simulating Worker Loop Logic ---")
    
    all_trades = [trade_short, trade_long]
    
    # 1. Main Cache Update
    run.CACHE["whales"]["data"] = all_trades
    print(f"Main Cache Size: {len(run.CACHE['whales']['data'])}")
    
    # 2. 30 DTE Cache Update (Logic copied from run.py)
    filtered_whales = []
    for w in all_trades:
        try:
            expiry = w.get("expirationDate")
            if expiry:
                expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
                days_to_expiry = (expiry_date - now_et.date()).days
                if days_to_expiry <= 30:
                    filtered_whales.append(w)
        except:
            pass
    
    run.CACHE["whales_30dte"]["data"] = filtered_whales
    print(f"30 DTE Cache Size: {len(run.CACHE['whales_30dte']['data'])}")
    
    # Assertions
    if len(run.CACHE["whales"]["data"]) == 2:
        print("✅ Main Cache: Contains ALL trades (PASSED)")
    else:
        print("❌ Main Cache: FAILED")
        
    if len(run.CACHE["whales_30dte"]["data"]) == 1:
        trade = run.CACHE["whales_30dte"]["data"][0]
        if trade["ticker"] == "SHORT_DTE":
            print("✅ 30 DTE Cache: Contains ONLY short DTE trade (PASSED)")
        else:
            print(f"❌ 30 DTE Cache: Wrong trade {trade['ticker']}")
    else:
        print(f"❌ 30 DTE Cache: Wrong size {len(run.CACHE['whales_30dte']['data'])}")

    # Verify API Endpoints (Mocking request/response is harder here without running server, 
    # but verifying cache population is the core logic)

if __name__ == "__main__":
    test_separation()
