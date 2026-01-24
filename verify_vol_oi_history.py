
import requests
import json

def test_vol_oi_history(ticker="O:NVDA260618C00152000", days=20):
    url = f"http://localhost:8001/api/flow/vol_oi_history/{ticker}?days={days}"
    try:
        print(f"Testing {url}...")
        response = requests.get(url)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            history = data.get("history", [])
            print(f"Returned {len(history)} history items.")
            if len(history) > 6:
                print("SUCCESS: Returned more than 6 items.")
            else:
                print(f"WARNING: Returned {len(history)} items (expected up to {days}). This might be due to lack of historical data.")
            
            # Print first and last date
            if history:
                print(f"Range: {history[0]['date']} to {history[-1]['date']}")
        else:
            print("Error response:", response.text)
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    # Use the contract ID found in previous step
    test_vol_oi_history("O:NVDA260618C00152000", 20)
