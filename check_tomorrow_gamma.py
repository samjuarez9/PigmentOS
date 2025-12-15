import os
import requests
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv

load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
SYMBOL = "SPY"

def check_tomorrow_data():
    if not POLYGON_API_KEY:
        print("Error: POLYGON_API_KEY not found.")
        return

    tz_eastern = pytz.timezone('US/Eastern')
    now_et = datetime.now(tz_eastern)
    
    # Calculate Tomorrow (or next valid expiry)
    # Simple logic: just add 1 day, if weekend add more
    tomorrow = now_et + timedelta(days=1)
    while tomorrow.weekday() >= 5: # Skip Sat/Sun
        tomorrow += timedelta(days=1)
        
    expiry_date = tomorrow.strftime("%Y-%m-%d")
    print(f"Checking data for {SYMBOL} expiry: {expiry_date}...")
    
    # Polygon options chain snapshot endpoint
    url = f"https://api.polygon.io/v3/snapshot/options/{SYMBOL}"
    
    # Use a wide strike range just to see if ANY data exists
    params = {
        "apiKey": POLYGON_API_KEY,
        "limit": 10, 
        "expiration_date": expiry_date,
        "order": "asc",
        "sort": "strike_price"
    }
    
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "OK" and data.get("results"):
                count = len(data['results'])
                print(f"SUCCESS: Received {count} contracts for {expiry_date}.")
                print("Sample Contract:", data['results'][0]['details']['ticker'])
            else:
                print(f"FAILURE: No data returned for {expiry_date}. Status: {data.get('status')}")
        else:
            print(f"FAILURE: API Error {resp.status_code}: {resp.text}")
            
    except Exception as e:
        print(f"EXCEPTION: {e}")

if __name__ == "__main__":
    check_tomorrow_data()
