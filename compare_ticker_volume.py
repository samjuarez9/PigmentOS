import sys
import os
import requests
import json
from datetime import datetime
import pytz
from dotenv import load_dotenv

# Load environment variables
load_dotenv("/Users/newuser/PigmentOS/.env")

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

ALPACA_DATA_URL = "https://data.alpaca.markets/v1beta1/options"

def compare_ticker_volume(ticker="AMD"):
    print(f"🧪 Comparing Data Volume for {ticker}: Polygon vs Alpaca")
    
    if not ALPACA_API_KEY or not POLYGON_API_KEY:
        print("❌ API Keys missing in .env")
        return

    # --- ALPACA ---
    print(f"\n1. Fetching {ticker} chain from Alpaca...")
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
        "Accept": "application/json"
    }
    
    alpaca_total = 0
    alpaca_active = 0
    
    url = f"{ALPACA_DATA_URL}/snapshots/{ticker}"
    params = {"limit": 1000} # Max limit is 1000
    
    try:
        start_time = datetime.now()
        # Alpaca pagination uses 'page_token'
        next_token = None
        
        while True:
            current_params = params.copy()
            if next_token:
                current_params["page_token"] = next_token
                
            resp = requests.get(url, headers=headers, params=current_params, timeout=20)
            if resp.status_code != 200:
                print(f"❌ Alpaca Error: {resp.text}")
                break
                
            data = resp.json()
            snapshots = data.get("snapshots", {})
            alpaca_total += len(snapshots)
            
            for _, snapshot in snapshots.items():
                if snapshot.get("dailyBar", {}).get("v", 0) > 0:
                    alpaca_active += 1
            
            next_token = data.get("next_page_token")
            if not next_token:
                break
                
            print(f"   Alpaca Page: {len(snapshots)} contracts...", end="\r")
            
        print(f"✅ Alpaca: {alpaca_total} contracts found ({alpaca_active} active with vol > 0)")
        print(f"   Time taken: {(datetime.now() - start_time).total_seconds():.2f}s")
            
    except Exception as e:
        print(f"❌ Alpaca Exception: {e}")


    # --- POLYGON ---
    print(f"\n2. Fetching {ticker} chain from Polygon...")
    poly_total = 0
    poly_active = 0
    
    # Polygon doesn't have a direct "snapshot all for underlying" in the same way that returns EVERYTHING in one go easily without pagination if it's huge.
    # But /v3/snapshot/options/{underlying} is the equivalent.
    poly_url = f"https://api.polygon.io/v3/snapshot/options/{ticker}"
    poly_params = {"apiKey": POLYGON_API_KEY, "limit": 250} # Polygon max limit per page is often 250
    
    try:
        start_time = datetime.now()
        # We need to handle pagination to get a fair count
        next_url = poly_url
        page_count = 0
        
        while next_url:
            resp = requests.get(next_url, params=poly_params if page_count == 0 else None, timeout=20)
            if resp.status_code != 200:
                print(f"❌ Polygon Error: {resp.text}")
                break
                
            data = resp.json()
            results = data.get("results", [])
            poly_total += len(results)
            
            for r in results:
                if r.get("day", {}).get("volume", 0) > 0:
                    poly_active += 1
            
            next_url = data.get("next_url")
            if next_url:
                next_url += f"&apiKey={POLYGON_API_KEY}"
            
            page_count += 1
            print(f"   Page {page_count}: {len(results)} contracts...", end="\r")
            
            # Safety break for very large chains during test
            if page_count > 20: 
                print("\n   (Stopping after 20 pages for speed)")
                break
                
        print(f"\n✅ Polygon: {poly_total} contracts found ({poly_active} active with vol > 0)")
        print(f"   Time taken: {(datetime.now() - start_time).total_seconds():.2f}s")
        
    except Exception as e:
        print(f"❌ Polygon Exception: {e}")

    # --- COMPARISON ---
    print("\n--- 📊 VOLUME COMPARISON ---")
    print(f"Ticker: {ticker}")
    print(f"{'METRIC':<15} | {'ALPACA':<15} | {'POLYGON':<15} | {'WINNER'}")
    print("-" * 60)
    
    winner_total = "Alpaca" if alpaca_total > poly_total else "Polygon"
    if alpaca_total == poly_total: winner_total = "Tie"
    
    winner_active = "Alpaca" if alpaca_active > poly_active else "Polygon"
    if alpaca_active == poly_active: winner_active = "Tie"
    
    print(f"{'Total Contracts':<15} | {alpaca_total:<15} | {poly_total:<15} | {winner_total}")
    print(f"{'Active (Vol>0)':<15} | {alpaca_active:<15} | {poly_active:<15} | {winner_active}")
    print("-" * 60)

if __name__ == "__main__":
    target = "AMD"
    if len(sys.argv) > 1:
        target = sys.argv[1]
    compare_ticker_volume(target)
