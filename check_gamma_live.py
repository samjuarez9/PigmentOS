import requests
import json
import time

try:
    print("🔍 Querying Local Gamma Wall API for SPY...")
    resp = requests.get("http://127.0.0.1:8001/api/gamma?symbol=SPY", timeout=5)
    
    if resp.status_code == 200:
        data = resp.json()
        
        print(f"✅ Status: {resp.status_code}")
        print(f"📊 Symbol: {data.get('symbol')}")
        print(f"🕒 Time Period: {data.get('time_period')}")
        print(f"🏷️ Source: {data.get('source')}")
        print(f"💰 Current Price: {data.get('current_price')}")
        
        strikes = data.get('strikes', [])
        print(f"📉 Total Strikes: {len(strikes)}")
        
        if strikes:
            total_vol = sum(s['call_vol'] + s['put_vol'] for s in strikes)
            print(f"🔊 Total Volume (Today): {total_vol}")
            
            print("\nTop 5 Strikes by Volume:")
            # Sort by total volume
            sorted_strikes = sorted(strikes, key=lambda x: x['call_vol'] + x['put_vol'], reverse=True)
            for s in sorted_strikes[:5]:
                print(f"  - ${s['strike']}: Call Vol {s['call_vol']} | Put Vol {s['put_vol']}")
        else:
            print("⚠️ No strikes returned (Empty).")
            
    else:
        print(f"❌ Error: Status {resp.status_code}")
        print(resp.text)

except Exception as e:
    print(f"❌ Connection Failed: {e}")
