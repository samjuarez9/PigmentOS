
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("POLYGON_API_KEY")

if not API_KEY:
    print("❌ No POLYGON_API_KEY found in environment")
    exit(1)

print(f"Checking Polygon Access with Key: {API_KEY[:4]}...{API_KEY[-4:]}")

# 1. Check Previous Close (Free/Basic endpoint)
url = f"https://api.polygon.io/v2/aggs/ticker/SPY/prev?adjusted=true&apiKey={API_KEY}"
print(f"\nTesting Previous Close (v2/aggs/ticker/SPY/prev)...")
try:
    resp = requests.get(url, timeout=10)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        if data.get("results"):
            print(f"✅ Success! Price: {data['results'][0]['c']}")
        else:
            print("⚠️ Request success but no results:", data)
    else:
        print("❌ Failed:", resp.text)
except Exception as e:
    print(f"❌ Exception: {e}")

# 2. Check Real-Time/Delayed Last Trade (Stocks API)
url2 = f"https://api.polygon.io/v2/last/trade/SPY?apiKey={API_KEY}"
print(f"\nTesting Last Trade (v2/last/trade/SPY)...")
try:
    resp = requests.get(url2, timeout=10)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        print(f"✅ Success! Data: {resp.json()}")
    elif resp.status_code == 403:
        print("❌ 403 Forbidden - Likely no access to Real-Time/Delayed Stocks")
    else:
        print(f"❌ Failed: {resp.status_code} - {resp.text}")
except Exception as e:
    print(f"❌ Exception: {e}")
