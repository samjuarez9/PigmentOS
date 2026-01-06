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

def parse_occ_symbol(symbol):
    """Parse OCC option symbol like SPY260102C00680000"""
    try:
        # Remove O: prefix if present
        clean = symbol.replace("O:", "")
        
        # Find where the date starts (first digit after letters)
        i = 0
        while i < len(clean) and clean[i].isalpha():
            i += 1
        
        underlying = clean[:i]
        rest = clean[i:]
        
        # YYMMDD format
        date_str = rest[:6]
        put_call = rest[6]  # C or P
        strike_raw = rest[7:]  # Price in 1/1000 dollars
        strike = float(strike_raw) / 1000
        
        # Parse expiration
        year = 2000 + int(date_str[:2])
        month = int(date_str[2:4])
        day = int(date_str[4:6])
        expiry = f"{year}-{month:02d}-{day:02d}"
        
        return {
            "underlying": underlying,
            "expiry": expiry,
            "put_call": put_call,
            "strike": strike
        }
    except:
        return None

def compare_real_data():
    print("🧪 Comparing Real Data: Polygon vs Alpaca (Standalone)")
    
    if not ALPACA_API_KEY or not POLYGON_API_KEY:
        print("❌ API Keys missing in .env")
        return

    # 1. Get a valid contract from Alpaca (Source of Truth for "Active" contracts)
    print("\n1. Finding an active contract from Alpaca...")
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
        "Accept": "application/json"
    }
    
    # Fetch SPY snapshots
    url = f"{ALPACA_DATA_URL}/snapshots/SPY"
    params = {"limit": 100} 
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code != 200:
            print(f"❌ Alpaca Error: {resp.text}")
            return
            
        data = resp.json()
        snapshots = data.get("snapshots", {})
        
        target_contract = None
        alpaca_data = None
        
        for symbol, snapshot in snapshots.items():
            daily_bar = snapshot.get("dailyBar", {})
            if daily_bar.get("v", 0) > 100: # Find one with decent volume
                target_contract = symbol
                alpaca_data = snapshot
                break
        
        if not target_contract:
            print("❌ No active SPY contracts found in Alpaca snapshot.")
            return
            
        print(f"✅ Found Contract: {target_contract}")
        
    except Exception as e:
        print(f"❌ Alpaca Exception: {e}")
        return

    # 2. Fetch same contract from Polygon
    print("\n2. Fetching same contract from Polygon...")
    poly_ticker = f"O:{target_contract}" # Polygon format
    parsed = parse_occ_symbol(target_contract)
    
    poly_url = f"https://api.polygon.io/v3/snapshot/options/{parsed['underlying']}/{poly_ticker}"
    poly_params = {"apiKey": POLYGON_API_KEY}
    
    poly_data = None
    try:
        resp = requests.get(poly_url, params=poly_params, timeout=10)
        if resp.status_code != 200:
            print(f"❌ Polygon Error: {resp.text}")
            # Fallback to general snapshot search
            print("   Trying general snapshot search...")
            poly_url_gen = f"https://api.polygon.io/v3/snapshot/options/SPY"
            resp = requests.get(poly_url_gen, params=poly_params, timeout=10)
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                for r in results:
                    if r.get("details", {}).get("ticker") == poly_ticker:
                        poly_data = r
                        break
        else:
            poly_data = resp.json().get("results", {})
            
        if not poly_data:
            print("❌ Could not find contract in Polygon.")
            return
            
        print("✅ Polygon Data Fetched")
        
    except Exception as e:
        print(f"❌ Polygon Exception: {e}")
        return

    # 3. Compare
    print("\n--- 📊 DATA COMPARISON ---")
    print(f"Contract: {target_contract}")
    
    # Extract Alpaca Values
    a_vol = alpaca_data.get("dailyBar", {}).get("v", 0)
    a_price = alpaca_data.get("latestTrade", {}).get("p", 0)
    
    # Extract Polygon Values
    p_vol = poly_data.get("day", {}).get("volume", 0)
    p_price = poly_data.get("day", {}).get("close", 0) 
    p_last_trade_price = poly_data.get("last_trade", {}).get("price", 0)
    
    # Use last trade price if available and close is 0 or different
    # Polygon 'day' close is often the last trade price.
    
    print(f"{'METRIC':<15} | {'ALPACA':<15} | {'POLYGON':<15} | {'MATCH?'}")
    print("-" * 60)
    
    # Volume
    match_vol = "✅" if a_vol == p_vol else "⚠️"
    print(f"{'Volume':<15} | {a_vol:<15} | {p_vol:<15} | {match_vol}")
    
    # Price
    # Allow small difference
    price_to_compare = p_last_trade_price if p_last_trade_price > 0 else p_price
    match_price = "✅" if abs(a_price - price_to_compare) < 0.05 else "⚠️"
    print(f"{'Price':<15} | {a_price:<15} | {price_to_compare:<15} | {match_price}")
    
    print("-" * 60)
    if match_vol == "✅" and match_price == "✅":
        print("\n✅ CONCLUSION: Data matches perfectly/closely.")
    else:
        print("\n⚠️ CONCLUSION: Data discrepancies found.")
        print("   (Note: Slight differences are normal due to different data providers/aggregation methods)")

if __name__ == "__main__":
    compare_real_data()
