import requests
import json

# Use a known liquid contract (SPY) to ensure volume and price variance
# Note: Adjust contract to a recent one if needed
CONTRACT = "O:SPY260130C00500000" # SPY Jan 30 2026 500 Call

def check_vwap_diff():
    try:
        print(f"Fetching history for {CONTRACT}...")
        # Local server URL
        url = f"http://localhost:8001/api/flow/vol_oi_history/{CONTRACT}?days=10"
        
        resp = requests.get(url)
        if resp.status_code != 200:
            print(f"Error: {resp.status_code} - {resp.text}")
            return

        data = resp.json()
        history = data.get("history", [])
        
        print(f"{'Date':<12} | {'Close':<10} | {'VWAP':<10} | {'Diff':<10}")
        print("-" * 50)
        
        for day in history:
            date = day.get("date")
            close = day.get("price", 0)
            vwap = day.get("vwap", 0)
            diff = abs(close - vwap)
            
            print(f"{date:<12} | {close:<10.2f} | {vwap:<10.2f} | {diff:<10.4f}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    check_vwap_diff()
