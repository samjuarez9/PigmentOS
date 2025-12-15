import os
import sys
import time
from datetime import datetime
import pytz
from dotenv import load_dotenv
import requests

# Load env vars
load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

if not POLYGON_API_KEY:
    print("❌ No POLYGON_API_KEY found in .env")
    sys.exit(1)

def fetch_unusual_options_polygon_standalone(symbol):
    """
    Standalone version of the fetch logic to verify API response.
    """
    try:
        # Hardcoded price for verification to avoid another API call
        current_price = 595.0 
        
        # Calculate strike range (±10%)
        strike_low = int(current_price * 0.90)
        strike_high = int(current_price * 1.10)
        
        # Polygon snapshot endpoint
        url = f"https://api.polygon.io/v3/snapshot/options/{symbol}"
        params = {
            "apiKey": POLYGON_API_KEY,
            "limit": 250,
            "strike_price.gte": strike_low,
            "strike_price.lte": strike_high
        }
        
        print(f"  -> Requesting {url}...")
        resp = requests.get(url, params=params, timeout=15)
        
        if resp.status_code != 200:
            print(f"Polygon Error: Status {resp.status_code}")
            return None
        
        data = resp.json()
        return data
        
    except Exception as e:
        print(f"Fetch Failed: {e}")
        return None

symbol = "SPY"
print(f"\n🔍 Fetching Polygon Options Snapshot for {symbol} (Standalone)...")

data = fetch_unusual_options_polygon_standalone(symbol)

if not data or "results" not in data:
    print("❌ No data returned from Polygon.")
    sys.exit(0)

results = data["results"]
print(f"✅ Received {len(results)} contracts.")

tz_eastern = pytz.timezone('US/Eastern')
now_et = datetime.now(tz_eastern)
today_date = now_et.date()

print(f"📅 Today is: {today_date}")

stale_count = 0
fresh_count = 0

print("\nChecking first 20 contracts for freshness:")
for contract in results[:20]: # Check first 20
    day_data = contract.get("day", {})
    last_updated = day_data.get("last_updated", 0)
    
    if last_updated:
        trade_time_obj = datetime.fromtimestamp(last_updated / 1_000_000_000, tz=tz_eastern)
        trade_date = trade_time_obj.date()
        
        is_fresh = trade_date == today_date
        status = "✅ FRESH" if is_fresh else "⚠️ STALE"
        
        if is_fresh:
            fresh_count += 1
        else:
            stale_count += 1
            
        print(f"  - {contract['details']['ticker']}: {trade_time_obj} ({status})")

print(f"\n📊 Summary:")
print(f"  Fresh (Today): {fresh_count}")
print(f"  Stale (Older): {stale_count}")

if stale_count > 0:
    print("\nℹ️  Polygon is returning stale data (expected for Snapshot).")
    print("   ✅ My logic in `run.py` WILL filter these out.")
else:
    print("\nℹ️  Polygon is only returning fresh data.")
    print("   ✅ My logic in `run.py` will accept these.")
