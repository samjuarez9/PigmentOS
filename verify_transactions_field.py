import os
import requests
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

if not POLYGON_API_KEY:
    print("❌ POLYGON_API_KEY not found in .env")
    exit(1)

def verify_transactions_field():
    print(f"🔑 Using API Key: {POLYGON_API_KEY[:5]}...")
    
    # 1. Find an active contract (using SPY)
    print("\n🔎 Finding an active SPY contract...")
    chain_url = "https://api.polygon.io/v3/snapshot/options/SPY"
    params = {
        "apiKey": POLYGON_API_KEY,
        "limit": 1,
        "strike_price.gte": 500, # Arbitrary active range
        "expiration_date.gte": datetime.now().strftime("%Y-%m-%d")
    }
    
    try:
        resp = requests.get(chain_url, params=params, timeout=10)
        if resp.status_code != 200:
            print(f"❌ Failed to fetch chain: {resp.status_code} - {resp.text}")
            return
            
        data = resp.json()
        results = data.get("results", [])
        if not results:
            print("❌ No contracts found.")
            return
            
        contract = results[0]
        ticker = contract["details"]["ticker"]
        print(f"✅ Found contract: {ticker}")
        
        # 2. Check Snapshot API for 'n' (transactions)
        print(f"\n📸 Checking Snapshot API for {ticker}...")
        # Correct endpoint: /v3/snapshot/options/{underlying}/{contract}
        underlying = "SPY" # We know we are searching for SPY
        snapshot_url = f"https://api.polygon.io/v3/snapshot/options/{underlying}/{ticker}"
        snap_resp = requests.get(snapshot_url, params={"apiKey": POLYGON_API_KEY}, timeout=10)
        
        if snap_resp.status_code == 200:
            snap_data = snap_resp.json().get("results", [])
            # Handle if results is a list (common in Polygon APIs)
            if isinstance(snap_data, list):
                if not snap_data:
                    print("❌ Snapshot results list is empty.")
                    return
                snap_data = snap_data[0]
            
            day_data = snap_data.get("day", {})
            
            print(f"   Response keys in 'day': {list(day_data.keys())}")
            
            if "n" in day_data:
                print(f"   ✅ FOUND 'n' (transactions) in Snapshot! Value: {day_data['n']}")
            else:
                print("   ❌ 'n' (transactions) NOT found in Snapshot 'day' object.")
                print(f"   Full 'day' object: {json.dumps(day_data, indent=2)}")
        else:
            print(f"❌ Snapshot failed: {snap_resp.status_code}")

        # 3. Check Aggregates API for 'n' (transactions)
        print(f"\n📊 Checking Aggregates API for {ticker}...")
        
        # Try to get data for the last 5 days to find ANY volume
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
             
        aggs_url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}"
        aggs_resp = requests.get(aggs_url, params={"apiKey": POLYGON_API_KEY}, timeout=10)
        
        if aggs_resp.status_code == 200:
            aggs_data = aggs_resp.json().get("results", [])
            if aggs_data:
                # Find a bar with volume
                for bar in aggs_data:
                    if bar.get('v', 0) > 0:
                        print(f"   Found bar for {datetime.fromtimestamp(bar['t']/1000).strftime('%Y-%m-%d')}")
                        print(f"   Response keys in bar: {list(bar.keys())}")
                        if "n" in bar:
                            print(f"   ✅ FOUND 'n' (transactions) in Aggregates! Value: {bar['n']}")
                        else:
                            print("   ❌ 'n' (transactions) NOT found in Aggregates.")
                        break
                else:
                     print("   ⚠️ No bars with volume found in last 5 days.")
            else:
                print("   ⚠️ No aggregates data found for last 5 days.")
        else:
            print(f"❌ Aggregates failed: {aggs_resp.status_code}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    verify_transactions_field()
