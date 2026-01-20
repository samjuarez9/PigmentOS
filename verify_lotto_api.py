import requests
import json
import time

BASE_URL = "http://localhost:8001/api"

def test_lotto_feed():
    print("\n--- Testing Lotto Feed ---")
    try:
        resp = requests.get(f"{BASE_URL}/whales?lotto=true&limit=10")
        if resp.status_code == 200:
            data = resp.json().get('data', [])
            print(f"✅ Success! Fetched {len(data)} lotto trades.")
            if data:
                print(f"First Item Type: {type(data[0])}")
                print(f"First Item: {data[0]}")
                print(f"Sample Lotto: {data[0].get('ticker')} | Delta: {data[0].get('delta')} | Lotto Tag: {data[0].get('is_lotto')}")
        else:
            print(f"❌ Failed. Status: {resp.status_code}")
            print(resp.text)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def test_history_endpoint(ticker):
    print(f"\n--- Testing History Endpoint for {ticker} ---")
    try:
        resp = requests.get(f"{BASE_URL}/options/history/{ticker}")
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            print(f"✅ Success! Fetched {len(results)} historical bars.")
            if results:
                print(f"Sample Bar: {results[0]}")
        else:
            print(f"❌ Failed. Status: {resp.status_code}")
            print(resp.text)
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    # 1. Test Feed
    test_lotto_feed()
    
    # 2. Test History (using a known ticker or one from feed)
    # Let's try to get one from the feed first
    try:
        resp = requests.get(f"{BASE_URL}/whales?lotto=true&limit=1")
        if resp.status_code == 200 and resp.json():
            ticker = resp.json()[0]['ticker']
            test_history_endpoint(ticker)
        else:
            print("Could not fetch a lotto trade to test history. Testing with hardcoded SPY option.")
            # Fallback to a likely existing option (needs to be real for Polygon)
            # This might fail if we don't have a real active ticker.
            # We'll skip if we can't find one.
    except:
        pass
        
    # 3. Hardcoded Test (Fallback)
    test_history_endpoint("O:SPY260106C00500000")
