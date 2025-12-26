import os
import requests
import yfinance as yf
from datetime import datetime
import pytz

# Configuration
SYMBOL = "TSM"
POLYGON_API_KEY = os.environ.get("POLYGON_API_KEY")
MIN_WHALE_VAL = 500_000  # $500k for non-index/non-TSLA
VOLUME_THRESHOLD = 500

def format_money(val):
    if val >= 1_000_000: return f"${val/1_000_000:.1f}M"
    if val >= 1_000: return f"${val/1_000:.0f}k"
    return f"${val:.0f}"

def check_ticker():
    if not POLYGON_API_KEY:
        print("Error: POLYGON_API_KEY not found in environment")
        return

    print(f"🔍 Checking {SYMBOL} for whale trades...")

    # 1. Get Current Price
    try:
        ticker = yf.Ticker(SYMBOL)
        current_price = ticker.fast_info['last_price']
        print(f"   Current Price: ${current_price:.2f}")
    except Exception as e:
        print(f"   Error fetching price: {e}")
        return

    # 2. Fetch Options Snapshot
    strike_low = int(current_price * 0.90)
    strike_high = int(current_price * 1.10)
    
    url = f"https://api.polygon.io/v3/snapshot/options/{SYMBOL}"
    params = {
        "apiKey": POLYGON_API_KEY,
        "limit": 250,
        "strike_price.gte": strike_low,
        "strike_price.lte": strike_high
    }
    
    print(f"   Fetching options snapshot (Strikes: {strike_low}-{strike_high})...")
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code != 200:
            print(f"   API Error: {resp.status_code}")
            return
        data = resp.json()
    except Exception as e:
        print(f"   Fetch failed: {e}")
        return

    results = data.get("results", [])
    print(f"   Received {len(results)} contracts. Filtering...")

    # 3. Apply Filters
    tz_eastern = pytz.timezone('US/Eastern')
    now_et = datetime.now(tz_eastern)
    
    passed_count = 0
    rejection_reasons = {
        "volume": 0,
        "premium": 0,
        "ratio": 0,
        "dte": 0,
        "stale": 0
    }

    for contract in results:
        details = contract.get("details", {})
        day_data = contract.get("day", {})
        
        volume = int(day_data.get("volume", 0) or 0)
        open_interest = int(contract.get("open_interest", 0) or 0)
        last_price = float(day_data.get("close", 0) or 0)
        expiry = details.get("expiration_date", "")
        
        # Basic Data Check
        if volume == 0 or last_price == 0:
            continue

        # Calculate Metrics
        notional = volume * last_price * 100
        vol_oi_ratio = volume / open_interest if open_interest > 0 else 999
        
        # Filter 1: Volume
        if volume < VOLUME_THRESHOLD:
            rejection_reasons["volume"] += 1
            continue
            
        # Filter 2: Premium
        if notional < MIN_WHALE_VAL:
            rejection_reasons["premium"] += 1
            continue
            
        # Filter 3: Vol/OI Ratio
        if vol_oi_ratio <= 1.05:
            rejection_reasons["ratio"] += 1
            continue
            
        # Filter 4: DTE
        try:
            exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
            dte = (exp_date - now_et.date()).days
            if not (0 <= dte <= 15):
                rejection_reasons["dte"] += 1
                continue
        except:
            continue

        # Filter 5: Stale Data (Must be today)
        last_updated = day_data.get("last_updated", 0)
        if last_updated:
            trade_time_obj = datetime.fromtimestamp(last_updated / 1_000_000_000, tz=tz_eastern)
            if trade_time_obj.date() != now_et.date():
                rejection_reasons["stale"] += 1
                continue
        else:
            continue

        # PASSED!
        passed_count += 1
        print(f"\n✅ MATCH FOUND:")
        print(f"   Contract: {details.get('ticker')}")
        print(f"   Expiry: {expiry} (DTE: {dte})")
        print(f"   Type: {details.get('contract_type')}")
        print(f"   Strike: ${details.get('strike_price')}")
        print(f"   Volume: {volume}")
        print(f"   OI: {open_interest} (Ratio: {vol_oi_ratio:.1f}x)")
        print(f"   Premium: {format_money(notional)}")
        print(f"   Time: {trade_time_obj.strftime('%H:%M:%S')}")

    print("\n📊 SUMMARY")
    print(f"   Total Contracts Scanned: {len(results)}")
    print(f"   Passed Filters: {passed_count}")
    print("   Rejection Reasons:")
    for reason, count in rejection_reasons.items():
        print(f"     - {reason.title()}: {count}")

if __name__ == "__main__":
    check_ticker()
