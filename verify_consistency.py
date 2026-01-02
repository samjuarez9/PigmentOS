import requests
import json
import os
from datetime import datetime

# Load Environment Variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Credentials
POLYGON_KEY = os.getenv("POLYGON_API_KEY")
ALPACA_KEY = "PKD66OSCNTGDQ2ORIX4RGSKGI5"
ALPACA_SECRET = "9eSKSK2CchHQbFFwMYr1tnwZgu8MNZEMNfdXqVYwyF5M"

if not POLYGON_KEY:
    print("❌ Error: POLYGON_API_KEY not found in environment.")
    exit(1)

# Helper to format timestamp
def format_ts(ts_ns):
    # Handle nanoseconds (Polygon) vs ISO string (Alpaca)
    if isinstance(ts_ns, int):
        return datetime.fromtimestamp(ts_ns / 1e9).isoformat()
    return ts_ns

def verify_consistency(symbol):
    print(f"\n⚖️  Verifying Consistency for {symbol}...\n")
    
    # 1. Fetch Polygon Snapshot
    print("1️⃣  Fetching Polygon Data...")
    poly_url = f"https://api.polygon.io/v3/snapshot/options/{symbol}/{symbol}" # Snapshot for single ticker
    # Note: Polygon snapshot endpoint is usually /v3/snapshot/options/{underlying}?contract={symbol} or similar
    # Let's use the one we know works: /v3/snapshot/options/{underlying} and filter, OR /v3/quotes/{symbol} if allowed? No.
    # Polygon expects "O:" prefix for options in some endpoints, or just the ticker.
    # The 404 suggests "SPY260102C00500000" was not found.
    # Let's try adding "O:" prefix which is standard for Polygon Options tickers.
    underlying = "SPY"
    poly_ticker = f"O:{symbol}"
    poly_url = f"https://api.polygon.io/v3/snapshot/options/{underlying}/{poly_ticker}"
    
    poly_data = {}
    try:
        resp = requests.get(poly_url, params={"apiKey": POLYGON_KEY}, timeout=10)
        if resp.status_code == 200:
            full_resp = resp.json()
            poly_data = full_resp.get("results", {})
            # Debug: Print full response to see structure
            print(f"   🔍 Polygon Raw Data: {json.dumps(poly_data, indent=2)}")
        else:
            print(f"   ❌ Polygon Error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"   ❌ Polygon Exception: {e}")

    # 2. Fetch Alpaca Latest Trade
    print("2️⃣  Fetching Alpaca Data...")
    alpaca_url = f"https://data.alpaca.markets/v1beta1/options/trades/latest?symbols={symbol}"
    headers = {
        "APCA-API-KEY-ID": ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET
    }
    
    alpaca_data = {}
    try:
        resp = requests.get(alpaca_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            alpaca_data = resp.json().get("trades", {}).get(symbol, {})
        else:
            print(f"   ❌ Alpaca Error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"   ❌ Alpaca Exception: {e}")

    # 3. Compare
    print("\n📊 COMPARISON:")
    
    # Polygon Last Trade (or Day Close if Last Trade missing)
    poly_last_trade = poly_data.get("last_trade", {})
    if poly_last_trade:
        poly_price = poly_last_trade.get("p")
        poly_time = poly_last_trade.get("t")
    else:
        # Fallback to Day Close
        day_data = poly_data.get("day", {})
        poly_price = day_data.get("close")
        poly_time = day_data.get("last_updated") # nanoseconds
    
    # Alpaca Last Trade
    alpaca_price = alpaca_data.get("p")
    alpaca_time = alpaca_data.get("t") # ISO string
    
    print(f"   Polygon Price: ${poly_price}")
    print(f"   Alpaca Price:  ${alpaca_price}")
    
    print(f"   Polygon Time:  {format_ts(poly_time)}")
    print(f"   Alpaca Time:   {alpaca_time}")
    
    if poly_price and alpaca_price:
        diff = abs(poly_price - alpaca_price)
        if diff < 0.02:
            print("\n✅ MATCH! Prices are identical (or extremely close).")
            print("   This confirms both APIs are seeing the same market reality.")
        else:
            print(f"\n⚠️  MISMATCH! Price difference: ${diff:.2f}")
            print("   (This might be due to slightly different delay windows or aggregation).")
    else:
        print("\n❌ Could not compare (missing data).")

# Run Test
verify_consistency("SPY260102C00500000") # Use our known active symbol
