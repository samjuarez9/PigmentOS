#!/usr/bin/env python3
"""Check NVDA options against Unusual Whales filters (0-30 DTE)"""

import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

# ==== WHALE THRESHOLDS (from run.py) ====
# For NVDA (not SPY/QQQ/TSLA):
MIN_WHALE_PREMIUM = 500_000   # $500k notional value
MIN_VOLUME = 500              # 500 contracts
MEGA_WHALE_THRESHOLD = 1_000_000  # $1M for "MEGA"

def format_money(val):
    if val >= 1_000_000: return f"${val/1_000_000:.1f}M"
    if val >= 1_000: return f"${val/1_000:.0f}k"
    return f"${val:.0f}"

def check_polygon_nvda_whales():
    """Check NVDA options from Polygon.io with whale filters applied"""
    print("\n" + "="*60)
    print("POLYGON.IO - NVDA Whale Candidates (0-30 DTE)")
    print(f"Filters: Premium >= ${MIN_WHALE_PREMIUM:,}, Volume >= {MIN_VOLUME}")
    print("="*60)
    
    if not POLYGON_API_KEY:
        print("❌ POLYGON_API_KEY not set")
        return
    
    today = datetime.now()
    max_expiry = today + timedelta(days=30)
    
    url = f"https://api.polygon.io/v3/snapshot/options/NVDA"
    params = {
        "apiKey": POLYGON_API_KEY,
        "limit": 250,
        "expiration_date.gte": today.strftime("%Y-%m-%d"),
        "expiration_date.lte": max_expiry.strftime("%Y-%m-%d"),
    }
    
    try:
        resp = requests.get(url, params=params, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            print(f"Total contracts returned: {len(results)}")
            
            whales = []
            near_miss = []
            
            for contract in results:
                details = contract.get("details", {})
                day_data = contract.get("day", {})
                
                volume = int(day_data.get("volume", 0) or 0)
                last_price = float(day_data.get("close", 0) or day_data.get("vwap", 0) or 0)
                
                if volume == 0 or last_price == 0:
                    continue
                
                # Calculate notional (premium)
                notional = volume * last_price * 100
                
                contract_info = {
                    "ticker": details.get("ticker"),
                    "strike": details.get("strike_price"),
                    "type": details.get("contract_type"),
                    "expiry": details.get("expiration_date"),
                    "volume": volume,
                    "last_price": last_price,
                    "notional": notional,
                    "premium_fmt": format_money(notional),
                }
                
                # Check whale filters
                if notional >= MIN_WHALE_PREMIUM and volume >= MIN_VOLUME:
                    whales.append(contract_info)
                elif notional >= 100_000 or volume >= 200:
                    near_miss.append(contract_info)
            
            print(f"\n🐳 WHALE TRADES (pass all filters): {len(whales)}")
            if whales:
                whales.sort(key=lambda x: x['notional'], reverse=True)
                for w in whales[:10]:
                    print(f"  ✅ {w['ticker']}")
                    print(f"     Strike: ${w['strike']}, {w['type']}, Exp: {w['expiry']}")
                    print(f"     Volume: {w['volume']:,}, Price: ${w['last_price']:.2f}")
                    print(f"     Premium: {w['premium_fmt']}")
            else:
                print("  No NVDA options meet whale thresholds currently")
            
            print(f"\n📊 NEAR MISSES (>$100k or >200 vol): {len(near_miss)}")
            if near_miss:
                near_miss.sort(key=lambda x: x['notional'], reverse=True)
                for n in near_miss[:5]:
                    print(f"  ⚠️ {n['ticker']}")
                    print(f"     Volume: {n['volume']:,}, Premium: {n['premium_fmt']}")
                    missing = []
                    if n['notional'] < MIN_WHALE_PREMIUM:
                        missing.append(f"need ${(MIN_WHALE_PREMIUM - n['notional'])/1000:.0f}k more premium")
                    if n['volume'] < MIN_VOLUME:
                        missing.append(f"need {MIN_VOLUME - n['volume']} more volume")
                    print(f"     Missing: {', '.join(missing)}")
        else:
            print(f"❌ Error: {resp.text[:300]}")
    except Exception as e:
        print(f"❌ Exception: {e}")


def check_alpaca_nvda_whales():
    """Check NVDA options from Alpaca with whale filters applied"""
    print("\n" + "="*60)
    print("ALPACA - NVDA Whale Candidates (0-30 DTE)")
    print(f"Filters: Premium >= ${MIN_WHALE_PREMIUM:,}, Volume >= {MIN_VOLUME}")
    print("="*60)
    
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        print("❌ ALPACA credentials not set")
        return
    
    today = datetime.now()
    max_expiry = today + timedelta(days=30)
    
    url = "https://data.alpaca.markets/v1beta1/options/snapshots/NVDA"
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    }
    params = {
        "limit": 250,
        "expiration_date_gte": today.strftime("%Y-%m-%d"),
        "expiration_date_lte": max_expiry.strftime("%Y-%m-%d"),
    }
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            snapshots = data.get("snapshots", {})
            print(f"Total contracts returned: {len(snapshots)}")
            
            whales = []
            near_miss = []
            
            for symbol, snap in snapshots.items():
                trade = snap.get("latestTrade", {})
                quote = snap.get("latestQuote", {})
                
                # Alpaca gives volume in a different structure
                # We need to check the trade data
                last_price = float(trade.get("p", 0) or 0)
                volume = int(trade.get("s", 0) or 0)  # This is trade size, not daily volume
                
                # Alpaca snapshot doesn't give daily volume directly in this endpoint
                # We'll use the trade size as an approximation for now
                if last_price == 0:
                    continue
                
                # For proper volume, we'd need to check day.volume if available
                day = snap.get("day", {})
                daily_volume = int(day.get("v", 0) or day.get("volume", 0) or 0)
                if daily_volume > 0:
                    volume = daily_volume
                
                notional = volume * last_price * 100
                
                contract_info = {
                    "ticker": symbol,
                    "volume": volume,
                    "last_price": last_price,
                    "notional": notional,
                    "premium_fmt": format_money(notional),
                    "delta": snap.get("greeks", {}).get("delta", "N/A"),
                }
                
                if notional >= MIN_WHALE_PREMIUM and volume >= MIN_VOLUME:
                    whales.append(contract_info)
                elif notional >= 100_000 or volume >= 200:
                    near_miss.append(contract_info)
            
            print(f"\n🐳 WHALE TRADES (pass all filters): {len(whales)}")
            if whales:
                whales.sort(key=lambda x: x['notional'], reverse=True)
                for w in whales[:10]:
                    print(f"  ✅ {w['ticker']}")
                    print(f"     Volume: {w['volume']:,}, Price: ${w['last_price']:.2f}")
                    print(f"     Premium: {w['premium_fmt']}, Delta: {w['delta']}")
            else:
                print("  No NVDA options meet whale thresholds currently")
            
            print(f"\n📊 NEAR MISSES (>$100k or >200 vol): {len(near_miss)}")
            if near_miss:
                near_miss.sort(key=lambda x: x['notional'], reverse=True)
                for n in near_miss[:5]:
                    print(f"  ⚠️ {n['ticker']}: Vol {n['volume']:,}, {n['premium_fmt']}")
        else:
            print(f"❌ Error: {resp.text[:300]}")
    except Exception as e:
        print(f"❌ Exception: {e}")


if __name__ == "__main__":
    print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n🎯 UNUSUAL WHALES FILTER CRITERIA:")
    print(f"   • Minimum Premium: ${MIN_WHALE_PREMIUM:,} ($500k)")
    print(f"   • Minimum Volume: {MIN_VOLUME} contracts")
    print(f"   • Mega Whale: ${MEGA_WHALE_THRESHOLD:,}+ ($1M+)")
    
    check_polygon_nvda_whales()
    check_alpaca_nvda_whales()
    
    print("\n" + "="*60)
    print("Done!")
