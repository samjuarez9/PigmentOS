import json
import time
import requests
import threading
import os
from datetime import datetime, timedelta, date
import pytz
from flask import Blueprint, jsonify, request, Response, stream_with_context
from firebase_admin import firestore

# Globals to be injected
CACHE = None
POLYGON_API_KEY = None
FIRESTORE_DB = None
WHALE_WATCHLIST = None
GET_CACHED_PRICE_FUNC = None
GET_FINNHUB_PRICE_FUNC = None

WHALE_CACHE_FILE = "/tmp/pigmentos_whale_cache.json"
WHALE_CACHE_LAST_CLEAR = 0
CACHE_LOCK = threading.Lock()

whales_bp = Blueprint('whales', __name__)

def setup_whales(app, cache, polygon_key, firestore_db, watchlist, get_cached_price_func, get_finnhub_price_func):
    global CACHE, POLYGON_API_KEY, FIRESTORE_DB, WHALE_WATCHLIST, GET_CACHED_PRICE_FUNC, GET_FINNHUB_PRICE_FUNC
    CACHE = cache
    POLYGON_API_KEY = polygon_key
    FIRESTORE_DB = firestore_db
    WHALE_WATCHLIST = watchlist
    GET_CACHED_PRICE_FUNC = get_cached_price_func
    GET_FINNHUB_PRICE_FUNC = get_finnhub_price_func
    
    app.register_blueprint(whales_bp)
    
    # Load cache on startup
    load_whale_cache()

