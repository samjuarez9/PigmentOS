#!/usr/bin/env python3
"""Analyze WDC options with new Tier 3 filters"""

import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

# Tier 3 Thresholds
MIN_WHALE_PREMIUM = 100_000   # $100k
MIN_VOLUME = 100              # 100 contracts

def format_money(val):
    if val >= 1_000_000: return f"${val/1_000_000:.1f}M"
    if val >= 1_000: return f"${val/1_000:.0f}k"
    return f"${val:.0f}"

def analyze_wdc_options():
    print("\n" + "="*60)
    print("POLYGON.IO - WDC Options Analysis (Tier 3)")
    print("="*60)
    
    if not POLYGON_API_KEY:
        print("❌ POLYGON_API_KEY not set")
        return
    
    today = datetime.now()
    max_expiry = today + timedelta(days=45) 
    
    url = f"https://api.polygon.io/v3/snapshot/options/WDC"
    params = {
        "apiKey": POLYGON_API_KEY,
        "limit": 250,
        "expiration_date.gte": today.strftime("%Y-%m-%d"),
        "expiration_date.lte": max_expiry.strftime("%Y-%m-%d"),
    }
    
    print(f"Fetching WDC options from {today.strftime('%Y-%m-%d')} to {max_expiry.strftime('%Y-%m-%d')}...")
    
    try:
        resp = requests.get(url, params=params, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            print(f"Total contracts returned: {len(results)}")
            
            candidates = []
            
            for contract in results:
                details = contract.get("details", {})
                day_data = contract.get("day", {})
                
                volume = int(day_data.get("volume", 0) or 0)
                last_price = float(day_data.get("close", 0) or day_data.get("vwap", 0) or 0)
                oi = int(contract.get("open_interest", 0) or 0)
                
                if volume == 0:
                    continue
                
                notional = volume * last_price * 100
                
                # 1. Pure Whale Check
                is_pure_whale = (notional >= MIN_WHALE_PREMIUM) and (volume >= MIN_VOLUME)
                
                # 2. Unusual Activity Check
                is_unusual = False
                if oi > 0:
                    is_unusual = (volume > oi * 1.2) and (notional >= 20_000)
                elif oi == 0 and volume >= 100:
                    is_unusual = True
                
                if is_pure_whale or is_unusual:
                    candidates.append({
                        "strike": details.get("strike_price"),
                        "type": details.get("contract_type"),
                        "expiry": details.get("expiration_date"),
                        "volume": volume,
                        "oi": oi,
                        "price": last_price,
                        "notional": notional,
                        "premium_fmt": format_money(notional),
                        "reason": "WHALE" if is_pure_whale else "UNUSUAL"
                    })
            
            candidates.sort(key=lambda x: x['notional'], reverse=True)
            
            print(f"\nFound {len(candidates)} qualifying WDC contracts:")
            for c in candidates:
                print(f"✅ {c['reason']} | {c['strike']} {c['type']} | Vol: {c['volume']} (OI: {c['oi']}) | Prem: {c['premium_fmt']} | Exp: {c['expiry']}")
                
            if not candidates:
                print("❌ No WDC contracts met the Tier 3 criteria.")

        else:
            print(f"❌ Error: {resp.text[:300]}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    analyze_wdc_options()
