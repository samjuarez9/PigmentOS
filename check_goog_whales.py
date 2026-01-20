#!/usr/bin/env python3
"""
Diagnostic: Check why GOOG isn't appearing in whale feed
"""
import os
import sys
sys.path.insert(0, '/Users/newuser/PigmentOS')

import requests
from datetime import datetime
import pytz

POLYGON_API_KEY = os.environ.get("POLYGON_API_KEY")

def check_goog_options():
    """Fetch GOOG options from Polygon and analyze why trades might not qualify."""
    
    if not POLYGON_API_KEY:
        print("❌ POLYGON_API_KEY not set")
        return
    
    tz_eastern = pytz.timezone('US/Eastern')
    now_et = datetime.now(tz_eastern)
    print(f"🕐 Current time: {now_et.strftime('%Y-%m-%d %H:%M:%S ET')}")
    print(f"📅 Day of week: {now_et.strftime('%A')}")
    print()
    
    # Fetch GOOG options chain snapshot
    url = f"https://api.polygon.io/v3/snapshot/options/GOOG"
    params = {
        "apiKey": POLYGON_API_KEY,
        "limit": 250
    }
    
    print(f"🔍 Fetching GOOG options from Polygon...")
    resp = requests.get(url, params=params, timeout=15)
    
    if resp.status_code != 200:
        print(f"❌ API Error: {resp.status_code} - {resp.text}")
        return
    
    data = resp.json()
    results = data.get("results", [])
    print(f"📊 Total contracts returned: {len(results)}")
    print()
    
    # Thresholds
    MIN_PREMIUM = 500_000  # $500k for "others" category
    MIN_VOLUME = 500
    VOL_OI_MULTIPLIER = 1.2
    
    qualifying = []
    almost_qualifying = []
    
    for contract in results:
        details = contract.get("details", {})
        day_data = contract.get("day", {})
        
        volume = int(day_data.get("volume", 0) or 0)
        last_price = float(day_data.get("close", 0) or day_data.get("vwap", 0) or 0)
        open_interest = int(contract.get("open_interest", 0) or 0)
        
        if volume == 0 or last_price == 0:
            continue
        
        notional = volume * last_price * 100
        vol_oi_ratio = volume / open_interest if open_interest > 0 else 999
        
        strike = details.get("strike_price", 0)
        contract_type = details.get("contract_type", "")
        expiry = details.get("expiration_date", "")
        
        # Check each filter
        passes_premium = notional >= MIN_PREMIUM
        passes_volume = volume >= MIN_VOLUME
        passes_vol_oi = volume > (open_interest * VOL_OI_MULTIPLIER)
        
        trade_info = {
            "symbol": details.get("ticker", ""),
            "strike": strike,
            "type": contract_type,
            "expiry": expiry,
            "volume": volume,
            "open_interest": open_interest,
            "vol_oi_ratio": vol_oi_ratio,
            "last_price": last_price,
            "premium": notional,
            "passes_premium": passes_premium,
            "passes_volume": passes_volume,
            "passes_vol_oi": passes_vol_oi
        }
        
        if passes_premium and passes_volume and passes_vol_oi:
            qualifying.append(trade_info)
        elif notional >= 100_000:  # Show near-misses above $100k
            almost_qualifying.append(trade_info)
    
    # Report qualifying trades
    print("=" * 60)
    print(f"✅ QUALIFYING WHALE TRADES: {len(qualifying)}")
    print("=" * 60)
    
    if qualifying:
        for t in sorted(qualifying, key=lambda x: -x['premium'])[:10]:
            print(f"  ${t['premium']/1_000_000:.2f}M | {t['type'][:4]} ${t['strike']} exp {t['expiry']}")
            print(f"    Vol: {t['volume']:,} | OI: {t['open_interest']:,} | Vol/OI: {t['vol_oi_ratio']:.2f}x")
    else:
        print("  None - No GOOG options passed all filters today")
    
    print()
    print("=" * 60)
    print(f"⚠️ NEAR-MISS TRADES (>$100k premium): {len(almost_qualifying)}")
    print("=" * 60)
    
    # Show top 10 near-misses sorted by premium
    for t in sorted(almost_qualifying, key=lambda x: -x['premium'])[:10]:
        status = []
        if not t['passes_premium']:
            status.append(f"❌ Premium ${t['premium']/1000:.0f}k < $500k")
        if not t['passes_volume']:
            status.append(f"❌ Volume {t['volume']} < 500")
        if not t['passes_vol_oi']:
            status.append(f"❌ Vol/OI {t['vol_oi_ratio']:.2f}x < 1.2x")
        
        print(f"\n  {t['type'][:4]} ${t['strike']} exp {t['expiry']}")
        print(f"    Premium: ${t['premium']/1000:.0f}k | Vol: {t['volume']:,} | OI: {t['open_interest']:,}")
        for s in status:
            print(f"    {s}")

if __name__ == "__main__":
    check_goog_options()
