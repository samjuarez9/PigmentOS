import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

def check_polygon_option_bars(option_ticker):
    """
    Check if we can get historical bars for a specific option ticker.
    """
    print(f"\n--- Checking Historical Bars for {option_ticker} ---")
    
    # Date range: Last 30 days
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    # Endpoint: v2/aggs/ticker/{stocksTicker}/range/{multiplier}/{timespan}/{from}/{to}
    # For options, the ticker is the OCC symbol (e.g., O:SPY240119C00400000)
    url = f"https://api.polygon.io/v2/aggs/ticker/{option_ticker}/range/1/hour/{start_date}/{end_date}"
    
    params = {
        "apiKey": POLYGON_API_KEY,
        "adjusted": "true",
        "sort": "asc",
        "limit": 100
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            print(f"✅ Success! Found {len(results)} bars.")
            if results:
                print(f"Sample Bar: {results[0]}")
        else:
            print(f"❌ Failed. Status: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Error: {e}")

def check_lotto_candidates(underlying="SPY"):
    """
    Check if we can find 'lotto' trades (Low Delta, Short DTE) via Snapshot API.
    """
    print(f"\n--- Checking Lotto Candidates for {underlying} ---")
    
    # v3 Snapshot Endpoint
    url = f"https://api.polygon.io/v3/snapshot/options/{underlying}"
    
    # Lotto Criteria:
    # - 0-7 DTE (Short term)
    # - OTM (Out of the Money) -> We'll filter by Delta < 0.2 (approx)
    
    # Note: Polygon snapshot doesn't allow filtering by Delta directly in params,
    # so we have to fetch and filter. We can filter by strike to narrow it down.
    
    params = {
        "apiKey": POLYGON_API_KEY,
        "limit": 250,
        # "expiration_date.lte": ... # Can filter by expiry
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            print(f"Fetched {len(results)} contracts. Filtering for Lottos...")
            
            lottos = []
            for r in results:
                details = r.get("details", {})
                greeks = r.get("greeks", {})
                day = r.get("day", {})
                
                if not greeks or not day: continue
                
                delta = abs(float(greeks.get("delta") or 0))
                volume = float(day.get("volume") or 0)
                expiry = details.get("expiration_date")
                
                # Check Lotto Criteria
                # 1. Low Delta (e.g., < 0.15)
                # 2. High Volume (Liquid)
                # 3. Short DTE (Need to calc)
                
                if 0.01 < delta < 0.15 and volume > 1000:
                    lottos.append({
                        "ticker": details.get("ticker"),
                        "delta": delta,
                        "volume": volume,
                        "expiry": expiry,
                        "price": day.get("close")
                    })
            
            print(f"Found {len(lottos)} potential lotto candidates.")
            if lottos:
                print(f"Sample Lotto: {lottos[0]}")
                
        else:
            print(f"❌ Failed. Status: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    # Test with a known active option if possible, or just try to find one
    # For now, let's try to find a valid option ticker from the snapshot first
    
    # 1. Get a valid option ticker from snapshot
    url = f"https://api.polygon.io/v3/snapshot/options/SPY?apiKey={POLYGON_API_KEY}&limit=1"
    try:
        r = requests.get(url)
        if r.status_code == 200:
            res = r.json().get("results", [])
            if res:
                ticker = res[0]["details"]["ticker"]
                check_polygon_option_bars(ticker)
            else:
                print("Could not find any SPY options to test bars.")
        else:
            print("Failed to fetch snapshot for setup.")
    except Exception as e:
        print(f"Setup Error: {e}")

    # 2. Check Lotto Logic
    check_lotto_candidates("SPY")
