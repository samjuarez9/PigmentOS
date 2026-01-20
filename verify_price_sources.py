import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
SYMBOL = "GOOGL"

def check_finnhub():
    print(f"\n--- Checking Finnhub for {SYMBOL} ---")
    if not FINNHUB_API_KEY:
        print("❌ No FINNHUB_API_KEY")
        return
    
    url = f"https://finnhub.io/api/v1/quote?symbol={SYMBOL}&token={FINNHUB_API_KEY}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ Status 200: {json.dumps(data, indent=2)}")
            print(f"Current Price (c): {data.get('c')}")
        else:
            print(f"❌ Error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"❌ Exception: {e}")

def check_polygon_prev():
    print(f"\n--- Checking Polygon PREV for {SYMBOL} ---")
    if not POLYGON_API_KEY:
        print("❌ No POLYGON_API_KEY")
        return
        
    url = f"https://api.polygon.io/v2/aggs/ticker/{SYMBOL}/prev?apiKey={POLYGON_API_KEY}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ Status 200: {json.dumps(data, indent=2)}")
            if data.get('results'):
                print(f"Prev Close (c): {data['results'][0].get('c')}")
        else:
            print(f"❌ Error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"❌ Exception: {e}")

def check_polygon_snapshot():
    print(f"\n--- Checking Polygon SNAPSHOT for {SYMBOL} ---")
    if not POLYGON_API_KEY:
        print("❌ No POLYGON_API_KEY")
        return
        
    url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{SYMBOL}?apiKey={POLYGON_API_KEY}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            # print(f"✅ Status 200: {json.dumps(data, indent=2)}")
            ticker_data = data.get('ticker', {})
            print(f"Last Trade Price: {ticker_data.get('lastTrade', {}).get('p')}")
            print(f"Day Close: {ticker_data.get('day', {}).get('c')}")
            print(f"Prev Day Close: {ticker_data.get('prevDay', {}).get('c')}")
            print(f"Todays Change: {ticker_data.get('todaysChange')}")
        else:
            print(f"❌ Error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    check_finnhub()
    check_polygon_prev()
    check_polygon_snapshot()
