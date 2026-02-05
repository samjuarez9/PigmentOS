#!/usr/bin/env python3
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
MASSIVE_API_KEY = os.getenv("MASSIVE_API_KEY")
SYMBOL = "GOOGL"

def get_polygon_price(symbol):
    """Replicated from run.py"""
    try:
        url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/prev?adjusted=true&apiKey={POLYGON_API_KEY}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("resultsCount", 0) > 0 and data.get("results"):
                return data["results"][0].get("c")
    except Exception as e:
        print(f"Polygon price error: {e}")
    return None

def verify_massive_option_trade():
    """Verify one option trade field"""
    chain_url = f"https://api.massive.com/v3/snapshot/options/{SYMBOL}"
    resp = requests.get(chain_url, params={"apiKey": MASSIVE_API_KEY, "limit": 1})
    if resp.ok:
        res = resp.json().get("results", [])
        if res:
            ticker = res[0]["details"]["ticker"]
            massive_ticker = ticker if ticker.startswith("O:") else f"O:{ticker}"
            trades_url = f"https://api.massive.com/v3/trades/{massive_ticker}"
            trades = requests.get(trades_url, params={"apiKey": MASSIVE_API_KEY, "limit": 1})
            if trades.ok:
                t_list = trades.json().get("results", [])
                if t_list:
                    print("\n--- Massive Option Trade Keys ---")
                    print(list(t_list[0].keys()))
                    return
    print("Could not fetch massive option trade")

def main():
    print(f"--- Testing Fallback Price for {SYMBOL} ---")
    price = get_polygon_price(SYMBOL)
    print(f"Polygon Price: {price}")
    
    if price:
        print("✅ Fallback SUCCESS")
    else:
        print("❌ Fallback FAILED")
        
    verify_massive_option_trade()

if __name__ == "__main__":
    main()
