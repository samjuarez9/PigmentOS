import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
SYMBOL = "NVDA"

def count_options_30_days():
    if not POLYGON_API_KEY:
        print("Error: POLYGON_API_KEY not found.")
        return

    print(f"Counting options for {SYMBOL} for the next 30 days...")
    
    # 1. Get Option Contracts Reference to count total available
    # This is better than snapshot for counting
    url = "https://api.polygon.io/v3/reference/options/contracts"
    
    now = datetime.now()
    end_date = now + timedelta(days=30)
    
    params = {
        "underlying_ticker": SYMBOL,
        "expiration_date.gte": now.strftime("%Y-%m-%d"),
        "expiration_date.lte": end_date.strftime("%Y-%m-%d"),
        "expired": "false",
        "limit": 1000,
        "apiKey": POLYGON_API_KEY
    }
    
    total_contracts = 0
    api_calls = 0
    
    while True:
        api_calls += 1
        resp = requests.get(url, params=params)
        if resp.status_code != 200:
            print(f"Error: {resp.status_code} - {resp.text}")
            break
            
        data = resp.json()
        results = data.get("results", [])
        count = len(results)
        total_contracts += count
        
        print(f"Page {api_calls}: Found {count} contracts...")
        
        if data.get("next_url"):
            url = data["next_url"] + f"&apiKey={POLYGON_API_KEY}"
            params = {} # params are in next_url
        else:
            break
            
    print("-" * 30)
    print(f"Total Active Contracts (0-30 DTE): {total_contracts}")
    print(f"Total API Calls required to fetch list: {api_calls}")
    print("-" * 30)
    
    # 2. Check Snapshot Size (Payload estimation)
    # Snapshot allows fetching by underlying, but has pagination/limits?
    # Actually v3 snapshot returns ALL if no limit? No, default limit is 10. Max is 250.
    
    print("Estimating Snapshot Load...")
    snapshot_url = f"https://api.polygon.io/v3/snapshot/options/{SYMBOL}"
    snapshot_params = {
        "apiKey": POLYGON_API_KEY,
        "limit": 250,
        "expiration_date.gte": now.strftime("%Y-%m-%d"),
        "expiration_date.lte": end_date.strftime("%Y-%m-%d")
    }
    
    snap_calls = 0
    snap_items = 0
    
    # Just do one call to see size
    resp = requests.get(snapshot_url, params=snapshot_params)
    if resp.status_code == 200:
        data = resp.json()
        results = data.get("results", [])
        snap_items = len(results)
        size_kb = len(resp.content) / 1024
        print(f"Snapshot Sample (Limit 250): {snap_items} items, {size_kb:.2f} KB")
        
        estimated_total_calls = (total_contracts / 250)
        estimated_total_size_mb = (size_kb * estimated_total_calls) / 1024
        
        print(f"Estimated Calls for Full Snapshot: {estimated_total_calls:.1f}")
        print(f"Estimated Payload Size: {estimated_total_size_mb:.2f} MB")
    else:
        print("Snapshot check failed")

if __name__ == "__main__":
    count_options_30_days()