def save_whale_cache():
    """Save whale data to file for persistence across restarts."""
    try:
        with CACHE_LOCK:
            data = {
                "whales": CACHE["whales"]["data"],
                "timestamp": CACHE["whales"]["timestamp"],
                "last_clear": WHALE_CACHE_LAST_CLEAR
            }
        with open(WHALE_CACHE_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Failed to save whale cache: {e}")

def load_whale_cache():
    """Load whale data from file on startup."""
    global WHALE_CACHE_LAST_CLEAR
    try:
        if os.path.exists(WHALE_CACHE_FILE):
            with open(WHALE_CACHE_FILE, 'r') as f:
                data = json.load(f)
            
            # Check if we should clear (pre-market of next trading day)
            if should_clear_whale_cache(data.get("last_clear", 0)):
                print("🧹 Clearing stale whale cache (pre-market)")
                return
            
            with CACHE_LOCK:
                raw_whales = data.get("whales", [])
                
                # Apply 30-day DTE filter to ALL cached data (Main Dash + Expansion)
                filtered_whales = []
                tz_eastern = pytz.timezone('US/Eastern')
                now_et = datetime.now(tz_eastern)
                
                for w in raw_whales:
                    try:
                        # Check DTE
                        expiry = w.get("expirationDate")
                        if expiry:
                            expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
                            days_to_expiry = (expiry_date - now_et.date()).days
                            if days_to_expiry <= 30:
                                filtered_whales.append(w)
                    except:
                        pass
                
                CACHE["whales"]["data"] = filtered_whales
                CACHE["whales"]["timestamp"] = data.get("timestamp", 0)
                
                # 30 DTE Cache (Now redundant but kept for endpoint compatibility)
                CACHE["whales_30dte"]["data"] = filtered_whales
                CACHE["whales_30dte"]["timestamp"] = data.get("timestamp", 0)
                
            WHALE_CACHE_LAST_CLEAR = data.get("last_clear", 0)
            print(f"📂 Loaded {len(filtered_whales)} whale trades from cache (Filtered <= 30 DTE)")
    except Exception as e:
        print(f"Failed to load whale cache: {e}")

def should_clear_whale_cache(last_clear_ts):
    """
    Clear whale cache during pre-market (4 AM - 9:30 AM ET) on weekdays.
    Returns True if we're in pre-market and should show scanner animation.
    """
    tz_eastern = pytz.timezone('US/Eastern')
    now_et = datetime.now(tz_eastern)
    
    # Only clear on weekdays
    if now_et.weekday() >= 5:  # Saturday or Sunday
        return False
    
    # Pre-market is 4:00 AM - 9:30 AM ET
    current_time = now_et.hour + now_et.minute / 60
    is_premarket = 4.0 <= current_time < 9.5
    
    return is_premarket

def mark_whale_cache_cleared():
    """Mark the current time as when we cleared the cache."""
    global WHALE_CACHE_LAST_CLEAR
    WHALE_CACHE_LAST_CLEAR = time.time()

@whales_bp.route('/api/whales/snapshot')
def get_whale_snapshot():
    """
    Fetch daily snapshot for a specific ticker.
    Used for the Aftermarket Recap view.
    """
    print("DEBUG: PREMIUM FILTER ACTIVE")
    if not POLYGON_API_KEY:
        return jsonify([])
    
    symbol = request.args.get('symbol', '').upper()
    if not symbol:
        return jsonify([])
        
    try:
        # 1. Get Underlying Price for Smart Filtering
        price_data = {"price": 0}
        if GET_CACHED_PRICE_FUNC:
            price_val = GET_CACHED_PRICE_FUNC(symbol)
            if price_val:
                price_data["price"] = price_val
                
        current_price = price_data.get("price", 0)
        
        # 2. Construct Params
        params = {
            "apiKey": POLYGON_API_KEY,
            "limit": 1000,
            "expiration_date.gte": datetime.now().strftime("%Y-%m-%d"),
        }
        
        # Smart Strike Filter: +/- 50% of spot price
        if current_price > 0:
            min_strike = current_price * 0.50
            max_strike = current_price * 1.50
            params["strike_price.gte"] = min_strike
            params["strike_price.lte"] = max_strike
            print(f"DEBUG: Smart Filter for {symbol} (${current_price:.2f}): Strikes {min_strike:.2f} - {max_strike:.2f}")
        else:
            print(f"DEBUG: No price found for {symbol}, scanning full chain.")

        # 3. Fetch Snapshot (Paginated)
        results = []
        url = f"https://api.polygon.io/v3/snapshot/options/{symbol}"
        
        print(f"DEBUG: Fetching chain for {symbol}...")
        
        while url:
            try:
                resp = requests.get(url, params=params, timeout=10)
                if resp.status_code != 200:
                    print(f"Polygon Snapshot Error for {symbol}: {resp.text}")
                    break
                    
                data = resp.json()
                results.extend(data.get("results", []))
                
                # Check for next page
                url = data.get("next_url")
                if url:
                    params = {"apiKey": POLYGON_API_KEY}
                else:
                    break
            except Exception as e:
                print(f"Pagination Error: {e}")
                break
                
        print(f"DEBUG: Fetched {len(results)} total contracts. Filtering...")
        
        whales = []
        for r in results:
            details = r.get("details", {})
            day = r.get("day", {})
            greeks = r.get("greeks", {})
            
            # Construct a "Whale-like" object
            strike = details.get("strike_price")
            expiry = details.get("expiration_date")
            put_call = "C" if details.get("contract_type") == "call" else "P"
            
            # Calculate implied premium
            price = day.get("close", 0)
            volume = day.get("volume", 0)
            premium = price * volume * 100
            
            # Filter: Minimum Premium $300k (REMOVED)
            if premium < 300_000:
               print(f"DEBUG: Allowing Low Prem Trade: ${premium:,.0f} for {symbol} {strike}{put_call}")
            
            # Greeks
            delta = greeks.get("delta", 0)
            iv = greeks.get("implied_volatility", 0)
            oi = r.get("open_interest", 0)
            
            # Filter for meaningful activity
            if volume < 10:
                continue
                
            # Filter: Volume > 1.2x Open Interest
            if volume <= 1.2 * oi:
                continue
            
            # Tags
            is_lotto = abs(delta) < 0.20 if delta else False
            is_mega = premium > 1_000_000
            
            # Moneyness (Simplified)
            underlying_price = r.get("underlying_asset", {}).get("price", 0)
            moneyness = "OTM"
            if underlying_price > 0:
                if put_call == "C" and underlying_price > strike: moneyness = "ITM"
                elif put_call == "P" and underlying_price < strike: moneyness = "ITM"
            
            whales.append({
                "baseSymbol": symbol,
                "symbol": details.get("ticker"),
                "strikePrice": strike,
                "expirationDate": expiry,
                "putCall": put_call,
                "premium": f"${premium:,.0f}",
                "volume": volume,
                "openInterest": oi,
                "vol_oi": (volume / oi) if oi > 0 else 0,
                "delta": delta,
                "iv": iv,
                "is_lotto": is_lotto,
                "is_mega_whale": is_mega,
                "is_sweep": False,
                "moneyness": moneyness
            })
            
        # Sort final results by Premium (descending)
        whales.sort(key=lambda x: float(x['premium'].replace('$','').replace(',','')), reverse=True)
        
        return jsonify(whales)
        
    except Exception as e:
        print(f"Snapshot Error: {e}")
        return jsonify([])

@whales_bp.route('/api/whales/conviction')
def get_whale_conviction():
    """
    Fetch T+0 and T+1 data for a specific option contract to analyze conviction.
    Returns Day 1 Volume/OI and Day 2 OI/Volume.
    """
    ticker = request.args.get('ticker')
    date_str = request.args.get('date') # YYYY-MM-DD
    initial_oi = request.args.get('initial_oi', 0, type=int)
    
    if not ticker or not date_str:
        return jsonify({"error": "Missing ticker or date"}), 400
        
    if not POLYGON_API_KEY:
        return jsonify({"error": "Polygon API Key missing"}), 500

    try:
        # Parse date
        trade_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        
        # Calculate Next Trading Day (Day 2)
        next_day = trade_date + timedelta(days=1)
        while next_day.weekday() >= 5: # Skip Sat/Sun
            next_day += timedelta(days=1)
            
        next_date_str = next_day.strftime("%Y-%m-%d")
        
        # Check if Day 2 is in the future (or is Today)
        tz_eastern = pytz.timezone('US/Eastern')
        now_et = datetime.now(tz_eastern).date()
        
        # If next_day is in the future, we don't have Day 2 data yet
        is_pending = next_day > now_et
        
        # Fetch Current Snapshot for Day 2 Data (or Day 1 Volume confirmation)
        snapshot_url = f"https://api.polygon.io/v3/snapshot/options/{ticker}"
        snapshot_params = {"apiKey": POLYGON_API_KEY}
        
        print(f"DEBUG: Fetching Snapshot for Conviction {ticker}")
        snap_resp = requests.get(snapshot_url, params=snapshot_params, timeout=5)
        
        current_oi = 0
        current_volume = 0
        
        if snap_resp.status_code == 200:
            snap_data = snap_resp.json()
            res = snap_data.get("results", {})
            if isinstance(res, list):
                if len(res) > 0:
                    res = res[0]
                else:
                    res = {}
            
            current_oi = res.get("open_interest", 0)
            day_stats = res.get("day", {})
            current_volume = day_stats.get("volume", 0)
            
        # --- DATA MAPPING ---
        
        day1_volume = 0
        if trade_date == now_et:
            day1_volume = current_volume
        else:
            # Fetch historical volume from v1/open-close (reliable for Vol/Price)
            hist_url = f"https://api.polygon.io/v1/open-close/{ticker}/{date_str}"
            hist_resp = requests.get(hist_url, params={"apiKey": POLYGON_API_KEY}, timeout=5)
            if hist_resp.status_code == 200:
                day1_volume = hist_resp.json().get("volume", 0)
        
        day2_oi = 0
        day2_volume = 0
        
        if not is_pending:
            # If Day 2 is Today or Past
            if next_day == now_et:
                # Day 2 is Today -> Use Snapshot OI
                day2_oi = current_oi
                day2_volume = current_volume # Volume for Day 2 so far
            else:
                day2_oi = current_oi 
                
                # Fetch Day 2 Volume
                hist_url_2 = f"https://api.polygon.io/v1/open-close/{ticker}/{next_date_str}"
                hist_resp_2 = requests.get(hist_url_2, params={"apiKey": POLYGON_API_KEY}, timeout=5)
                if hist_resp_2.status_code == 200:
                    day2_volume = hist_resp_2.json().get("volume", 0)

        # --- HISTORY (BASELINE) ---
        # Fetch last 7 days to get ~5 trading days of history
        history_data = []
        try:
            start_date = trade_date - timedelta(days=10) # Go back enough to ensure 5 bars
            start_str = start_date.strftime("%Y-%m-%d")
            aggs_url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start_str}/{date_str}"
            aggs_resp = requests.get(aggs_url, params={"apiKey": POLYGON_API_KEY}, timeout=5)
            
            if aggs_resp.status_code == 200:
                aggs = aggs_resp.json().get('results', [])
                # Filter out the trade_date itself if included (we show that as Day 1)
                for bar in aggs:
                    bar_date = datetime.fromtimestamp(bar['t']/1000).date()
                    if bar_date < trade_date:
                        history_data.append({
                            "date": bar_date.strftime("%Y-%m-%d"),
                            "volume": bar.get('v', 0),
                            "oi": 0 # OI not available in aggs
                        })
                
                # Take last 4-5 days
                history_data = history_data[-5:]
        except Exception as e:
            print(f"History Fetch Error: {e}")

        response_data = {
            "ticker": ticker,
            "history": history_data,
            "day1": {
                "date": date_str,
                "volume": day1_volume,
                "oi": initial_oi, # Use passed-in OI
                "price": 0 
            },
            "day2": {
                "date": next_date_str,
                "volume": day2_volume,
                "oi": day2_oi,
                "price": 0,
                "pending": is_pending
            }
        }
        
        # Calculate Conviction
        if not is_pending and day2_oi > 0:
            delta_oi = day2_oi - initial_oi
            response_data["delta_oi"] = delta_oi
            
            if delta_oi > 0:
                ratio = delta_oi / day1_volume if day1_volume > 0 else 0
                if ratio > 0.5:
                    response_data["label"] = "POSITION OPENED"
                    response_data["conviction_score"] = "HIGH"
                else:
                    response_data["label"] = "POSITION BUILDING"
                    response_data["conviction_score"] = "MEDIUM"
            elif delta_oi < 0:
                 response_data["label"] = "POSITION CLOSED"
                 response_data["conviction_score"] = "LOW"
            else:
                response_data["label"] = "DAY TRADE / CHURN"
                response_data["conviction_score"] = "NEUTRAL"
        else:
            response_data["label"] = "PENDING"
            response_data["conviction_score"] = "UNKNOWN"
            
        return jsonify(response_data)

    except Exception as e:
        print(f"Conviction Error: {e}")
        return jsonify({"error": str(e)}), 500

