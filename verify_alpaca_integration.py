import sys
import os
import time
import json
from datetime import datetime

# Add current directory to path to import from run.py
sys.path.append(os.getcwd())

# Import the function to test
from run import fetch_alpaca_options_snapshot, ALPACA_API_KEY

def test_integration():
    print("🚀 Starting Alpaca Integration Verification...")
    
    if not ALPACA_API_KEY:
        print("❌ ALPACA_API_KEY not found in run.py configuration.")
        return

    # Test Symbol: SPY Call (likely liquid)
    # Note: You might need to update this to a valid future date if this expires
    # Using a far-out expiry to ensure it exists: SPY Jan 16 2026 500 Call
    test_symbol = "SPY260116C00500000" 
    
    print(f"🔎 Fetching Snapshot for {test_symbol}...")
    
    start_time = time.time()
    data = fetch_alpaca_options_snapshot(test_symbol)
    duration = time.time() - start_time
    
    if not data:
        print("❌ Fetch failed or returned None.")
        return

    print(f"✅ Fetch successful in {duration:.2f}s")
    print(json.dumps(data, indent=2))
    
    # Verify Structure
    quote = data.get("quote", {})
    trade = data.get("trade", {})
    
    bid = quote.get("bp") or quote.get("b")
    ask = quote.get("ap") or quote.get("a")
    trade_price = trade.get("p")
    
    print("\n📊 Data Analysis:")
    print(f"   Bid: {bid}")
    print(f"   Ask: {ask}")
    print(f"   Trade: {trade_price}")
    
    # Test Quote Rule Logic
    print("\n🧮 Testing Quote Rule Logic:")
    
    if bid and ask and trade_price:
        side = "NEUTRAL"
        if trade_price >= ask:
            side = "BUY (Aggressor paid Ask)"
        elif trade_price <= bid:
            side = "SELL (Aggressor hit Bid)"
        else:
            side = "NEUTRAL (Mid-market)"
            
        print(f"   Result: {side}")
    else:
        print("   ⚠️ Insufficient data for Quote Rule (missing bid/ask/trade)")

if __name__ == "__main__":
    test_integration()
