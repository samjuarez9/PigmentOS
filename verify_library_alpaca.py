import requests
import os
import json

# Local URL
BASE_URL = "http://127.0.0.1:8001"

def test_library_endpoint(symbol="NVDA"):
    print(f"Testing /api/library/options for {symbol}...")
    try:
        url = f"{BASE_URL}/api/library/options"
        params = {"symbol": symbol}
        
        resp = requests.get(url, params=params, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            if "data" in data:
                trades = data["data"]
                print(f"✅ Success! Received {len(trades)} trades.")
                if len(trades) > 0:
                    print("Sample Trade:")
                    print(json.dumps(trades[0], indent=2))
                    
                    # Verify fields
                    t = trades[0]
                    required = ["ticker", "strike", "type", "expiry", "premium", "lastPrice"]
                    missing = [f for f in required if f not in t]
                    if missing:
                        print(f"❌ Missing fields: {missing}")
                    else:
                        print("✅ All required fields present.")
                else:
                    print("⚠️ No trades returned (might be expected if no recent activity).")
            else:
                print("❌ Response missing 'data' key.")
                print(data)
        else:
            print(f"❌ Error: {resp.status_code}")
            print(resp.text)
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_library_endpoint()