def save_daily_snapshot():
    """
    Fetches daily snapshot for all watchlist tickers, filters them,
    and saves to Firestore for historical viewing.
    """
    print("📸 Starting Daily Whale Snapshot...")
    all_trades = []
    
    if not WHALE_WATCHLIST:
        print("⚠️ No watchlist provided for snapshot")
        return

    for symbol in WHALE_WATCHLIST:
        try:
            # 1. Get Underlying Price
            current_price = 0
            if GET_CACHED_PRICE_FUNC:
                price_val = GET_CACHED_PRICE_FUNC(symbol)
                if price_val:
                    current_price = price_val
            
            # 2. Construct Params
            params = {
                "apiKey": POLYGON_API_KEY,
                "limit": 1000,
                "expiration_date.gte": datetime.now().strftime("%Y-%m-%d"),
            }
            
            if current_price > 0:
                params["strike_price.gte"] = current_price * 0.50
                params["strike_price.lte"] = current_price * 1.50
            
            # 3. Fetch Snapshot (Paginated)
            results = []
            url = f"https://api.polygon.io/v3/snapshot/options/{symbol}"
            
            while url:
                try:
                    resp = requests.get(url, params=params, timeout=10)
                    if resp.status_code != 200:
                        print(f"  ❌ Snapshot failed for {symbol}: {resp.status_code}")
                        break
                        
                    data = resp.json()
                    results.extend(data.get("results", []))
                    
                    url = data.get("next_url")
                    if url:
                        params = {"apiKey": POLYGON_API_KEY}
                    else:
                        break
                except Exception as e:
                    print(f"  ⚠️ Pagination Error {symbol}: {e}")
                    break
            
            # Get current time in ET for date validation
            tz_eastern = pytz.timezone('US/Eastern')
            now_et = datetime.now(tz_eastern)
            is_weekend = now_et.weekday() >= 5  # Saturday=5, Sunday=6
            
            for r in results:
                details = r.get("details", {})
                day = r.get("day", {})
                greeks = r.get("greeks", {})
                
                # === DATE VALIDATION ===
                last_updated = day.get("last_updated", 0)
                if last_updated:
                    polygon_time_obj = datetime.fromtimestamp(last_updated / 1_000_000_000, tz=tz_eastern)
                    
                    if not is_weekend:
                        if polygon_time_obj.date() != now_et.date():
                            continue
                    else:
                        days_diff = (now_et.date() - polygon_time_obj.date()).days
                        if days_diff > 3:
                            continue
                
                volume = day.get("volume", 0)
                oi = r.get("open_interest", 0)
                
                # === FILTERS ===
                if volume < 10: continue
                if volume <= 1.2 * oi: continue
                
                # Construct Whale Object
                strike = details.get("strike_price")
                expiry = details.get("expiration_date")
                put_call = "C" if details.get("contract_type") == "call" else "P"
                price = day.get("close", 0)
                premium = price * volume * 100
                
                delta = greeks.get("delta", 0)
                
                # Moneyness
                underlying_price = r.get("underlying_asset", {}).get("price", 0)
                moneyness = "OTM"
                if underlying_price > 0:
                    if put_call == "C" and underlying_price > strike: moneyness = "ITM"
                    elif put_call == "P" and underlying_price < strike: moneyness = "ITM"

                trade = {
                    "baseSymbol": symbol,
                    "symbol": details.get("ticker"),
                    "strikePrice": strike,
                    "expirationDate": expiry,
                    "putCall": put_call,
                    "premium": f"${premium:,.0f}",
                    "volume": volume,
                    "openInterest": oi,
                    "vol_oi": (volume / oi) if oi > 0 else 0,
                    "delta": delta,
                    "iv": greeks.get("implied_volatility", 0),
                    "is_lotto": abs(delta) < 0.20 if delta else False,
                    "is_mega_whale": premium > 1_000_000,
                    "is_sweep": False,
                    "moneyness": moneyness
                }
                all_trades.append(trade)
                
        except Exception as e:
            print(f"  ⚠️ Error processing {symbol}: {e}")
            
    # Save to Firestore
    try:
        if all_trades and FIRESTORE_DB:
            today_str = datetime.now().strftime("%Y-%m-%d")
            FIRESTORE_DB.collection('whale_snapshots').document(today_str).set({
                'date': today_str,
                'trades': all_trades,
                'timestamp': time.time()
            })
            print(f"✅ Saved {len(all_trades)} trades to Firestore snapshot '{today_str}'")
        else:
            print("⚠️ No trades found for snapshot (or DB unavailable).")
            
    except Exception as e:
        print(f"❌ Firestore Save Error: {e}")

