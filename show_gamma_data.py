import requests
import pandas as pd
import json

try:
    # Fetch data
    resp = requests.get("http://localhost:8001/api/gamma?symbol=SPY")
    data = resp.json()
    
    print(f"Symbol: {data['symbol']}")
    print(f"Current Price: ${data['current_price']:.2f}")
    print(f"Expiration: {data['expiration']}")
    print("-" * 60)
    print(f"{'Strike':<10} | {'Call Vol':<10} | {'Put Vol':<10} | {'Call OI':<10} | {'Put OI':<10}")
    print("-" * 60)
    
    # Filter for strikes near price (+/- 10 strikes) to keep it readable
    price = data['current_price']
    strikes = data['strikes']
    
    # Find index of closest strike
    closest_idx = 0
    min_diff = float('inf')
    for i, s in enumerate(strikes):
        diff = abs(s['strike'] - price)
        if diff < min_diff:
            min_diff = diff
            closest_idx = i
            
    # Show window around price
    start = max(0, closest_idx - 10)
    end = min(len(strikes), closest_idx + 10)
    
    for s in strikes[start:end]:
        mark = "*" if abs(s['strike'] - price) < 1.0 else " "
        print(f"{s['strike']:<9.1f}{mark}| {s['call_vol']:<10} | {s['put_vol']:<10} | {s['call_oi']:<10} | {s['put_oi']:<10}")
        
    print("-" * 60)
    print(f"Total Strikes Fetched: {len(strikes)}")

except Exception as e:
    print(f"Error: {e}")
