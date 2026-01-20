import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
SYMBOL = "GOOGL"

def check_polygon_last_trade():
    print(f"\n--- Checking Polygon LAST TRADE for {SYMBOL} ---")
    if not POLYGON_API_KEY:
        print("❌ No POLYGON_API_KEY")
        return
        
    url = f"https://api.polygon.io/v2/last/trade/{SYMBOL}?apiKey={POLYGON_API_KEY}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ Status 200: {json.dumps(data, indent=2)}")
            if data.get('results'):
                print(f"Last Price (p): {data['results'].get('p')}")
        else:
            print(f"❌ Error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    check_polygon_last_trade()