@whales_bp.route('/api/whales')
def api_whales():
    from datetime import timedelta
    global CACHE
    limit = int(request.args.get('limit', 25))
    offset = int(request.args.get('offset', 0))
    lotto_only = request.args.get('lotto') == 'true'
    
    # Check if data has been hydrated
    if CACHE["whales"]["timestamp"] == 0:
        return jsonify({"loading": True, "data": [], "stale": False, "timestamp": 0})
    
    # FILTER: Ensure we only show TODAY'S trades (Server-side safety)
    raw_data = CACHE["whales"]["data"]
    tz_eastern = pytz.timezone('US/Eastern')
    now_et = datetime.now(tz_eastern)
    today_date = now_et.date()
    weekday = now_et.weekday()
    
    # On weekends, show Friday's trades; on weekdays show today's trades
    if weekday == 5:  # Saturday
        target_date = today_date - timedelta(days=1)  # Friday
    elif weekday == 6:  # Sunday
        target_date = today_date - timedelta(days=2)  # Friday
    else:
        target_date = today_date
    
    clean_data = []
    for whale in raw_data:
        # 'timestamp' is unix epoch
        trade_dt = datetime.fromtimestamp(whale['timestamp'], tz_eastern)
        if trade_dt.date() == target_date:
            # Lotto Filter
            if lotto_only:
                if not whale.get('is_lotto', False):
                    continue
            clean_data.append(whale)
            
    # If Lotto Mode, merge with persisted history
    if lotto_only and FIRESTORE_DB:
        try:
            # Fetch persisted lottos (limit 50 for speed)
            lottos_ref = FIRESTORE_DB.collection('lottos')
            query = lottos_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(50)
            docs = query.stream()
            saved_lottos = [doc.to_dict() for doc in docs]
            
            # Merge and Deduplicate
            merged = {}
            
            # 1. Add Saved Lottos
            for l in saved_lottos:
                sig = f"{l['ticker']}_{l['timestamp']}_{l['price']}"
                merged[sig] = l
                
            # 2. Add Live Lottos (Overwrite saved if newer/same)
            for l in clean_data:
                sig = f"{l['ticker']}_{l['timestamp']}_{l['price']}"
                merged[sig] = l
                
            # Convert back to list and sort
            clean_data = list(merged.values())
            clean_data.sort(key=lambda x: x['timestamp'], reverse=True)
            
        except Exception as e:
            print(f"❌ Failed to merge saved lottos: {e}")

    sliced = clean_data[offset:offset+limit]
    
    return jsonify({
        "data": sliced,
        "stale": False,
        "timestamp": int(CACHE["whales"]["timestamp"])
    })

