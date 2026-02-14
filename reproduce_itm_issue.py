import os
import requests
from dotenv import load_dotenv

load_dotenv()
MASSIVE_API_KEY = os.getenv("MASSIVE_API_KEY")

def test_strike_filtering(symbol="NVDA"):
    print(f"Testing strike filtering for {symbol}...")
    
    # 1. Get Price
    price_url = f"https://api.massive.com/v2/last/trade/{symbol}"
    try:
        price_resp = requests.get(price_url, params={"apiKey": MASSIVE_API_KEY}, timeout=5)
        data = price_resp.json()
        current_price = float(data.get("results", {}).get("price", 0) or data.get("results", {}).get("p", 0) or 0)
    except Exception as e:
        print(f"Price fetch failed: {e}")
        current_price = 0
        
    if current_price == 0:
        print("Could not get price from API, using hardcoded price for testing logic.")
        current_price = 118.00 # Approximate NVDA price
        
    print(f"Current Price: ${current_price:.2f}")

    if not current_price:
        print("Could not get price, aborting.")
        return

    # 2. Simulate "ALL" moneyness filter logic from run.py
    # DEFAULT: +/- 35%
    strike_min = int(current_price * 0.65)
    strike_max = int(current_price * 1.35)
    
    print(f"Default Filter Range: ${strike_min} - ${strike_max}")
    
    chain_url = f"https://api.massive.com/v3/snapshot/options/{symbol}"
    params = {
        "apiKey": MASSIVE_API_KEY, 
        "limit": 250,
        "strike_price.gte": strike_min,
        "strike_price.lte": strike_max
    }
    
    # Fetch Calls
    params["contract_type"] = "call"
    print(f"Fetching Calls with params: {params}")
    resp = requests.get(chain_url, params=params)
    calls = resp.json().get("results", [])
    print(f"Found {len(calls)} calls")

    if calls:
        print("Sample Call Tickers:")
        # Print raw structure of first item for debugging
        print(f"First item keys: {calls[0].keys()}")
        if "details" in calls[0]:
            print(f"Details keys: {calls[0]['details'].keys()}")
            
        for c in calls[:5]:
            t = c.get("details", {}).get("ticker") or c.get("ticker") or "N/A"
            s = parse_strike(t)
            print(f"  {t} -> Strike: {s}")
            
    # Check Call Moneyness
    itm_calls = []
    otm_calls = []
    for c in calls:
        t = c.get("details", {}).get("ticker") or c.get("ticker") or "N/A"
        s = parse_strike(t)
        if s == 0: continue
        
        if s < current_price: itm_calls.append(s)
        else: otm_calls.append(s)
        
    print(f"Calls: {len(itm_calls)} ITM (<{current_price}), {len(otm_calls)} OTM (>{current_price})")
    
    if itm_calls:
        print(f"Min ITM Call Strike: {min(itm_calls)}")
        print(f"Max ITM Call Strike: {max(itm_calls)}")
    if otm_calls:
        print(f"Min OTM Call Strike: {min(otm_calls)}")
        print(f"Max OTM Call Strike: {max(otm_calls)}")

    # Fetch Puts
    params["contract_type"] = "put"
    print(f"Fetching Puts with params: {params}")
    resp = requests.get(chain_url, params=params)
    puts = resp.json().get("results", [])
    print(f"Found {len(puts)} puts")
    
    # Check Put Moneyness
    itm_puts = [c for c in puts if parse_strike(c.get("ticker")) > current_price]
    otm_puts = [c for c in puts if parse_strike(c.get("ticker")) < current_price]
    print(f"Puts: {len(itm_puts)} ITM (>{current_price}), {len(otm_puts)} OTM (<{current_price})")

def parse_strike(ticker):
    try:
        # O:NVDA250117C00150000
        clean = ticker.replace("O:", "")
        i = 0
        while i < len(clean) and clean[i].isalpha(): i += 1
        rest = clean[i:]
        strike_str = rest[7:]
        return float(strike_str) / 1000
    except:
        return 0

if __name__ == "__main__":
    test_strike_filtering()
