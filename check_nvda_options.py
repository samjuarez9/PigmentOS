#!/usr/bin/env python3
"""Check NVDA options with 0-30 DTE from Polygon and Alpaca APIs"""

import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

def check_polygon_nvda():
    """Check NVDA options from Polygon.io"""
    print("\n" + "="*60)
    print("POLYGON.IO - NVDA Options (0-30 DTE)")
    print("="*60)
    
    if not POLYGON_API_KEY:
        print("❌ POLYGON_API_KEY not set")
        return
    
    today = datetime.now()
    max_expiry = today + timedelta(days=30)
    
    # Polygon options chain endpoint
    url = f"https://api.polygon.io/v3/snapshot/options/NVDA"
    params = {
        "apiKey": POLYGON_API_KEY,
        "limit": 250,
        "expiration_date.gte": today.strftime("%Y-%m-%d"),
        "expiration_date.lte": max_expiry.strftime("%Y-%m-%d"),
    }
    
    try:
        resp = requests.get(url, params=params, timeout=15)
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            print(f"✅ Found {len(results)} option contracts")
            
            if results:
                # Group by expiration
                by_expiry = {}
                for opt in results:
                    details = opt.get("details", {})
                    expiry = details.get("expiration_date", "unknown")
                    if expiry not in by_expiry:
                        by_expiry[expiry] = {"calls": 0, "puts": 0}
                    
                    if details.get("contract_type") == "call":
                        by_expiry[expiry]["calls"] += 1
                    else:
                        by_expiry[expiry]["puts"] += 1
                
                print("\nContracts by Expiration:")
                for exp in sorted(by_expiry.keys()):
                    counts = by_expiry[exp]
                    print(f"  {exp}: {counts['calls']} calls, {counts['puts']} puts")
                
                # Show sample data
                print("\nSample contract data (first 3):")
                for opt in results[:3]:
                    details = opt.get("details", {})
                    greeks = opt.get("greeks", {})
                    day = opt.get("day", {})
                    print(f"  - {details.get('ticker')}")
                    print(f"    Strike: ${details.get('strike_price')}, Type: {details.get('contract_type')}")
                    print(f"    Expiry: {details.get('expiration_date')}")
                    print(f"    Delta: {greeks.get('delta', 'N/A')}, Volume: {day.get('volume', 'N/A')}")
        else:
            print(f"❌ Error: {resp.text[:500]}")
    except Exception as e:
        print(f"❌ Exception: {e}")


def check_alpaca_nvda():
    """Check NVDA options from Alpaca"""
    print("\n" + "="*60)
    print("ALPACA - NVDA Options (0-30 DTE)")
    print("="*60)
    
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        print("❌ ALPACA_API_KEY or ALPACA_SECRET_KEY not set")
        return
    
    today = datetime.now()
    max_expiry = today + timedelta(days=30)
    
    # Alpaca option chain endpoint
    url = "https://data.alpaca.markets/v1beta1/options/snapshots/NVDA"
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    }
    params = {
        "limit": 100,
        "expiration_date_gte": today.strftime("%Y-%m-%d"),
        "expiration_date_lte": max_expiry.strftime("%Y-%m-%d"),
    }
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            snapshots = data.get("snapshots", {})
            print(f"✅ Found {len(snapshots)} option contracts")
            
            if snapshots:
                # Group by expiration from symbol
                by_expiry = {}
                sample = []
                
                for symbol, snap in list(snapshots.items())[:50]:
                    # Parse expiration from OCC symbol: NVDA250117C00100000
                    # Format: underlying + YYMMDD + C/P + strike*1000
                    try:
                        # Find where the date starts (after ticker)
                        import re
                        match = re.search(r'(\d{6})([CP])', symbol)
                        if match:
                            date_str = match.group(1)
                            opt_type = "call" if match.group(2) == "C" else "put"
                            expiry = f"20{date_str[:2]}-{date_str[2:4]}-{date_str[4:6]}"
                            
                            if expiry not in by_expiry:
                                by_expiry[expiry] = {"calls": 0, "puts": 0}
                            
                            if opt_type == "call":
                                by_expiry[expiry]["calls"] += 1
                            else:
                                by_expiry[expiry]["puts"] += 1
                            
                            if len(sample) < 3:
                                sample.append((symbol, snap, expiry, opt_type))
                    except:
                        pass
                
                print("\nContracts by Expiration (sampled):")
                for exp in sorted(by_expiry.keys()):
                    counts = by_expiry[exp]
                    print(f"  {exp}: {counts['calls']} calls, {counts['puts']} puts")
                
                print("\nSample contract data:")
                for symbol, snap, expiry, opt_type in sample:
                    greeks = snap.get("greeks", {})
                    quote = snap.get("latestQuote", {})
                    trade = snap.get("latestTrade", {})
                    print(f"  - {symbol}")
                    print(f"    Type: {opt_type}, Expiry: {expiry}")
                    print(f"    Delta: {greeks.get('delta', 'N/A')}")
                    print(f"    Bid: {quote.get('bp', 'N/A')}, Ask: {quote.get('ap', 'N/A')}")
                    print(f"    Last: {trade.get('p', 'N/A')}, Size: {trade.get('s', 'N/A')}")
        else:
            print(f"❌ Error: {resp.text[:500]}")
    except Exception as e:
        print(f"❌ Exception: {e}")


if __name__ == "__main__":
    print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Checking NVDA options expiring within next 30 days...")
    
    check_polygon_nvda()
    check_alpaca_nvda()
    
    print("\n" + "="*60)
    print("Done!")
