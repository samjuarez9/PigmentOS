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

def diag_aapl():
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
        "Accept": "application/json"
    }
    
    symbol = "AAPL"
    print(f"--- Diagnosing Side Logic for {symbol} ---")
    
    # 1. Get Snapshots
    snapshot_url = f"{ALPACA_DATA_URL}/snapshots/{symbol}"
    resp = requests.get(snapshot_url, headers=headers, params={"limit": 500})
    if resp.status_code != 200:
        print(f"Error fetching snapshots: {resp.status_code}")
        return
    
    snapshots = resp.json().get("snapshots", {})
    option_symbols = list(snapshots.keys())
    
    # Filter for active contracts (0-30 DTE)
    tz_eastern = pytz.timezone('US/Eastern')
    now_et = datetime.now(tz_eastern)
    
    valid_contracts = []
    for sym in option_symbols:
        # Simple parsing for DTE (assuming standard format)
        try:
            # AAPL260116C00250000
            date_part = sym[4:10] # 260116
            expiry = datetime.strptime(date_part, "%y%m%d").date()
            dte = (expiry - now_et.date()).days
            if 0 <= dte <= 30:
                valid_contracts.append(sym)
        except:
            pass
            
    print(f"Found {len(valid_contracts)} active contracts (0-30 DTE).")
    
    # 2. Fetch Trades (Last 30 days)
    start_date = (now_et - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00Z")
    
    # Check a batch
    batch = valid_contracts[:20]
    trades_url = "https://data.alpaca.markets/v1beta1/options/trades"
    params = {
        "symbols": ",".join(batch),
        "start": start_date,
        "limit": 1000
    }
    
    trades_resp = requests.get(trades_url, headers=headers, params=params)
    trades_data = trades_resp.json().get("trades", {})
    
    total_bought = 0
    total_sold = 0
    
    for opt_sym, trades in trades_data.items():
        # Sort ascending
        trades.sort(key=lambda x: x.get("t", ""))
        
        snapshot = snapshots.get(opt_sym, {})
        quote = snapshot.get("latestQuote", {})
        bid = float(quote.get("bp", 0) or 0)
        ask = float(quote.get("ap", 0) or 0)
        
        last_price = None
        last_side = "BUY"
        
        print(f"\nContract: {opt_sym} | Bid: {bid} | Ask: {ask}")
        
        for t in trades:
            price = float(t.get("p", 0))
            size = int(t.get("s", 0))
            premium = price * size * 100
            
            if premium < 100000 or size < 50:
                last_price = price
                continue
                
            timestamp_str = t.get("t", "")
            trade_dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            is_recent = (now_et - trade_dt).total_seconds() < 900
            
            side = "BUY"
            reason = ""
            
            if is_recent and bid > 0 and ask > 0:
                reason = "Live Quote"
                if price <= bid: side = "SELL"
                elif price >= ask: side = "BUY"
                else: side = "BUY"
            else:
                if last_price is not None:
                    reason = "Tick Test"
                    if price > last_price: side = "BUY"
                    elif price < last_price: side = "SELL"
                    else: side = last_side
                else:
                    reason = "First Trade (Fallback)"
                    # THIS IS THE SUSPECT LOGIC
                    if bid > 0 and price <= bid: side = "SELL"
                    else: side = "BUY"
            
            last_price = price
            last_side = side
            
            if side == "BUY": total_bought += 1
            else: total_sold += 1
            
            print(f"  {timestamp_str} | Price: {price} | Side: {side} ({reason})")

    print(f"\nTotal: {total_bought} BOUGHT | {total_sold} SOLD")

if __name__ == "__main__":
    diag_aapl()