def fetch_option_chain_snapshot_for_flow(symbol):
    """
    Fetch option chain snapshot from Polygon for the Unusual Flow expanded view.
    """
    if not POLYGON_API_KEY:
        return None
    
    try:
        # Get current price from Finnhub for moneyness calculation
        current_price = 0
        if GET_FINNHUB_PRICE_FUNC:
            price_val = GET_FINNHUB_PRICE_FUNC(symbol)
            if price_val:
                current_price = price_val
        
        if not current_price:
            print(f"⚠️ Could not get price for {symbol}, using fallback")
            current_price = 0
        
        # Calculate strike range (±15% for comprehensive view)
        strike_low = int(current_price * 0.85) if current_price else 0
        strike_high = int(current_price * 1.15) if current_price else 999999
        
        # Calculate 30 DTE date filter
        tz_eastern = pytz.timezone('US/Eastern')
        now_et = datetime.now(tz_eastern)
        max_expiry = (now_et + timedelta(days=30)).strftime('%Y-%m-%d')
        
        # Polygon Option Chain Snapshot endpoint
        url = f"https://api.polygon.io/v3/snapshot/options/{symbol}"
        params = {
            "apiKey": POLYGON_API_KEY,
            "limit": 250,
            "strike_price.gte": strike_low,
            "strike_price.lte": strike_high,
            "expiration_date.lte": max_expiry
        }
        
        resp = requests.get(url, params=params, timeout=15)
        
        if resp.status_code != 200:
            print(f"❌ Polygon Snapshot Error ({symbol}): Status {resp.status_code}")
            return None
        
        data = resp.json()
        results = data.get("results", [])
        
        if not results:
            print(f"⚠️ No options data for {symbol}")
            return None
        
        whale_trades = []
        
        for contract in results:
            try:
                details = contract.get("details", {})
                day = contract.get("day", {})
                greeks = contract.get("greeks", {})
                quote = contract.get("last_quote", {})
                trade = contract.get("last_trade", {})
                underlying = contract.get("underlying_asset", {})
                
                # Extract core data
                strike = details.get("strike_price", 0)
                contract_type = details.get("contract_type", "").lower()
                expiry = details.get("expiration_date", "")
                ticker = details.get("ticker", "")
                
                # Volume and Open Interest
                volume = day.get("volume", 0) or day.get("v", 0) or 0
                oi = contract.get("open_interest", 0) or 0
                
                # Minimum volume filter for noise reduction
                if volume < 100:
                    continue
                
                # Vol/OI ratio (key unusual activity indicator)
                vol_oi = volume / oi if oi > 0 else 999
                
                # Strictly filter: only show contracts with Vol/OI >= 1.2
                if vol_oi < 1.2:
                    continue
                
                # Pricing data
                last_price = trade.get("price", 0) or day.get("close", 0) or 0
                bid = quote.get("bid", 0) or 0
                ask = quote.get("ask", 0) or 0
                midpoint = quote.get("midpoint", 0) or ((bid + ask) / 2 if bid and ask else 0)
                
                # Premium calculation (volume * price * 100)
                notional = volume * last_price * 100
                
                # Premium threshold ($25k minimum for whale status)
                if notional < 25000:
                    continue
                
                # Greeks
                delta = greeks.get("delta", 0) or 0
                
                # Moneyness
                moneyness = "OTM"
                if current_price > 0:
                    if contract_type == "call" and current_price > strike: moneyness = "ITM"
                    elif contract_type == "put" and current_price < strike: moneyness = "ITM"
                
                whale_trades.append({
                    "baseSymbol": symbol,
                    "symbol": ticker,
                    "strikePrice": strike,
                    "expirationDate": expiry,
                    "putCall": "C" if contract_type == "call" else "P",
                    "premium": f"${notional:,.0f}",
                    "volume": volume,
                    "openInterest": oi,
                    "vol_oi": vol_oi,
                    "delta": delta,
                    "iv": greeks.get("implied_volatility", 0) or 0,
                    "is_lotto": abs(delta) < 0.20,
                    "is_mega_whale": notional > 1_000_000,
                    "is_sweep": False,
                    "moneyness": moneyness,
                    "notional_value": notional,
                    "timestamp": time.time()
                })
                
            except Exception as e:
                continue
                
        return whale_trades
        
    except Exception as e:
        print(f"Snapshot Logic Error: {e}")
        return None

