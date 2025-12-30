
import os
import requests
from datetime import datetime
import pytz
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("POLYGON_API_KEY")
if not API_KEY:
    print("❌ No API Key")
    exit(1)

# Get today's date
tz_eastern = pytz.timezone('US/Eastern')
today = datetime.now(tz_eastern).strftime('%Y-%m-%d')

print(f"Testing Polygon Intraday for {today}...")

# Try to get 1-minute bars for today (should be available even on free/starter plans, usually delayed)
url = f"https://api.polygon.io/v2/aggs/ticker/SPY/range/1/minute/{today}/{today}?adjusted=true&sort=desc&limit=1&apiKey={API_KEY}"

try:
    resp = requests.get(url, timeout=10)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        if data.get("results"):
            last_bar = data['results'][0]
            print(f"✅ Success! Latest Bar: {last_bar}")
            # Check timestamp of the bar
            ts = last_bar.get('t') / 1000
            bar_time = datetime.fromtimestamp(ts, tz_eastern)
            print(f"   Bar Time: {bar_time}")
        else:
            print("⚠️ Request success but no results (Market might be just opening or delayed data not ready?)")
            print(f"   Response: {data}")
    else:
        print(f"❌ Failed: {resp.text}")

except Exception as e:
    print(f"❌ Exception: {e}")
