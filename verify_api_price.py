import requests
import time

# Wait for server to reload if needed
time.sleep(2)

try:
    url = "http://localhost:8001/api/price?symbol=SPY"
    print(f"Fetching {url}...")
    resp = requests.get(url, timeout=5)
    
    if resp.status_code == 200:
        data = resp.json()
        print("✅ Success!")
        print(f"Symbol: {data.get('symbol')}")
        print(f"Price: {data.get('price')}")
        print(f"Source: {data.get('source')}")
        print(f"Timestamp: {data.get('timestamp')}")
    else:
        print(f"❌ Failed: {resp.status_code}")
        print(resp.text)
except Exception as e:
    print(f"❌ Error: {e}")