@whales_bp.route('/api/whales/rest')
def api_whales_rest():
    """
    Endpoint for the Expanded View (REST Polling).
    Uses Polygon Option Chain Snapshot for fresh, accurate data.
    Falls back to cache if no symbol specified or API fails.
    """
    symbol = request.args.get('symbol', '').upper()
    limit = int(request.args.get('limit', 100))
    date_filter = request.args.get('date')  # Optional date filter for historical view
    
    # If a specific symbol is requested, fetch fresh snapshot data
    if symbol and symbol != "ALL" and POLYGON_API_KEY:
        snapshot_data = fetch_option_chain_snapshot_for_flow(symbol)
        if snapshot_data:
            # Sort by premium (notional value) descending
            snapshot_data.sort(key=lambda x: x.get('notional_value', 0), reverse=True)
            return jsonify({
                "data": snapshot_data[:limit],
                "timestamp": time.time(),
                "source": "polygon_snapshot"
            })
    
    # Fallback: Use cached data from WebSocket/polling
    data = list(CACHE["whales"]["data"])
    
    # Filter by Symbol
    if symbol and symbol != "ALL":
        data = [w for w in data if w.get('baseSymbol') == symbol]
        
    # Sort by Timestamp Descending
    data.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
    
    return jsonify({
        "data": data[:limit],
        "timestamp": CACHE["whales"]["timestamp"],
        "source": "cache"
    })

