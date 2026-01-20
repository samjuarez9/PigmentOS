import os
import requests
from dotenv import load_dotenv
import json

load_dotenv()

API_KEY = os.getenv("POLYGON_API_KEY")
SYMBOL = "GOOG"

def check_snapshot():
    if not API_KEY:
        print("❌ No API Key found")
        return

    url = f"https://api.polygon.io/v3/snapshot/options/{SYMBOL}"
    params = {
        "apiKey": API_KEY,
        "limit": 5,
        "strike_price.gte": 170, # Near money
        "expiration_date.gte": "2025-01-12"
    }

    print(f"📡 Requesting Snapshot for {SYMBOL}...")
    try:
        resp = requests.get(url, params=params, timeout=10)
        print(f"Status Code: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            print(f"✅ Success! Found {len(results)} contracts.")
            if results:
                print("Sample Contract:", json.dumps(results[0], indent=2))
        else:
            print(f"❌ Failed: {resp.text}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_snapshot()
