import requests
import json

def verify():
    url = "http://localhost:8001/api/whales/snapshot?symbol=NVDA"
    try:
        print(f"Fetching from {url}...")
        resp = requests.get(url, timeout=20)
        data = resp.json()
        
        print(f"Fetched {len(data)} trades.")
        
        low_prem_count = 0
        min_prem = float('inf')
        
        for t in data:
            prem_str = t['premium'].replace('$','').replace(',','')
            prem = float(prem_str)
            if prem < min_prem:
                min_prem = prem
            
            if prem < 300_000:
                low_prem_count += 1
                if low_prem_count <= 5:
                    print(f"  Found Low Prem: {t['symbol']} {t['strikePrice']}{t['putCall']} = ${prem:,.0f}")
        
        print(f"\nStats:")
        print(f"  Total Trades: {len(data)}")
        print(f"  Trades < $300k: {low_prem_count}")
        print(f"  Lowest Premium: ${min_prem:,.0f}")
        
        if low_prem_count > 0:
            print("\n✅ SUCCESS: Filter is REMOVED (Found trades < $300k)")
        else:
            print("\n⚠️ WARNING: No trades < $300k found. (Could be coincidence or filter still active)")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify()
