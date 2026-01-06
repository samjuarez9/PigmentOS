import os
import requests
import json
from datetime import datetime

# Load API Key from run.py or env (Simulating run.py's load)
# For this script, I'll try to grep it or just assume it's in the env if set, 
# but safer to read from run.py if possible. 
# Actually, I'll just ask the user's env or use the one I saw earlier if I can.
# I will try to read it from the file directly to be safe.

def get_api_key():
    return "z5qccs10zpN5nVqpB_BLuXp0Fo8ejdlw"

def check_polygon_trades():
    api_key = get_api_key()
    if not api_key:
        print("Could not find POLYGON_API_KEY")
        return

    # Use the SPY contract we found earlier: O:SPY260105C00500000
    # Note: If it's expired, this might return nothing. 
    # Let's try to find a contract from the snapshot first to be sure it has volume.
    
    # 1. Get a high volume contract
    print("Finding a high volume contract...")
    snapshot_url = f"https://api.polygon.io/v3/snapshot/options/SPY?apiKey={api_key}&limit=10"
    try:
        snap_resp = requests.get(snapshot_url)
        if snap_resp.status_code != 200:
            print(f"Snapshot failed: {snap_resp.status_code}")
            return
            
        results = snap_resp.json().get("results", [])
        # Sort by volume
        results.sort(key=lambda x: x.get("day", {}).get("volume", 0), reverse=True)
        
        if not results:
            print("No contracts found.")
            return
            
        target_contract = results[0]["details"]["ticker"]
        volume = results[0]["day"]["volume"]
        print(f"Targeting: {target_contract} (Vol: {volume})")
        
        # 2. Fetch Trades for this contract
        print(f"Fetching trades for {target_contract}...")
        trades_url = f"https://api.polygon.io/v3/trades/{target_contract}?apiKey={api_key}&limit=5"
        
        trades_resp = requests.get(trades_url)
        if trades_resp.status_code != 200:
            print(f"Trades fetch failed: {trades_resp.status_code}")
            print(trades_resp.text)
            return
            
        trades_data = trades_resp.json().get("results", [])
        
        print(f"\nFound {len(trades_data)} individual trades:")
        for t in trades_data:
            # SIP Timestamp is usually in nanoseconds
            ts_ns = t.get("sip_timestamp")
            dt = datetime.fromtimestamp(ts_ns / 1_000_000_000)
            size = t.get("size")
            price = t.get("price")
            print(f"  - Time: {dt.strftime('%H:%M:%S')} | Size: {size} | Price: ${price}")
            
        if len(trades_data) > 0:
            print("\n✅ SUCCESS: We can fetch individual historical trades.")
        else:
            print("\n⚠️ WARNING: No trades returned (might be empty for this specific query).")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_polygon_trades()
