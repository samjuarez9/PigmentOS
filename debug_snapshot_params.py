import os
import requests
from datetime import datetime
from dotenv import load_dotenv
import json

load_dotenv()

API_KEY = os.getenv("POLYGON_API_KEY")
SYMBOL = "GOOG"

def debug_snapshot():
    if not API_KEY:
        print("❌ No API Key")
        return

    url = f"https://api.polygon.io/v3/snapshot/options/{SYMBOL}"
    
    # Same params as run.py
    params = {
        "apiKey": API_KEY,
        "limit": 50,
        "expiration_date.gte": datetime.now().strftime("%Y-%m-%d"),
        "order": "desc",
        "sort": "open_interest"
    }
    
    print(f"Params: {params}")

    try:
        resp = requests.get(url, params=params, timeout=10)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            print(f"Results count: {len(results)}")
            if results:
                print("First result day volume:", results[0].get("day", {}).get("volume"))
        else:
            print(f"Error: {resp.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    debug_snapshot()
