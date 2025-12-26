import os
import requests
import yfinance as yf
from datetime import datetime, timedelta
import pytz

# Configuration
SYMBOL = "ORCL"
POLYGON_API_KEY = os.environ.get("POLYGON_API_KEY")

def get_current_price(symbol):
    try:
        ticker = yf.Ticker(symbol)
        return ticker.fast_info['last_price']
    except:
        return None

def fetch_gamma_data(symbol):
    if not POLYGON_API_KEY:
        print("Error: POLYGON_API_KEY not found")
        return

    print(f"🔍 Fetching Gamma Data for {symbol}...")
    
    # 1. Get Price
    current_price = get_current_price(symbol)
    if not current_price:
        print("   Failed to get price")
        return
    print(f"   Current Price: ${current_price:.2f}")

    # 2. Determine Expiry (Logic from run.py)
    tz_eastern = pytz.timezone('US/Eastern')
    now_et = datetime.now(tz_eastern)
    today_weekday = now_et.weekday()
    
    # Simple logic for non-daily tickers (ORCL)
    # Use next Friday
    days_until_friday = (4 - today_weekday) % 7
    if days_until_friday == 0 and now_et.hour >= 17:
        days_until_friday = 7
    
    expiry_date = (now_et + timedelta(days=days_until_friday)).strftime("%Y-%m-%d")
    print(f"   Target Expiry: {expiry_date}")

    # 3. Fetch Options Chain
    strike_low = int(current_price * 0.80)
    strike_high = int(current_price * 1.20)
    
    url = f"https://api.polygon.io/v3/snapshot/options/{symbol}"
    params = {
        "apiKey": POLYGON_API_KEY,
        "limit": 250,
        "strike_price.gte": strike_low,
        "strike_price.lte": strike_high,
        "expiration_date": expiry_date,
        "order": "asc",
        "sort": "strike_price"
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code != 200:
            print(f"   API Error: {resp.status_code}")
            return
        data = resp.json()
    except Exception as e:
        print(f"   Fetch failed: {e}")
        return

    results = data.get("results", [])
    print(f"   Received {len(results)} contracts. Processing...")

    # 4. Parse Gamma Data
    gamma_data = {}
    
    for contract in results:
        details = contract.get("details", {})
        strike = details.get("strike_price")
        side = details.get("contract_type", "").lower()
        
        if not strike or not side: continue
        
        if strike not in gamma_data:
            gamma_data[strike] = {"call_vol": 0, "put_vol": 0, "net_gex": 0}
            
        day_data = contract.get("day", {})
        greeks = contract.get("greeks", {})
        
        vol = int(day_data.get("volume", 0) or 0)
        oi = int(contract.get("open_interest", 0) or 0)
        gamma_val = float(greeks.get("gamma", 0) or 0)
        
        # GEX Calculation
        gex = gamma_val * oi * 100 * (current_price ** 2) * 0.01 if gamma_val and oi else 0
        
        if side == "call":
            gamma_data[strike]["call_vol"] += vol
            gamma_data[strike]["net_gex"] += gex
        else:
            gamma_data[strike]["put_vol"] += vol
            gamma_data[strike]["net_gex"] -= gex # Puts are negative gamma

    # 5. Display Results (Top Levels)
    sorted_strikes = sorted(gamma_data.keys())
    
    print("\n📊 GAMMA WALL DATA (Top Volume & GEX)")
    print(f"{'Strike':<10} {'Call Vol':<10} {'Put Vol':<10} {'Net GEX ($M)':<15}")
    print("-" * 50)
    
    for strike in sorted_strikes:
        data = gamma_data[strike]
        total_vol = data["call_vol"] + data["put_vol"]
        if total_vol < 100: continue # Filter noise
        
        gex_m = data["net_gex"] / 1_000_000
        print(f"${strike:<9.1f} {data['call_vol']:<10} {data['put_vol']:<10} {gex_m:<15.2f}")

if __name__ == "__main__":
    fetch_gamma_data(SYMBOL)
