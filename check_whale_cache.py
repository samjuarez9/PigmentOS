#!/usr/bin/env python3
"""
Diagnostic: Check current whale cache contents and ticker distribution
"""
import os
import sys
sys.path.insert(0, '/Users/newuser/PigmentOS')

import requests
from collections import Counter

def check_whale_cache():
    """Fetch current whale cache from the running server and analyze ticker distribution."""
    
    print("🔍 Fetching current whale cache from server...")
    print()
    
    try:
        # Hit the whales API endpoint
        resp = requests.get("http://localhost:5001/api/whales", timeout=10)
        
        if resp.status_code != 200:
            print(f"❌ API Error: {resp.status_code}")
            return
        
        data = resp.json()
        trades = data.get("data", [])
        
        print(f"📊 Total trades in cache: {len(trades)}")
        print()
        
        # Count by ticker
        ticker_counts = Counter()
        ticker_premium = {}
        source_counts = Counter()
        
        for trade in trades:
            base = trade.get("baseSymbol", "UNKNOWN")
            source = trade.get("source", "unknown")
            premium_str = trade.get("premium", "$0")
            notional = trade.get("notional_value", 0)
            
            ticker_counts[base] += 1
            source_counts[source] += 1
            
            if base not in ticker_premium:
                ticker_premium[base] = []
            ticker_premium[base].append(notional)
        
        # Print ticker distribution
        print("=" * 60)
        print("📈 TICKER DISTRIBUTION IN CACHE")
        print("=" * 60)
        
        for ticker, count in ticker_counts.most_common():
            max_prem = max(ticker_premium.get(ticker, [0]))
            avg_prem = sum(ticker_premium.get(ticker, [0])) / count if count > 0 else 0
            print(f"  {ticker:8} | {count:3} trades | Max: ${max_prem/1_000_000:.2f}M | Avg: ${avg_prem/1_000_000:.2f}M")
        
        print()
        print("=" * 60)
        print("📡 SOURCE DISTRIBUTION")
        print("=" * 60)
        for source, count in source_counts.most_common():
            print(f"  {source:10} | {count:3} trades")
        
        # Show if GOOG/GOOGL are present
        print()
        print("=" * 60)
        print("🔍 GOOG/GOOGL SPECIFIC")
        print("=" * 60)
        
        goog_trades = [t for t in trades if t.get("baseSymbol") in ["GOOG", "GOOGL"]]
        if goog_trades:
            print(f"  Found {len(goog_trades)} GOOG/GOOGL trades in cache:")
            for t in sorted(goog_trades, key=lambda x: -x.get("notional_value", 0))[:10]:
                print(f"    {t.get('baseSymbol')} | {t.get('premium')} | {t.get('putCall')} ${t.get('strikePrice')} | {t.get('tradeTime')} | src: {t.get('source')}")
        else:
            print("  ❌ NO GOOG/GOOGL trades found in cache!")
            
        # Check for potential deduplication issues
        print()
        print("=" * 60)
        print("🔬 CHECKING ALPACA vs POLYGON OVERLAP")
        print("=" * 60)
        
        alpaca_trades = [t for t in trades if t.get("source") == "alpaca"]
        polygon_trades = [t for t in trades if t.get("source") == "polygon"]
        
        alpaca_tickers = set(t.get("baseSymbol") for t in alpaca_trades)
        polygon_tickers = set(t.get("baseSymbol") for t in polygon_trades)
        
        print(f"  Alpaca tickers: {sorted(alpaca_tickers)}")
        print(f"  Polygon tickers: {sorted(polygon_tickers)}")
        print(f"  Overlap: {sorted(alpaca_tickers & polygon_tickers)}")
        
        # Check if Alpaca is filtering out GOOG
        if "GOOG" in polygon_tickers and "GOOG" not in alpaca_tickers:
            print("  ⚠️ GOOG in Polygon but NOT in Alpaca - possible Alpaca filter issue")
        if "GOOGL" in polygon_tickers and "GOOGL" not in alpaca_tickers:
            print("  ⚠️ GOOGL in Polygon but NOT in Alpaca - possible Alpaca filter issue")
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server at localhost:5001")
        print("   Is the server running?")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_whale_cache()