@whales_bp.route('/api/whales/stream')
def api_whales_stream():
    def generate():
        # Initial Data
        current_time = time.time()
        # Just yield the cache periodically
        while True:
            # Send immediately on connect
            # FILTER: Ensure we only show TODAY'S trades (Server-side safety)
            raw_data = CACHE["whales"]["data"]
            tz_eastern = pytz.timezone('US/Eastern')
            now_et = datetime.now(tz_eastern)
            today_date = now_et.date()
            weekday = now_et.weekday()
            
            # On weekends, show Friday's trades; on weekdays show today's trades
            target_date = today_date
            
            clean_data = []
            for whale in raw_data:
                # 'timestamp' is unix epoch
                trade_dt = datetime.fromtimestamp(whale['timestamp'], tz_eastern)
                if trade_dt.date() == target_date:
                    clean_data.append(whale)

            yield f"data: {json.dumps({'data': clean_data, 'stale': False, 'timestamp': int(CACHE['whales']['timestamp'])})}\\n\\n"
            # Optimization: Slow down stream when market is closed
            tz_eastern = pytz.timezone('US/Eastern')
            now = datetime.now(tz_eastern)
            # Options trade 9:30 AM - 4:15 PM ET
            is_market_hours = (now.weekday() < 5) and (
                (now.hour > 9 or (now.hour == 9 and now.minute >= 30)) and 
                (now.hour < 16 or (now.hour == 16 and now.minute < 15))
            )
            
            sleep_time = 5 if is_market_hours else 60
            time.sleep(sleep_time)

    return Response(stream_with_context(generate()), mimetype='text/event-stream')
