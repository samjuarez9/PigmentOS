import os
import requests
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz

load_dotenv()

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_DATA_URL = "https://data.alpaca.markets/v1beta1/options"

def diag_side(symbol="NVDA"):
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
        "Accept": "application/json"
    }
    
    print(f"--- Diagnosing Side Logic for {symbol} ---")
    
    # 1. Get Snapshots
    snapshot_url = f"{ALPACA_DATA_URL}/snapshots/{symbol}"
    resp = requests.get(snapshot_url, headers=headers, params={"limit": 10})
    if resp.status_code != 200:
        print(f"Error fetching snapshots: {resp.status_code}")
        return
    
    snapshots = resp.json().get("snapshots", {})
    if not snapshots:
        print("No snapshots found.")
        return
    
    # Pick a few contracts
    option_symbols = list(snapshots.keys())[:5]
    print(f"Checking contracts: {option_symbols}")
    
    # 2. Fetch Trades for these contracts (last 3 days)
    tz_eastern = pytz.timezone('US/Eastern')
    now_et = datetime.now(tz_eastern)
    start_date = (now_et - timedelta(days=3)).strftime("%Y-%m-%dT00:00:00Z")
    
    trades_url = "https://data.alpaca.markets/v1beta1/options/trades"
    params = {
        "symbols": ",".join(option_symbols),
        "start": start_date,
        "limit": 50
    }
    
    trades_resp = requests.get(trades_url, headers=headers, params=params)
    if trades_resp.status_code != 200:
        print(f"Error fetching trades: {trades_resp.status_code}")
        return
    
    trades_data = trades_resp.json().get("trades", {})
    
    for opt_sym, trades in trades_data.items():
        print(f"\nContract: {opt_sym}")
        snapshot = snapshots.get(opt_sym, {})
        quote = snapshot.get("latestQuote", {})
        bid = float(quote.get("bp", 0) or 0)
        ask = float(quote.get("ap", 0) or 0)
        print(f"Current Quote -> Bid: {bid} | Ask: {ask}")
        
        # Sort trades ascending for tick test
        trades.sort(key=lambda x: x.get("t", ""))
        
        last_price = None
        last_side = "BOUGHT"
        
        bought_count = 0
        sold_count = 0
        
        for t in trades:
            price = float(t.get("p", 0))
            timestamp_str = t.get("t", "")
            trade_dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            is_recent = (now_et - trade_dt).total_seconds() < 900
            
            side = "BOUGHT"
            if is_recent and bid > 0 and ask > 0:
                if price <= bid:
                    side = "SOLD"
                elif price >= ask:
                    side = "BOUGHT"
                else:
                    side = "BOUGHT (MID)"
            else:
                if last_price is not None:
                    if price > last_price:
                        side = "BOUGHT"
                    elif price < last_price:
                        side = "SOLD"
                    else:
                        side = last_side
                else:
                    if bid > 0 and price <= bid:
                        side = "SOLD"
                    else:
                        side = "BOUGHT"
            
            last_price = price
            last_side = side
            
            if side == "SOLD":
                sold_count += 1
            else:
                bought_count += 1
            
            # Print first 5 trades for detail
            if (bought_count + sold_count) <= 5:
                print(f"  Trade: Price {price} | Side: {side} | Time: {timestamp_str}")
        
        print(f"Summary: {bought_count} BOUGHT | {sold_count} SOLD")

if __name__ == "__main__":
    diag_side()
