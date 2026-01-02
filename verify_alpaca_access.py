import requests
import json
import os

# Credentials provided by user
API_KEY = "PKD66OSCNTGDQ2ORIX4RGSKGI5"
SECRET_KEY = "9eSKSK2CchHQbFFwMYr1tnwZgu8MNZEMNfdXqVYwyF5M"
# Note: User provided Paper endpoint, but Data API usually lives at data.alpaca.markets
DATA_URL = "https://data.alpaca.markets/v1beta1/options"

def test_alpaca_options(symbol):
    print(f"\nTesting Alpaca Options Data for {symbol}...")
    
    headers = {
        "APCA-API-KEY-ID": API_KEY,
        "APCA-API-SECRET-KEY": SECRET_KEY,
        "Accept": "application/json"
    }
    
    # 1. Test Latest Quotes (NBBO)
    # Endpoint: /v1beta1/options/quotes/latest?symbols={symbol}
    quotes_url = f"{DATA_URL}/quotes/latest"
    params = {"symbols": symbol}
    
    print(f"1. Requesting Latest Quote...")
    try:
        resp = requests.get(quotes_url, headers=headers, params=params, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            print("✅ Quote Response Received:")
            print(json.dumps(data, indent=2))
            
            quote = data.get("quotes", {}).get(symbol)
            if quote:
                # Check for Bid/Ask
                bid = quote.get("bp") or quote.get("b") # bid price
                ask = quote.get("ap") or quote.get("a") # ask price
                if bid and ask:
                    print(f"   ✅ Success! Bid: {bid}, Ask: {ask}")
                else:
                    print(f"   ⚠️  Response valid but missing Bid/Ask fields: {quote}")
            else:
                print("   ⚠️  No quote found for symbol (Market might be closed or symbol invalid)")
        elif resp.status_code == 403:
            print("❌ Access Denied (403). Plan likely does not include Options Data.")
        elif resp.status_code == 422:
            print("❌ Invalid Symbol or Parameter (422).")
        else:
            print(f"❌ Error {resp.status_code}: {resp.text}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

    # 2. Test Latest Trades
    # Endpoint: /v1beta1/options/trades/latest?symbols={symbol}
    trades_url = f"{DATA_URL}/trades/latest"
    
    print(f"\n2. Requesting Latest Trade...")
    try:
        resp = requests.get(trades_url, headers=headers, params=params, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            print("✅ Trade Response Received:")
            print(json.dumps(data, indent=2))
        elif resp.status_code == 403:
            print("❌ Access Denied (403).")
        else:
            print(f"❌ Error {resp.status_code}: {resp.text}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

# Use a likely valid option symbol (OCC format)
# SPY Jan 2 2026 500 Call -> SPY260102C00500000
# Note: Alpaca expects standard OCC format string
test_symbol = "SPY260102C00500000" 
test_alpaca_options(test_symbol)
