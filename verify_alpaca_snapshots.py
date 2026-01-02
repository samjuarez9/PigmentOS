import requests
import json
import os

# Credentials provided by user
API_KEY = "PKD66OSCNTGDQ2ORIX4RGSKGI5"
SECRET_KEY = "9eSKSK2CchHQbFFwMYr1tnwZgu8MNZEMNfdXqVYwyF5M"
DATA_URL = "https://data.alpaca.markets/v1beta1/options"

def test_alpaca_snapshots(symbols):
    print(f"\nTesting Alpaca Snapshots for {len(symbols)} symbols...")
    
    headers = {
        "APCA-API-KEY-ID": API_KEY,
        "APCA-API-SECRET-KEY": SECRET_KEY,
        "Accept": "application/json"
    }
    
    # Endpoint: /v1beta1/options/snapshots?symbols=SYM1,SYM2...
    snapshots_url = f"{DATA_URL}/snapshots"
    params = {"symbols": ",".join(symbols)}
    
    print(f"Requesting Snapshots...")
    try:
        resp = requests.get(snapshots_url, headers=headers, params=params, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            snapshots = data.get("snapshots", {})
            
            if snapshots:
                print(f"✅ Success! Received {len(snapshots)} snapshots.")
                sample_key = list(snapshots.keys())[0]
                sample = snapshots[sample_key]
                print(f"   Sample ({sample_key}):")
                print(json.dumps(sample, indent=2))
                
                # Check for Quote (Bid/Ask) AND Trade in snapshot
                quote = sample.get("latestQuote") or sample.get("quote")
                trade = sample.get("latestTrade") or sample.get("trade")
                
                has_quote = quote and ('bp' in quote or 'b' in quote)
                has_trade = trade and ('p' in trade)
                
                if has_quote and has_trade:
                    print("   ✅ Snapshot contains BOTH Quote and Trade data!")
                    print("   🚀 WE CAN USE THIS FOR REAL-TIME WHALES!")
                else:
                    print(f"   ⚠️  Snapshot missing data: Quote={has_quote}, Trade={has_trade}")
                return True
            else:
                print("⚠️  Response valid but returned NO snapshots.")
                return False
        elif resp.status_code == 403:
            print("❌ Access Denied (403).")
            return False
        else:
            print(f"❌ Error {resp.status_code}: {resp.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

# Test with our known active symbol
test_symbols = ["SPY260102C00500000"]
test_alpaca_snapshots(test_symbols)
