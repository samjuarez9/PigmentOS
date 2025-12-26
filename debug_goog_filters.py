#!/usr/bin/env python3
"""
Debug script to analyze GOOG/GOOGL trades that are being filtered out.
Run this from the PigmentOS directory where .env or environment vars are set.
"""

import os
import requests
from datetime import datetime
import pytz
from dotenv import load_dotenv

# Load environment
load_dotenv()

POLYGON_API_KEY = os.environ.get("POLYGON_API_KEY")
if not POLYGON_API_KEY:
    print("❌ POLYGON_API_KEY not found in environment")
    exit(1)

tz_eastern = pytz.timezone('US/Eastern')
now_et = datetime.now(tz_eastern)

# Current filter thresholds (from run.py)
MIN_VOL_OI_RATIO = 1.05
MIN_PREMIUM = 500_000  # $500k for non-index tickers
MIN_VOLUME = 500
MAX_DTE = 14

def format_money(val):
    if val >= 1_000_000: return f"${val/1_000_000:.1f}M"
    if val >= 1_000: return f"${val/1_000:.0f}k"
    return f"${val:.0f}"

for symbol in ['GOOG', 'GOOGL']:
    print(f"\n{'='*70}")
    print(f"ANALYZING {symbol} OPTIONS")
    print(f"{'='*70}")
    
    # Get current price
    price_url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/prev"
    price_resp = requests.get(price_url, params={"apiKey": POLYGON_API_KEY}, timeout=5)
    current_price = 0
    if price_resp.status_code == 200:
        price_data = price_resp.json()
        if price_data.get("results"):
            current_price = price_data["results"][0].get("c", 0)
    
    print(f"Current Price: ${current_price:.2f}")
    
    # Fetch options data
    strike_low = int(current_price * 0.90)
    strike_high = int(current_price * 1.10)
    
    url = f"https://api.polygon.io/v3/snapshot/options/{symbol}"
    params = {
        "apiKey": POLYGON_API_KEY,
        "limit": 250,
        "strike_price.gte": strike_low,
        "strike_price.lte": strike_high
    }
    
    resp = requests.get(url, params=params, timeout=15)
    if resp.status_code != 200:
        print(f"API Error: {resp.status_code}")
        continue
    
    data = resp.json()
    contracts = data.get("results", [])
    print(f"Total contracts fetched: {len(contracts)}")
    print(f"Strike range: ${strike_low} - ${strike_high}")
    
    # Analyze each contract
    passed = []
    filtered_out = []
    
    for contract in contracts:
        details = contract.get("details", {})
        day_data = contract.get("day", {})
        
        volume = int(day_data.get("volume", 0) or 0)
        open_interest = int(contract.get("open_interest", 0) or 0)
        last_price = float(day_data.get("close", 0) or 0)
        strike = float(details.get("strike_price", 0))
        contract_type = details.get("contract_type", "")
        expiry = details.get("expiration_date", "")
        
        # Skip zero activity
        if volume == 0 and last_price == 0:
            continue
        
        notional = volume * last_price * 100 if volume > 0 and last_price > 0 else 0
        vol_oi_ratio = volume / open_interest if open_interest > 0 else 999
        
        # Calculate DTE
        try:
            exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
            dte = (exp_date - now_et.date()).days
        except:
            dte = 999
        
        # Check filters
        reasons = []
        if vol_oi_ratio <= MIN_VOL_OI_RATIO:
            reasons.append(f"vol/oi={vol_oi_ratio:.2f}≤{MIN_VOL_OI_RATIO}")
        if notional < MIN_PREMIUM:
            reasons.append(f"prem={format_money(notional)}<$500k")
        if volume < MIN_VOLUME:
            reasons.append(f"vol={volume}<500")
        if dte < 0 or dte > MAX_DTE:
            reasons.append(f"dte={dte}")
        
        trade_info = {
            "strike": strike,
            "type": contract_type[:1],  # C or P
            "expiry": expiry,
            "dte": dte,
            "volume": volume,
            "oi": open_interest,
            "vol_oi": vol_oi_ratio,
            "premium": notional,
            "reasons": reasons
        }
        
        # Only consider trades with some activity
        if volume > 0:
            if len(reasons) == 0:
                passed.append(trade_info)
            else:
                filtered_out.append(trade_info)
    
    print(f"\n✅ PASSED ALL FILTERS: {len(passed)}")
    for t in sorted(passed, key=lambda x: -x['premium'])[:5]:
        print(f"   ${t['strike']:.0f}{t['type']} exp:{t['expiry']} dte:{t['dte']} | vol:{t['volume']:,} oi:{t['oi']:,} v/oi:{t['vol_oi']:.1f} | {format_money(t['premium'])}")
    
    print(f"\n❌ FILTERED OUT - TOP 15 BY PREMIUM:")
    near_miss = sorted(filtered_out, key=lambda x: -x['premium'])[:15]
    for t in near_miss:
        print(f"   ${t['strike']:.0f}{t['type']} exp:{t['expiry']} dte:{t['dte']} | vol:{t['volume']:,} oi:{t['oi']:,} v/oi:{t['vol_oi']:.1f} | {format_money(t['premium'])}")
        print(f"      └─ {', '.join(t['reasons'])}")
    
    # Summary stats
    premiums = [t['premium'] for t in filtered_out if t['premium'] > 0]
    if premiums:
        print(f"\n📊 FILTERED OUT STATS:")
        print(f"   Max premium filtered: {format_money(max(premiums))}")
        print(f"   Trades with premium $100k-$500k: {len([p for p in premiums if 100_000 <= p < 500_000])}")
        print(f"   Trades with premium $50k-$100k: {len([p for p in premiums if 50_000 <= p < 100_000])}")
