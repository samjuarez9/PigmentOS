import os
import requests
from datetime import datetime
import pytz

from dotenv import load_dotenv
load_dotenv()

ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY")
ALPACA_DATA_URL = "https://data.alpaca.markets/v1beta1/options"

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

def check_amd_flow():
    symbol = "AMD"
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
        "Accept": "application/json"
    }
    
    # 1. Get snapshots to find contracts
    snapshot_url = f"{ALPACA_DATA_URL}/snapshots/{symbol}"
    resp = requests.get(snapshot_url, headers=headers, params={"limit": 500})
    if resp.status_code != 200:
        print(f"Error fetching snapshots: {resp.status_code}")
        return

    snapshots = resp.json().get("snapshots", {})
    jan_9_contracts = []
    for opt_sym in snapshots.keys():
        parsed = parse_occ(opt_sym)
        if parsed and parsed['expiry'] == '2026-01-09':
            jan_9_contracts.append(opt_sym)
    
    print(f"Found {len(jan_9_contracts)} contracts for Jan 9th.")
    
    if not jan_9_contracts:
        return

    # 2. Fetch trades for these contracts
    trades_url = f"{ALPACA_DATA_URL}/trades"
    tz_eastern = pytz.timezone('US/Eastern')
    now_et = datetime.now(tz_eastern)
    
    # Batch request (Alpaca allows multiple symbols)
    all_trades_list = []
    batch_size = 50
    for i in range(0, len(jan_9_contracts), batch_size):
        batch = jan_9_contracts[i:i+batch_size]
        params = {
            "symbols": ",".join(batch),
            "start": now_et.strftime("%Y-%m-%dT00:00:00Z"),
            "limit": 1000
        }
        trades_resp = requests.get(trades_url, headers=headers, params=params)
        if trades_resp.status_code == 200:
            trades_data = trades_resp.json().get("trades", {})
            for opt_sym, trades in trades_data.items():
                for t in trades:
                    all_trades_list.append((opt_sym, t))

    total_trades = 0
    call_whales = 0
    put_whales = 0
    near_miss_puts = 0
    
    for opt_sym, t in all_trades_list:
        total_trades += 1
        price = float(t.get('p', 0))
        size = int(t.get('s', 0))
        premium = price * size * 100
        parsed = parse_occ(opt_sym)
        type = parsed['type']
        
        if premium >= 100000 and size >= 50:
            if type == 'CALL':
                call_whales += 1
            else:
                put_whales += 1
            print(f"WHALE {type}: {opt_sym} | Price: {price} | Size: {size} | Premium: ${premium:,.0f}")
        elif type == 'PUT' and premium >= 25000:
            near_miss_puts += 1
            # print(f"Near-miss PUT: {opt_sym} | Price: {price} | Size: {size} | Premium: ${premium:,.0f}")

    print(f"\nSummary for AMD Jan 9th Flow:")
    print(f"Total Trades Today: {total_trades}")
    print(f"Whale Calls (>$100k, >50 size): {call_whales}")
    print(f"Whale Puts (>$100k, >50 size): {put_whales}")
    print(f"Near-miss Puts (>$25k premium): {near_miss_puts}")

if __name__ == "__main__":
    check_amd_flow()
