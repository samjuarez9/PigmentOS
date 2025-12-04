import requests
import json
import re
import math

def audit_polymarket_outcomes():
    url = "https://gamma-api.polymarket.com/events?limit=20&active=true&closed=false&order=volume24hr&ascending=false"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    print("Fetching Polymarket Data...")
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        events = resp.json()
    except Exception as e:
        print(f"Error: {e}")
        return

    print(f"\nScanning {len(events)} events for outcome mapping...\n")

    for event in events:
        title = event.get('title', '')
        markets = event.get('markets', [])
        if not markets: continue
        
        m = markets[0] # Main market
        
        # Raw Data
        raw_outcomes = m.get('outcomes')
        raw_prices = m.get('outcomePrices')
        group_title = m.get('groupItemTitle')
        
        # Parse JSON if needed
        outcomes = json.loads(raw_outcomes) if isinstance(raw_outcomes, str) else raw_outcomes
        prices = json.loads(raw_prices) if isinstance(raw_prices, str) else raw_prices
        
        print(f"--- {title} ---")
        print(f"Group Title: {group_title}")
        print(f"Raw Outcomes: {outcomes}")
        print(f"Raw Prices: {prices}")
        
        # Logic from run.py
        outcome_data = []
        if len(outcomes) >= 2 and len(prices) >= 2:
            for i in range(len(outcomes)):
                try:
                    price = float(prices[i])
                    label = str(outcomes[i])
                    outcome_data.append({"label": label, "price": price})
                except: continue
            
            # Sort by Price (Probability)
            outcome_data.sort(key=lambda x: x['price'], reverse=True)
            
            if len(outcome_data) < 2: 
                print("Skipped: < 2 valid outcomes")
                continue
            
            top1 = outcome_data[0]
            top2 = outcome_data[1]
            
            # Label Override Logic
            if group_title and top1['label'].lower() == "yes":
                print(f"-> Override Applied: 'Yes' -> '{group_title}'")
                top1['label'] = group_title
            
            print(f"Mapped 1: {top1['label']} ({int(top1['price']*100)}%)")
            print(f"Mapped 2: {top2['label']} ({int(top2['price']*100)}%)")
            print("\n")

if __name__ == "__main__":
    audit_polymarket_outcomes()
