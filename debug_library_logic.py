import os
import requests
import datetime
import pytz
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

# Configuration
ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY")
ALPACA_DATA_URL = "https://data.alpaca.markets/v1beta1/options"
SYMBOL = "SPY"

if not ALPACA_API_KEY:
    print("⚠️ ALPACA_API_KEY not found")
    exit(1)

headers = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    "Accept": "application/json"
}

tz_eastern = pytz.timezone('US/Eastern')
now_et = datetime.datetime.now(tz_eastern)

print(f"DEBUG: Analyzing Library Logic for {SYMBOL}")

# 1. Fetch Snapshots
print("Fetching snapshots...")
snapshot_url = f"{ALPACA_DATA_URL}/snapshots/{SYMBOL}"
resp = requests.get(snapshot_url, headers=headers, params={"limit": 500}, timeout=15)

if resp.status_code != 200:
    print(f"Error fetching snapshots: {resp.status_code}")
    exit(1)

snapshots = resp.json().get("snapshots", {})
print(f"Found {len(snapshots)} total contracts")

# 2. Filter Contracts (0-30 DTE)
def parse_occ(sym):
    try:
        clean = sym.replace("O:", "")
        i = 0
        while i < len(clean) and clean[i].isalpha(): i += 1
        rest = clean[i:]
        date_str = rest[:6]
        put_call = rest[6]
        strike = float(rest[7:]) / 1000
        year = 2000 + int(date_str[:2])
        month = int(date_str[2:4])
        day = int(date_str[4:6])
        expiry = f"{year}-{month:02d}-{day:02d}"
        return {"expiry": expiry, "type": "CALL" if put_call == "C" else "PUT", "strike": strike}
    except: return None

valid_contracts = []
for option_symbol in snapshots.keys():
    parsed = parse_occ(option_symbol)
    if not parsed: continue
    
    try:
        expiry_date = datetime.datetime.strptime(parsed['expiry'], "%Y-%m-%d").date()
        days_to_expiry = (expiry_date - now_et.date()).days
        if 0 <= days_to_expiry <= 30:
            valid_contracts.append(option_symbol)
    except:
        continue

print(f"Found {len(valid_contracts)} valid contracts (0-30 DTE)")

# 3. Fetch Trades (Batch)
all_trades = []
batch_size = 20
start_date = (now_et - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00Z")

# Limit to first 5 batches for debug speed
valid_contracts = valid_contracts[:100] 

print(f"Fetching trades for {len(valid_contracts)} contracts...")

for i in range(0, len(valid_contracts), batch_size):
    batch = valid_contracts[i:i+batch_size]
    symbols_param = ",".join(batch)
    
    trades_url = "https://data.alpaca.markets/v1beta1/options/trades"
    params = {
        "symbols": symbols_param,
        "start": start_date,
        "limit": 1000
    }
    
    try:
        trades_resp = requests.get(trades_url, headers=headers, params=params, timeout=15)
        if trades_resp.status_code == 200:
            trades_data = trades_resp.json().get("trades", {})
            for option_symbol, trades in trades_data.items():
                for trade in trades:
                    all_trades.append({
                        "symbol": option_symbol,
                        "price": float(trade.get("p", 0)),
                        "size": int(trade.get("s", 0)),
                        "timestamp": trade.get("t", ""),
                        "condition": trade.get("c", ""),
                        "exchange": trade.get("x", "")
                    })
    except Exception as e:
        print(f"Error batch {i}: {e}")

print(f"Fetched {len(all_trades)} raw trades")

# 4. Process Trades (Side Logic)
MIN_PREMIUM = 100000
MIN_SIZE = 50

trades_by_contract = {}
for trade in all_trades:
    option_symbol = trade["symbol"]
    if option_symbol not in trades_by_contract:
        trades_by_contract[option_symbol] = []
    trades_by_contract[option_symbol].append(trade)

processed_count = 0
buy_count = 0
sell_count = 0
filtered_count = 0

print("\n--- Processing Logic ---")

for option_symbol, contract_trades in trades_by_contract.items():
    contract_trades.sort(key=lambda x: x.get("t", ""))
    
    last_price = None
    last_side = "BUY"
    
    snapshot = snapshots.get(option_symbol, {})
    quote = snapshot.get("latestQuote", {})
    bid = float(quote.get("bp", 0) or 0)
    ask = float(quote.get("ap", 0) or 0)
    
    for trade in contract_trades:
        price = float(trade["price"])
        size = int(trade["size"])
        premium = price * size * 100
        
        if premium < MIN_PREMIUM or size < MIN_SIZE:
            last_price = price
            filtered_count += 1
            continue
            
        processed_count += 1
        
        # Parse timestamp
        try:
            trade_dt = datetime.datetime.fromisoformat(trade["timestamp"].replace("Z", "+00:00"))
            trade_dt_et = trade_dt.astimezone(tz_eastern)
            is_recent = (now_et - trade_dt_et).total_seconds() < 900
        except:
            is_recent = False
        
        # Side Logic
        side = "BUY"
        method = "Tick"
        
        if is_recent and bid > 0 and ask > 0:
            method = "Quote"
            if price <= bid:
                side = "SELL"
            elif price >= ask:
                side = "BUY"
            else:
                # Mid-Market: Use distance
                dist_to_bid = abs(price - bid)
                dist_to_ask = abs(price - ask)
                if dist_to_bid < dist_to_ask:
                    side = "SELL"
                    method = "Mid-Bid"
                else:
                    side = "BUY"
                    method = "Mid-Ask"
        else:
            method = "Tick"
            if last_price is not None:
                if price > last_price:
                    side = "BUY"
                elif price < last_price:
                    side = "SELL"
                else:
                    side = last_side
            else:
                side = "BUY" # Default
        
        last_price = price
        last_side = side
        
        if side == "BUY": buy_count += 1
        else: sell_count += 1
        
        # Print sample
        if processed_count <= 20:
            print(f"Trade: {price} x {size} | {method} -> {side} | Quote: {bid}/{ask} | Recent: {is_recent}")

print("\n--- Summary ---")
print(f"Total Processed: {processed_count}")
print(f"Filtered (Size/Prem): {filtered_count}")
print(f"BUY: {buy_count}")
print(f"SELL: {sell_count}")
