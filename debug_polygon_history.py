import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("POLYGON_API_KEY")
SYMBOL = "NVDA"
# Try to get data for last Friday (assuming today is Monday/Tuesday, let's pick a known past trading day)
# If today is Jan 12 (Monday), last Friday was Jan 9.
PAST_DATE = "2025-01-09" 

def test_snapshot_history():
    print(f"Testing Polygon Snapshot for {SYMBOL} on {PAST_DATE}...")
    
    # URL for Options Snapshot
    url = f"https://api.polygon.io/v3/snapshot/options/{SYMBOL}"
    
    # Try various parameters that might trigger historical data
    # Polygon docs usually say Snapshot is real-time, but let's verify.
    # Sometimes 'timestamp' or 'date' works.
    
    params_list = [
        {"apiKey": API_KEY, "limit": 1, "expiration_date.gte": "2025-01-20"}, # Control (Current)
        {"apiKey": API_KEY, "limit": 1, "timestamp": PAST_DATE},
        {"apiKey": API_KEY, "limit": 1, "date": PAST_DATE},
        {"apiKey": API_KEY, "limit": 1, "as_of": PAST_DATE}
    ]
    
    for params in params_list:
        print(f"\nTesting params: {json.dumps({k:v for k,v in params.items() if k!='apiKey'})}")
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                if results:
                    # Check the 'day' volume or timestamp to see if it matches our past date
                    first = results[0]
                    day_data = first.get("day", {})
                    last_updated = first.get("greeks", {}).get("last_updated", 0)
                    print(f"✅ Success! Got {len(results)} results.")
                    print(f"   Sample Vol: {day_data.get('volume')}")
                    print(f"   Last Updated: {last_updated}")
                else:
                    print("⚠️  200 OK but no results.")
            else:
                print(f"❌ Error {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_snapshot_history()
