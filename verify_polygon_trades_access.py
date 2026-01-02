import os
import requests
import json
from datetime import datetime, timedelta

# Load API Key from .env or use a placeholder if not found (though it should be in env)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

API_KEY = os.getenv("POLYGON_API_KEY")

if not API_KEY:
    print("❌ Error: POLYGON_API_KEY not found in environment variables.")
    exit(1)

def test_endpoint(name, url, params):
    print(f"\nTesting {name}...")
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            if results:
                print(f"✅ Success! Found {len(results)} records.")
                print(f"   Sample: {results[0]}")
                return True
            else:
                print(f"⚠️  Success (200 OK), but no results found. (Market might be closed or date invalid)")
                return True # Still accessible
        elif resp.status_code == 401:
            print(f"❌ Access Denied (401). Your plan likely does not support this endpoint.")
            return False
        elif resp.status_code == 403:
            print(f"❌ Forbidden (403). Your plan likely does not support this endpoint.")
            return False
        else:
            print(f"⚠️  Error {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

# Use a recent trading day (Friday if today is weekend, or yesterday)
# For simplicity, let's try a hardcoded recent date known to be a trading day to avoid weekend issues
# Today is 2026-01-02 (Friday). Let's try yesterday 2026-01-01 (Holiday?) -> Let's try 2025-12-31 (Wednesday) just to be safe and sure.
# Actually, let's just use "yesterday" logic but fallback to a known date if needed.
target_date = "2025-12-31" 
symbol = "SPY" # Underlying
# For options, we need a specific contract. Let's find one first via snapshot or just use underlying trades for now.
# The user asked about "Unusual Whales", which implies OPTIONS trades.
# So we must test OPTIONS trades, not just stock trades.

print(f"Using API Key: {API_KEY[:5]}...{API_KEY[-4:]}")

# 1. Find an active option contract to test
print(f"\n1. Finding an active option contract for {symbol}...")
snapshot_url = f"https://api.polygon.io/v3/snapshot/options/{symbol}"
params = {
    "apiKey": API_KEY,
    "limit": 1,
    "strike_price.gte": 500 # Arbitrary
}
contract_ticker = None
try:
    resp = requests.get(snapshot_url, params=params, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        if data.get("results"):
            contract_ticker = data["results"][0]["details"]["ticker"]
            print(f"   Found contract: {contract_ticker}")
        else:
            print("   No contracts found in snapshot.")
    else:
        print(f"   Snapshot failed: {resp.status_code}")
except Exception as e:
    print(f"   Snapshot exception: {e}")

if not contract_ticker:
    print("❌ Cannot proceed without a contract ticker.")
    exit(1)

# 2. Test Trades API for that option
trades_url = f"https://api.polygon.io/v3/trades/{contract_ticker}"
trades_params = {
    "apiKey": API_KEY,
    "timestamp": target_date,
    "limit": 5
}
trades_access = test_endpoint("Options Trades API", trades_url, trades_params)

# 3. Test Quotes API for that option (needed for Bid/Ask comparison)
quotes_url = f"https://api.polygon.io/v3/quotes/{contract_ticker}"
quotes_params = {
    "apiKey": API_KEY,
    "timestamp": target_date,
    "limit": 5
}
quotes_access = test_endpoint("Options Quotes API (NBBO)", quotes_url, quotes_params)

print("\n=== SUMMARY ===")
if trades_access and quotes_access:
    print("✅ GREAT NEWS: You have access to BOTH Trades and Quotes!")
    print("   You CAN implement the 'Quote Rule' to determine Buy/Sell side.")
elif trades_access:
    print("⚠️  Partial Access: You have Trades but NOT Quotes.")
    print("   You can see individual trades, but cannot accurately determine Buy/Sell side without Quotes.")
else:
    print("❌ No Access: Your plan does not support granular Options Trades/Quotes.")
