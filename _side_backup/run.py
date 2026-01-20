# Gevent monkey patching - ONLY for production (gunicorn)
# Skip for local development to avoid SSL conflicts with requests library
import os
if os.environ.get('GUNICORN_WORKER') or os.environ.get('DYNO'):  # Render/Heroku sets DYNO
    from gevent import monkey
    monkey.patch_all(ssl=False)
    print("🐒 Gevent monkey patching enabled (production mode)")
else:
    print("🔧 Running in local development mode (no gevent)")

# === WEBSOCKET DISABLED ===
# WebSocket causes SSL conflicts with other network calls.
# Using REST snapshot polling instead (more reliable).
DISABLE_WEBSOCKET = True

import json
import whales_service
import time
import random
import threading
import concurrent.futures
import requests
import socket

# Set global timeout to prevent hanging requests (e.g. blocked yfinance)
socket.setdefaulttimeout(5)

import yfinance as yf
# Set cache to /tmp for Render compatibility
try:
    yf.set_tz_cache_location("/tmp/yfinance_cache")
except:
    pass

import pandas as pd
import statistics
import os
from dotenv import load_dotenv
load_dotenv()  # Load .env file for POLYGON_API_KEY and other secrets

# Alpaca API Configuration (Hybrid Approach for Real-time Quotes)
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_DATA_URL = "https://data.alpaca.markets/v1beta1/options"

import ssl
import calendar
from datetime import datetime, date, timedelta
import pytz
from flask import Flask, jsonify, Response, request, send_from_directory, stream_with_context
from flask_cors import CORS
import feedparser
import re

# Fix for SSL Certificate Verify Failed
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Initialize Flask App
app = Flask(__name__, static_folder='.')
CORS(app)

# Timeout wrapper for external calls (prevents hanging)
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
TIMEOUT_EXECUTOR = ThreadPoolExecutor(max_workers=10)

def with_timeout(func, timeout_seconds=5):
    """Run a function with a timeout. Returns None if timeout."""
    try:
        # Safety check: don't submit if executor is shutting down
        if TIMEOUT_EXECUTOR._shutdown:
            print(f"⚠️ Executor shutdown, running {func} directly")
            return func()
        future = TIMEOUT_EXECUTOR.submit(func)
        return future.result(timeout=timeout_seconds)
    except FuturesTimeoutError:
        print(f"⏰ Timeout after {timeout_seconds}s: {func}")
        return None
    except RuntimeError as e:
        if "cannot schedule" in str(e) or "shutdown" in str(e).lower():
            # Executor is shutting down, run synchronously
            print(f"⚠️ Executor unavailable, running {func} directly")
            try:
                return func()
            except:
                return None
        raise
    except Exception as e:
        err_str = str(e)
        if "Too Many Requests" in err_str:
            print(f"⚠️ Rate Limit (Too Many Requests) in {func.__name__ if hasattr(func, '__name__') else 'func'}")
        else:
            print(f"⚠️ Error in with_timeout: {e}")
        return None

# Rate Limiting
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["20000 per day", "5000 per hour"],
    storage_uri="memory://"
)

# Stripe Configuration
import stripe
from stripe_config import STRIPE_SECRET_KEY, STRIPE_PRICE_ID, TRIAL_DAYS, STRIPE_WEBHOOK_SECRET, FIREBASE_CREDENTIALS_B64
stripe.api_key = STRIPE_SECRET_KEY

# Firebase Admin SDK Initialization
import firebase_admin
from firebase_admin import credentials, firestore, auth as firebase_auth
import base64

firestore_db = None  # Will be initialized if credentials are available

if FIREBASE_CREDENTIALS_B64:
    try:
        creds_json = base64.b64decode(FIREBASE_CREDENTIALS_B64).decode('utf-8')
        creds_dict = json.loads(creds_json)
        cred = credentials.Certificate(creds_dict)
        firebase_admin.initialize_app(cred)
        firestore_db = firestore.client()
        print("✅ Firebase Admin SDK initialized successfully")
    except Exception as e:
        print(f"⚠️ Firebase Admin SDK initialization failed: {e}")
else:
    print("⚠️ FIREBASE_CREDENTIALS_B64 not set - Firestore updates will be disabled")



@app.route('/preview')
def preview_page():
    return send_from_directory('.', 'preview.html')

@app.route('/api/whales/snapshot')
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
        price_data = get_cached_price(symbol)
        current_price = price_data.get("price", 0)
        
        # 2. Construct Params
        params = {
            "apiKey": POLYGON_API_KEY,
            "limit": 1000,
            "expiration_date.gte": datetime.now().strftime("%Y-%m-%d"),
        }
        
        # Smart Strike Filter: +/- 50% of spot price
        # This removes deep OTM garbage and reduces API load
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

@app.route('/api/whales/conviction')
def get_whale_conviction():
    """
    Fetch T+0 and T+1 data for a specific option contract to analyze conviction.
    Returns Day 1 Volume/OI and Day 2 OI/Volume.
    
    Strategy:
    - Day 1 OI: Provided by frontend (from the original trade snapshot).
    - Day 2 OI: Fetched from Polygon v3/snapshot (Current OI).
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
        # v3/snapshot gives us the *current* state of the contract
        snapshot_url = f"https://api.polygon.io/v3/snapshot/options/{ticker}"
        snapshot_params = {"apiKey": POLYGON_API_KEY}
        
        print(f"DEBUG: Fetching Snapshot for Conviction {ticker}")
        snap_resp = requests.get(snapshot_url, params=snapshot_params, timeout=5)
        
        current_oi = 0
        current_volume = 0
        
        if snap_resp.status_code == 200:
            snap_data = snap_resp.json()
            res = snap_data.get("results", {})
            # Handle both list and dict return types (snapshot usually returns dict for single ticker?)
            # v3/snapshot/options/{ticker} returns a single object in 'results' usually? 
            # Actually docs say it returns a wrapper. Let's be safe.
            if isinstance(res, list):
                if len(res) > 0:
                    res = res[0]
                else:
                    res = {}
            
            current_oi = res.get("open_interest", 0)
            day_stats = res.get("day", {})
            current_volume = day_stats.get("volume", 0)
            
        # --- DATA MAPPING ---
        
        # Day 1 (Trade Day)
        # Volume: We need Day 1 Volume. 
        # If trade_date == Today, use current_volume.
        # If trade_date < Today, we need historical volume.
        
        day1_volume = 0
        if trade_date == now_et:
            day1_volume = current_volume
        else:
            # Fetch historical volume from v1/open-close (reliable for Vol/Price)
            hist_url = f"https://api.polygon.io/v1/open-close/{ticker}/{date_str}"
            hist_resp = requests.get(hist_url, params={"apiKey": POLYGON_API_KEY}, timeout=5)
            if hist_resp.status_code == 200:
                day1_volume = hist_resp.json().get("volume", 0)
        
        # Day 2 (Follow-through)
        # OI: If Day 2 is Today (or past), use current_oi (Snapshot).
        # Note: Snapshot OI is updated morning of Today. So it represents "Today's" OI.
        # If trade was Yesterday, Today's OI is the Day 2 OI.
        
        day2_oi = 0
        day2_volume = 0
        
        if not is_pending:
            # If Day 2 is Today or Past
            if next_day == now_et:
                # Day 2 is Today -> Use Snapshot OI
                day2_oi = current_oi
                day2_volume = current_volume # Volume for Day 2 so far
            else:
                # Day 2 was in the past -> We need historical OI? 
                # We established we CANNOT get historical OI easily.
                # Fallback: Use current_oi as the "latest" OI. 
                # It's better than 0.
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
            # Range: start_date to trade_date (exclusive of trade_date usually, but aggs are inclusive)
            # We want strictly BEFORE trade_date
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
        # Only if we have valid Day 2 data
        if not is_pending and day2_oi > 0:
            delta_oi = day2_oi - initial_oi
            response_data["delta_oi"] = delta_oi
            
            # Logic: If Delta OI > 0 and significant relative to volume
            # Threshold: 50% of Day 1 Volume? Or just positive?
            # User said: "If Delta OI is positive and close to Monday's Volume"
            
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
    
    for symbol in WHALE_WATCHLIST:
        try:
            # 1. Get Underlying Price
            price_data = get_cached_price(symbol)
            current_price = price_data.get("price", 0)
            
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
                # Polygon returns last_updated as nanoseconds since epoch (UTC)
                # Convert to ET and ensure data is from today's market session
                last_updated = day.get("last_updated", 0)
                if last_updated:
                    # Convert nanoseconds to seconds, then to ET datetime
                    polygon_time_obj = datetime.fromtimestamp(last_updated / 1_000_000_000, tz=tz_eastern)
                    
                    if not is_weekend:
                        # On weekdays, only accept today's data
                        if polygon_time_obj.date() != now_et.date():
                            continue
                    else:
                        # On weekends, allow data from up to 3 days ago (Friday's data)
                        days_diff = (now_et.date() - polygon_time_obj.date()).days
                        if days_diff > 3:
                            continue
                
                volume = day.get("volume", 0)
                oi = r.get("open_interest", 0)
                
                # === FILTERS ===
                # 1. Minimum Volume
                if volume < 10: continue
                
                # 2. Vol/OI Ratio > 1.2 (Unusual Activity)
                if volume <= 1.2 * oi: continue
                
                # Construct Whale Object
                strike = details.get("strike_price")
                expiry = details.get("expiration_date")
                put_call = "C" if details.get("contract_type") == "call" else "P"
                price = day.get("close", 0)
                premium = price * volume * 100
                
                # Filter: Minimum Premium $300k
                # if premium < 300_000: continue
                
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
        if all_trades:
            today_str = datetime.now().strftime("%Y-%m-%d")
            db.collection('whale_snapshots').document(today_str).set({
                'date': today_str,
                'trades': all_trades,
                'timestamp': time.time()
            })
            print(f"✅ Saved {len(all_trades)} trades to Firestore snapshot '{today_str}'")
        else:
            print("⚠️ No trades found for snapshot.")
            
    except Exception as e:
        print(f"❌ Firestore Save Error: {e}")

# Watchlist for "Whale" Scan
WATCHLIST = [
    "NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "GOOG",
    "AMD", "AVGO", "ARM", "SMCI", "MU", "INTC",
    "PLTR", "SOFI", "RKLB", "ORCL",
    "SPY", "QQQ", "IWM"
]

MEGA_WHALE_THRESHOLD = 8_000_000  # $8M
MEGA_WHALE_THRESHOLD_TSLA = 30_000_000  # $30M for TSLA

# Cache structure
CACHE_DURATION = 120 # 2 minutes (was 300)
MACRO_CACHE_DURATION = 120 # 2 minutes (was 300)
CACHE_LOCK = threading.Lock()
POLY_STATE = {}

CACHE = {
    "whales": {"data": [], "timestamp": 0},
    "whales_rest": {"data": [], "timestamp": 0}, # REST Polling (Expanded View)
    "whales_30dte": {"data": [], "timestamp": 0},
    "vix": {"data": {"value": 0, "rating": "Neutral"}, "timestamp": 0},
    "cnn_fear_greed": {"data": {"value": 50, "rating": "Neutral"}, "timestamp": 0},
    "polymarket": {"data": [], "timestamp": 0, "is_mock": False},
    "movers": {"data": [], "timestamp": 0},
    "movers": {"data": [], "timestamp": 0},
    "news": {"data": [], "timestamp": 0},
    "heatmap": {"data": [], "timestamp": 0},
    "gamma_SPY": {"data": None, "timestamp": 0},
    "economic_calendar": {"data": [], "timestamp": 0}
}

# Service Status Tracker
SERVICE_STATUS = {
    "POLY": {"status": "ONLINE", "last_updated": 0},
    "YFIN": {"status": "ONLINE", "last_updated": 0},
    "RSS": {"status": "ONLINE", "last_updated": 0},
    "GAMMA": {"status": "ONLINE", "last_updated": 0}
}

@app.route('/api/status')
def api_status():
    return jsonify(SERVICE_STATUS)

# --- HELPER FUNCTIONS ---

# === CONFIGURATION ===
WHALE_WATCHLIST = [
    'NVDA', 'TSLA', 'AAPL', 'AMD', 'MSFT', 'AMZN', 
    'META', 'GOOG', 'GOOGL', 'PLTR', 'MU', 'ORCL', 'TSM'
]

# MarketData.app API Token (for enhanced options data)
MARKETDATA_TOKEN = os.environ.get("MARKETDATA_TOKEN")
# Rate limit tracking for MarketData.app
MARKETDATA_LAST_REQUEST = 0
MARKETDATA_MIN_INTERVAL = 0.25  # 250ms between requests

# Polygon.io API Key (primary options data source - unlimited calls)
POLYGON_API_KEY = os.environ.get("POLYGON_API_KEY")
FMP_API_KEY = os.environ.get("FMP_API_KEY")  # No longer used
FRED_API_KEY = os.environ.get("FRED_API_KEY", "9832f887b004951ec7d53cb78f1063a0")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "d56539pr01qu3qo8fk40d56539pr01qu3qo8fk4g")

# Price cache to reduce redundant API calls (TTL: 15 minutes)
PRICE_CACHE = {}  # {symbol: {"price": float, "timestamp": float}}
PRICE_CACHE_TTL = 900  # seconds (15 mins)

# === WHALE CACHE PERSISTENCE ===
WHALE_CACHE_FILE = "/tmp/pigmentos_whale_cache.json"
WHALE_CACHE_LAST_CLEAR = 0  # Track when we last cleared



def get_cached_price(symbol):
    """Get price from cache or fetch from yfinance if stale/missing."""
    global PRICE_CACHE
    
    now = time.time()
    
    # Check cache
    if symbol in PRICE_CACHE:
        cached = PRICE_CACHE[symbol]
        # If valid price and fresh
        if cached["price"] is not None and (now - cached["timestamp"] < PRICE_CACHE_TTL):
            return cached["price"]
        # If negative cache (failed recently), wait 120s before retrying
        if cached["price"] is None and (now - cached["timestamp"] < 120):
            return None
    
    # Fetch from yfinance with timeout (Primary source for price)
    try:
        def fetch_price():
            t = yf.Ticker(symbol)
            return t.fast_info.last_price
        
        price = with_timeout(fetch_price, timeout_seconds=5)
        if price:
            PRICE_CACHE[symbol] = {"price": price, "timestamp": now}
            return price
    except Exception as e:
        print(f"yfinance price error ({symbol}): {e}")
        # Return stale cache if available
        if symbol in PRICE_CACHE and PRICE_CACHE[symbol]["price"] is not None:
            PRICE_CACHE[symbol]["timestamp"] = now  # Bump timestamp
            return PRICE_CACHE[symbol]["price"]
    
    # Cache the failure for 30s
    PRICE_CACHE[symbol] = {"price": None, "timestamp": now}
    return None

# Separate cache for Finnhub prices (used by Gamma Wall and Unusual Whales only)
FINNHUB_PRICE_CACHE = {}  # {symbol: {"price": float, "timestamp": float}}
FINNHUB_PRICE_CACHE_TTL = 60  # 1 minute TTL (fresher than yfinance cache)

def get_finnhub_price(symbol):
    """Get price from Finnhub API (used by Gamma Wall and Unusual Whales only).
    
    Uses Finnhub REST API for faster, more reliable price fetching.
    Falls back to Polygon previous close if Finnhub fails (after-hours, rate limit).
    Has its own cache to avoid affecting yfinance-based features.
    """
    global FINNHUB_PRICE_CACHE
    
    if not FINNHUB_API_KEY:
        return None
    
    now = time.time()
    
    # Check cache first
    if symbol in FINNHUB_PRICE_CACHE:
        cached = FINNHUB_PRICE_CACHE[symbol]
        if cached["price"] is not None and (now - cached["timestamp"] < FINNHUB_PRICE_CACHE_TTL):
            return cached["price"]
    
    # Fetch from Finnhub
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            price = data.get("c")  # "c" = current price
            if price and price > 0:
                FINNHUB_PRICE_CACHE[symbol] = {"price": price, "timestamp": now}
                print(f"📈 Finnhub price {symbol}: ${price:.2f}")
                return price
    except Exception as e:
        print(f"Finnhub price error ({symbol}): {e}")
    
    # Return stale cache if available
    if symbol in FINNHUB_PRICE_CACHE and FINNHUB_PRICE_CACHE[symbol]["price"]:
        return FINNHUB_PRICE_CACHE[symbol]["price"]
    
    # FALLBACK: Polygon previous close (works after hours when Finnhub fails)
    if POLYGON_API_KEY:
        try:
            url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/prev?apiKey={POLYGON_API_KEY}"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("results"):
                    price = data["results"][0].get("c")  # Previous close
                    if price and price > 0:
                        FINNHUB_PRICE_CACHE[symbol] = {"price": price, "timestamp": now}
                        print(f"📈 Polygon fallback price {symbol}: ${price:.2f}")
                        return price
        except Exception as e:
            print(f"Polygon fallback price error ({symbol}): {e}")
    
    return None

def fetch_options_chain_polygon(symbol, strike_limit=40):
    """
    Fetch options chain snapshot from Polygon.io API.
    Returns data formatted for Gamma Wall or None if failed.
    
    Polygon Starter: Unlimited API calls, 15-min delayed, Greeks included.
    """
    if not POLYGON_API_KEY:
        return None
    
    try:
        # Get current price from Finnhub (faster than yfinance)
        from datetime import timedelta
        
        current_price = get_finnhub_price(symbol)
            
        # FALLBACK: If price fetch fails (Rate Limit/403), use a safe default to allow Gamma Wall to load
        if not current_price:
            # Try to get from last known good state or hardcoded defaults
            defaults = {"SPY": 600, "QQQ": 500, "IWM": 220, "DIA": 440}
            current_price = defaults.get(symbol, 100)
            print(f"Polygon: Price fetch failed, using fallback {current_price} for {symbol}")

        # Calculate strike range
        # For indices (SPY, QQQ, IWM, DIA), use TIGHTER range (±5%) to avoid hitting 250-item limit
        # which truncates upside data (since Polygon sorts asc).
        # For others, use wider range (±20%) to capture more context.
        if symbol.upper() in ['SPY', 'QQQ', 'IWM', 'DIA']:
            strike_low = int(current_price * 0.95)
            strike_high = int(current_price * 1.05)
        else:
            strike_low = int(current_price * 0.80)
            strike_high = int(current_price * 1.20)
        
        # Smart expiration selection for SPY/QQQ/IWM/DIA:
        tz_eastern = pytz.timezone('US/Eastern')
        now_et = datetime.now(tz_eastern)
        today_weekday = now_et.weekday()  # 0=Mon, 4=Fri, 5=Sat, 6=Sun
        
        pre_market_start = now_et.replace(hour=4, minute=0, second=0, microsecond=0)
        market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
        post_market_end = now_et.replace(hour=20, minute=0, second=0, microsecond=0)
        
        is_weekend = today_weekday >= 5
        
        # Tickers with daily expirations (0DTE available)
        daily_expiry_tickers = ['SPY', 'QQQ', 'IWM', 'DIA']
        has_daily = symbol.upper() in daily_expiry_tickers
        
        # Custom Logic: Switch to next expiry at 5:00 PM ET (17:00)
        # This allows users to see next day's levels after market close
        switch_hour = 17 
        current_hour = now_et.hour
        
        # Track if we're showing next trading day data
        is_next_trading_day = False
        date_label = "TODAY"
        
        if is_weekend:
            is_next_trading_day = True
            if has_daily:
                # Weekend + daily ticker: use next Monday (Polygon has Monday options ready)
                days_until_monday = (7 - today_weekday) % 7
                if days_until_monday == 0:
                    days_until_monday = 1
                expiry_date = (now_et + timedelta(days=days_until_monday)).strftime("%Y-%m-%d")
                # Format: "MON DEC 23"
                next_day = now_et + timedelta(days=days_until_monday)
                date_label = next_day.strftime("%a %b %d").upper()
                print(f"Polygon: Weekend - using Monday {expiry_date} for {symbol}")
            else:
                # Weekend + non-daily ticker: use next Friday for DATA, but label as Monday for UI consistency
                days_until_friday = (4 - today_weekday + 7) % 7
                if days_until_friday == 0:
                    days_until_friday = 7
                expiry_date = (now_et + timedelta(days=days_until_friday)).strftime("%Y-%m-%d")
                
                # UI LABEL: Always show next trading day (Monday) to match SPY/QQQ
                days_until_monday = (7 - today_weekday) % 7
                if days_until_monday == 0: days_until_monday = 1
                next_trading_day = now_et + timedelta(days=days_until_monday)
                date_label = next_trading_day.strftime("%a %b %d").upper()
                
                print(f"Polygon: Weekend - using Friday {expiry_date} for {symbol} (Label: {date_label})")
        elif has_daily:
            # For daily tickers (SPY, QQQ, etc.)
            # Keep showing TODAY's expiry until 5:00 PM
            if current_hour < switch_hour:
                expiry_date = now_et.strftime("%Y-%m-%d")
                date_label = "TODAY"
                print(f"Polygon: Pre-5PM - using today {expiry_date} for {symbol}")
            else:
                # After 5 PM, switch to next trading day
                is_next_trading_day = True
                if today_weekday == 4:  # Friday -> Monday
                    days_ahead = 3
                elif today_weekday == 5:  # Saturday -> Monday
                    days_ahead = 2
                elif today_weekday == 6:  # Sunday -> Monday
                    days_ahead = 1
                else:
                    days_ahead = 1
                next_day = now_et + timedelta(days=days_ahead)
                expiry_date = next_day.strftime("%Y-%m-%d")
                date_label = next_day.strftime("%a %b %d").upper()
                print(f"Polygon: Post-5PM - using next expiry {expiry_date} for {symbol}")
        else:
            # Non-daily tickers: always use next Friday
            days_until_friday = (4 - today_weekday) % 7
            
            # If it's Friday and after 5 PM, switch to NEXT Friday for data
            if days_until_friday == 0 and current_hour >= switch_hour:
                days_until_friday = 7
                
            next_friday = now_et + timedelta(days=days_until_friday)
            expiry_date = next_friday.strftime("%Y-%m-%d")
            
            # UI LABEL LOGIC:
            # For individual tickers, show the actual Friday date we are using
            is_next_trading_day = True
            date_label = next_friday.strftime("%a %b %d").upper()
            
            print(f"Polygon: Using Friday {expiry_date} for {symbol} (Label: {date_label})")
        
        # Polygon options chain snapshot endpoint
        url = f"https://api.polygon.io/v3/snapshot/options/{symbol}"
        
        params = {
            "apiKey": POLYGON_API_KEY,
            "limit": 250,  # Polygon max is 250
            "strike_price.gte": strike_low,
            "strike_price.lte": strike_high,
            "expiration_date": expiry_date,
            "order": "asc",
            "sort": "strike_price"
        }
        
        resp = requests.get(url, params=params, timeout=15)
        
        # No fallback - if no data, return None (status light will indicate issue)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "OK" and data.get("results"):
                print(f"Polygon: Fetched {len(data['results'])} contracts for {symbol} (exp: {expiry_date})")
                data["_current_price"] = current_price
                data["_expiry_date"] = expiry_date  # Include expiry in response
                data["_is_next_trading_day"] = is_next_trading_day  # Flag for UI
                data["_date_label"] = date_label  # Formatted label for UI
                return data
            else:
                print(f"Polygon: No data for {symbol} exp:{expiry_date}")
                return None
        
        if resp.status_code == 403:
            print(f"Polygon Auth Error - check API key")
            return None
        print(f"Polygon Error ({symbol}): Status {resp.status_code}")
        return None
        
    except Exception as e:
        print(f"Polygon Fetch Failed ({symbol}): {e}")
        return None

def parse_polygon_to_gamma_format(polygon_data, current_price=None):
    """
    Convert Polygon options snapshot to Gamma Wall format.
    Groups contracts by strike and aggregates call/put volume.
    """
    gamma_data = {}
    underlying_price = current_price
    
    # Get underlying price from Polygon stocks API if not provided
    if not underlying_price and POLYGON_API_KEY:
        try:
            # Use Polygon previous close endpoint for price
            price_url = f"https://api.polygon.io/v2/aggs/ticker/SPY/prev"
            price_resp = requests.get(price_url, params={"apiKey": POLYGON_API_KEY}, timeout=5)
            if price_resp.status_code == 200:
                price_data = price_resp.json()
                if price_data.get("results"):
                    underlying_price = price_data["results"][0].get("c", 0)  # close price
        except:
            pass
    
    # If still no price, return with a sensible fallback (no yfinance)
    if not underlying_price:
        underlying_price = 600  # Fallback default for SPY
    
    for contract in polygon_data.get("results", []):
        details = contract.get("details", {})
        strike = details.get("strike_price")
        side = details.get("contract_type", "").lower()  # "call" or "put"
        
        if not strike or not side:
            continue
        
        if strike not in gamma_data:
            gamma_data[strike] = {
                "call_vol": 0, "put_vol": 0, 
                "call_oi": 0, "put_oi": 0, 
                "call_premium": 0, "put_premium": 0,
                "call_gex": 0, "put_gex": 0,  # GEX per strike
                "net_gex": 0  # Net GEX (industry standard: call_gex + put_gex)
            }
        
        day_data = contract.get("day", {})
        greeks = contract.get("greeks", {})
        
        vol = int(day_data.get("volume", 0) or 0)
        oi = int(contract.get("open_interest", 0) or 0)
        price = float(day_data.get("close", 0) or day_data.get("vwap", 0) or 0)  # Contract price
        gamma_val = float(greeks.get("gamma", 0) or 0)
        
        # GEX Formula (Industry Standard - 1% Move Normalization):
        # GEX = Gamma × OI × 100 shares × Spot² × 0.01
        # This represents "$ of shares MMs must trade per 1% move in underlying"
        # Calls = positive GEX (MM buys dips), Puts = negative GEX (MM sells dips)
        gex = gamma_val * oi * 100 * (underlying_price ** 2) * 0.01 if gamma_val and oi else 0
        
        if side == "call":
            gamma_data[strike]["call_vol"] += vol
            gamma_data[strike]["call_oi"] += oi
            gamma_data[strike]["call_premium"] = max(gamma_data[strike]["call_premium"], price)
            gamma_data[strike]["call_gex"] += gex  # Positive (bullish hedging)
            gamma_data[strike]["net_gex"] += gex  # Net GEX: calls add
        else:
            gamma_data[strike]["put_vol"] += vol
            gamma_data[strike]["put_oi"] += oi
            gamma_data[strike]["put_premium"] = max(gamma_data[strike]["put_premium"], price)
            gamma_data[strike]["put_gex"] -= gex  # Negative (bearish hedging)
            gamma_data[strike]["net_gex"] -= gex  # Net GEX: puts subtract
    
    return gamma_data, underlying_price




def fetch_unusual_options_polygon(symbol):
    """
    Fetch options data from Polygon and detect unusual activity (whale trades).
    Returns list of whale trades meeting criteria.
    """
    if not POLYGON_API_KEY:
        return None
    
    try:
        from datetime import timedelta
        
        # Get current price from Finnhub (faster than yfinance)
        current_price = get_finnhub_price(symbol)
        
        if not current_price:
            print(f"Finnhub: Could not get price for {symbol}, skipping whale scan")
            return None
        
        # Calculate strike range (±10% for whale detection - wider range)
        strike_low = int(current_price * 0.90)
        strike_high = int(current_price * 1.10)
        
        # Polygon snapshot endpoint
        url = f"https://api.polygon.io/v3/snapshot/options/{symbol}"
        params = {
            "apiKey": POLYGON_API_KEY,
            "limit": 250,
            "strike_price.gte": strike_low,
            "strike_price.lte": strike_high
        }
        
        resp = requests.get(url, params=params, timeout=15)
        
        if resp.status_code != 200:
            print(f"Polygon Whale Error ({symbol}): Status {resp.status_code}")
            return None
        
        data = resp.json()
        if not data.get("results"):
            return None
        
        # Store current price for moneyness calculation
        data["_current_price"] = current_price
        return data
        
    except Exception as e:
        print(f"Polygon Whale Fetch Failed ({symbol}): {e}")
        return None


def fetch_polygon_historical_aggs(contract_symbol, timespan="minute", multiplier=5, limit=5000):
    """
    Fetch historical aggregates (bars) for a specific option contract from Polygon.
    Used for the "Trade Visualization" chart as a fallback for restricted Trades API.
    """
    if not POLYGON_API_KEY:
        return None
        
    try:
        # Calculate date range (last 30 days)
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        # Polygon v2 Aggs Endpoint
        # https://api.polygon.io/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}
        url = f"https://api.polygon.io/v2/aggs/ticker/{contract_symbol}/range/{multiplier}/{timespan}/{start_date}/{end_date}"
        
        params = {
            "apiKey": POLYGON_API_KEY,
            "limit": limit,
            "adjusted": "true",
            "sort": "asc"
        }
        
        resp = requests.get(url, params=params, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            return results
        else:
            print(f"Polygon Aggs Error ({contract_symbol}): {resp.status_code}")
            return None
            
    except Exception as e:
        print(f"Polygon Aggs Fetch Failed ({contract_symbol}): {e}")
        return None

@app.route('/api/options/history/<path:ticker>')
def get_option_history(ticker):
    """
    Get historical bars for a specific option contract.
    Ticker can be passed as OCC symbol (e.g., O:SPY...) or clean (SPY...).
    """
    # Clean ticker if needed
    clean_ticker = ticker.replace("O:", "")
    formatted_ticker = f"O:{clean_ticker}" if not ticker.startswith("O:") else ticker
    
    # Use Aggregates (5-minute bars)
    bars = fetch_polygon_historical_aggs(formatted_ticker, timespan="minute", multiplier=5)
    
    if bars is None:
        # Fallback: Try without "O:" prefix
        if formatted_ticker.startswith("O:"):
             bars = fetch_polygon_historical_aggs(clean_ticker, timespan="minute", multiplier=5)
             
    if bars is None:
        return jsonify({"error": "Failed to fetch history"}), 500
        
    return jsonify({"results": bars})


# === POLYGON WEBSOCKET VWAP MANAGER ===
# Real-time trade streaming for per-contract VWAP charts

import asyncio
from collections import defaultdict
from datetime import datetime

# In-memory trade buffer for VWAP calculation
# Structure: { contract_symbol: [ {timestamp, price, size, is_call} ] }
VWAP_TRADE_BUFFER = defaultdict(list)
VWAP_BUCKET_SIZE_MINUTES = 5

# Active WebSocket subscriptions
ACTIVE_WS_SUBSCRIPTIONS = set()

# Firestore collection for lotto persistence
LOTTO_TRADES_COLLECTION = "lotto_trades"

def calculate_vwap_buckets(trades, bucket_minutes=5):
    """
    Aggregate trades into VWAP buckets.
    Returns: [{ time: "HH:MM", vwap: float, call_volume: int, put_volume: int }]
    """
    if not trades:
        return []
    
    tz_eastern = pytz.timezone('US/Eastern')
    buckets = defaultdict(lambda: {"price_volume": 0, "total_volume": 0, "call_volume": 0, "put_volume": 0})
    
    for trade in trades:
        ts = trade.get("timestamp")
        if not ts:
            continue
        
        # Parse timestamp
        try:
            if isinstance(ts, (int, float)):
                dt = datetime.fromtimestamp(ts / 1000 if ts > 1e10 else ts, tz=tz_eastern)
            else:
                dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(tz_eastern)
        except:
            continue
        
        # Calculate bucket key (round down to bucket_minutes)
        bucket_minute = (dt.minute // bucket_minutes) * bucket_minutes
        bucket_key = dt.replace(minute=bucket_minute, second=0, microsecond=0).strftime("%H:%M")
        
        price = trade.get("price", 0)
        size = trade.get("size", 0)
        is_call = trade.get("is_call", True)
        
        if price > 0 and size > 0:
            buckets[bucket_key]["price_volume"] += price * size
            buckets[bucket_key]["total_volume"] += size
            if is_call:
                buckets[bucket_key]["call_volume"] += size
            else:
                buckets[bucket_key]["put_volume"] += size
    
    # Calculate VWAP per bucket
    result = []
    for time_key in sorted(buckets.keys()):
        bucket = buckets[time_key]
        if bucket["total_volume"] > 0:
            vwap = bucket["price_volume"] / bucket["total_volume"]
            result.append({
                "time": time_key,
                "vwap": round(vwap, 4),
                "call_volume": bucket["call_volume"],
                "put_volume": bucket["put_volume"],
                "total_volume": bucket["total_volume"]
            })
    
    return result

def add_trade_to_buffer(contract_symbol, price, size, timestamp, is_call=True):
    """Add a trade to the in-memory buffer for VWAP calculation."""
    global VWAP_TRADE_BUFFER
    
    trade = {
        "timestamp": timestamp,
        "price": price,
        "size": size,
        "is_call": is_call
    }
    VWAP_TRADE_BUFFER[contract_symbol].append(trade)
    
    # Limit buffer size per contract (keep last 1000 trades)
    if len(VWAP_TRADE_BUFFER[contract_symbol]) > 1000:
        VWAP_TRADE_BUFFER[contract_symbol] = VWAP_TRADE_BUFFER[contract_symbol][-1000:]

def clear_trade_buffer(contract_symbol=None):
    """Clear trade buffer for a specific contract or all contracts."""
    global VWAP_TRADE_BUFFER
    if contract_symbol:
        VWAP_TRADE_BUFFER[contract_symbol] = []
    else:
        VWAP_TRADE_BUFFER.clear()

@app.route('/api/vwap/<path:contract>')
def get_vwap_data(contract):
    """
    Get VWAP buckets for a specific option contract.
    Returns aggregated 5-minute VWAP data + call/put volume bars.
    """
    # Clean contract symbol
    clean_contract = contract.replace("O:", "")
    formatted_contract = f"O:{clean_contract}" if not contract.startswith("O:") else contract
    
    # Get trades from buffer
    trades = VWAP_TRADE_BUFFER.get(formatted_contract, [])
    
    # If no buffered trades, try to fetch historical data from Polygon aggs
    if not trades:
        bars = fetch_polygon_historical_aggs(formatted_contract, timespan="minute", multiplier=5)
        if bars:
            # Convert agg bars to trade-like format for VWAP calculation
            is_call = "C" in formatted_contract.upper()
            trades = [
                {
                    "timestamp": bar.get("t"),
                    "price": bar.get("vw", bar.get("c", 0)),  # Use VWAP or close
                    "size": bar.get("v", 0),
                    "is_call": is_call
                }
                for bar in bars
            ]
    
    # Calculate VWAP buckets
    buckets = calculate_vwap_buckets(trades, VWAP_BUCKET_SIZE_MINUTES)
    
    return jsonify({
        "contract": formatted_contract,
        "bucket_size_minutes": VWAP_BUCKET_SIZE_MINUTES,
        "buckets": buckets,
        "trade_count": len(trades)
    })


# === POLYGON WEBSOCKET WHALE STREAMING ===
# Delayed (15-min) trade streaming for real-time whale detection
# Using official polygon-api-client for reliable WebSocket handling
from polygon import WebSocketClient
from polygon.websocket import Feed, Market
import ssl

# WebSocket state
POLYGON_WS_STATUS = {"connected": False, "error": None, "last_trade": None}
POLYGON_WS_TRADE_BUFFER = []  # Buffer for incoming trades before processing

def format_money_ws(val):
    """Format money for display."""
    if val >= 1_000_000: return f"${val/1_000_000:.1f}M"
    if val >= 1_000: return f"${val/1_000:.0f}k"
    return f"${val:.0f}"

def parse_occ_symbol_ws(symbol):
    """Parse OCC option symbol like O:SPY260117C00600000"""
    try:
        clean = symbol.replace("O:", "")
        i = 0
        while i < len(clean) and clean[i].isalpha():
            i += 1
        underlying = clean[:i]
        rest = clean[i:]
        date_str = rest[:6]
        put_call = rest[6]
        strike_raw = rest[7:]
        strike = float(strike_raw) / 1000
        year = 2000 + int(date_str[:2])
        month = int(date_str[2:4])
        day = int(date_str[4:6])
        expiry = f"{year}-{month:02d}-{day:02d}"
        return {"underlying": underlying, "expiry": expiry, "put_call": put_call, "strike": strike}
    except:
        return None

def fetch_polygon_trades_rest(ticker, limit=50):
    """
    Fetch recent trades for a specific option contract using Polygon REST API.
    Used for the Expanded View (REST Polling).
    """
    if not POLYGON_API_KEY:
        return []
        
    url = f"https://api.polygon.io/v3/trades/{ticker}"
    params = {
        "apiKey": POLYGON_API_KEY,
        "limit": limit,
        "sort": "timestamp",
        "order": "desc"
    }
    
    try:
        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code != 200:
            return []
            
        data = resp.json()
        return data.get("results", [])
    except Exception as e:
        print(f"REST Trade Fetch Error ({ticker}): {e}")
        return []

def refresh_single_whale_polygon(symbol):
    """
    Polls Polygon for unusual activity using REST API.
    Uses Aggregates endpoint (works after hours) + Trades endpoint.
    Populates CACHE["whales_rest"] for the Expanded View.
    """
    if not POLYGON_API_KEY:
        return

    try:
        from datetime import timedelta
        
        # 1. Get current price (use yfinance-based cache which works with gevent)
        current_price = get_cached_price(symbol)
        if not current_price:
            return
            
        # 2. Get Snapshot to find contracts with Greeks/OI data
        snapshot_data = fetch_unusual_options_polygon(symbol)
        snapshot_map = {}
        if snapshot_data and snapshot_data.get("results"):
            for r in snapshot_data.get("results", []):
                ticker = r.get("details", {}).get("ticker")
                if ticker:
                    snapshot_map[ticker] = r
        
        # 3. Use Aggregates endpoint to find contracts with volume TODAY
        # This works after market hours unlike snapshot's day.v
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Calculate strike range (±15% for broader coverage)
        strike_low = int(current_price * 0.85)
        strike_high = int(current_price * 1.15)
        
        # Get contracts from snapshot (they have the ticker format we need)
        url = f"https://api.polygon.io/v3/snapshot/options/{symbol}"
        params = {
            "apiKey": POLYGON_API_KEY,
            "limit": 250,
            "strike_price.gte": strike_low,
            "strike_price.lte": strike_high
        }
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code != 200:
            return
            
        contracts = resp.json().get("results", [])
        if not contracts:
            return
            
        # 4. Check Aggregates for each contract to find those with volume today
        active_contracts = []
        for contract in contracts[:50]:  # Limit to 50 to avoid too many API calls
            ticker = contract.get("details", {}).get("ticker")
            if not ticker:
                continue
                
            # Fetch daily aggregates for this contract
            agg_url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{today}/{today}"
            try:
                agg_resp = requests.get(agg_url, params={"apiKey": POLYGON_API_KEY}, timeout=5)
                if agg_resp.status_code == 200:
                    agg_data = agg_resp.json()
                    if agg_data.get("resultsCount", 0) > 0:
                        bar = agg_data["results"][0]
                        volume = bar.get("v", 0)
                        if volume >= 100:  # Minimum volume filter
                            contract["_agg_volume"] = volume
                            active_contracts.append(contract)
            except:
                continue
                
            # Rate limit - don't hammer the API
            time.sleep(0.1)
            
            # Stop early if we have enough active contracts
            if len(active_contracts) >= 10:
                break
        
        # Sort by volume and take top 5
        active_contracts.sort(key=lambda x: x.get("_agg_volume", 0), reverse=True)
        active_contracts = active_contracts[:5]
        
        new_whales = []
        
        # 5. Fetch Trades for Active Contracts
        for contract in active_contracts:
            ticker = contract.get("details", {}).get("ticker")
            strike = contract.get("details", {}).get("strike_price")
            contract_type = contract.get("details", {}).get("contract_type")
            expiry = contract.get("details", {}).get("expiration_date")
            oi = contract.get("open_interest", 0)
            
            trades = fetch_polygon_trades_rest(ticker)
            
            for t in trades:
                # Filter for Size/Premium
                size = t.get("size", 0)
                price = t.get("price", 0)
                premium = size * price * 100
                
                if premium < 25000:  # $25k Minimum
                    continue
                    
                # Get Greeks from snapshot if available
                snapshot_contract = snapshot_map.get(ticker, contract)
                delta = snapshot_contract.get("greeks", {}).get("delta", 0)
                
                # Build Whale Object
                whale = {
                    "ticker": ticker,
                    "baseSymbol": symbol,
                    "strikePrice": strike,
                    "putCall": "C" if contract_type == "call" else "P",
                    "expirationDate": expiry,
                    "price": price,
                    "size": size,
                    "premium": int(premium),
                    "timestamp": t.get("participant_timestamp") / 1e9,  # Nanoseconds to Seconds
                    "vol_oi": (contract.get("_agg_volume", size) / (oi or 1)),
                    "delta": delta,
                    "moneyness": "ITM" if (contract_type == "call" and current_price > strike) or (contract_type == "put" and current_price < strike) else "OTM",
                    "is_sweep": False,  # Hard to detect via REST without conditions map
                    "is_lotto": abs(delta) < 0.2,
                    "is_mega_whale": premium > 1000000
                }
                new_whales.append(whale)
                
        # 6. Update Cache (Deduplicate)
        current_rest_cache = CACHE["whales_rest"]["data"]
        existing_sigs = {f"{w['ticker']}_{w['timestamp']}_{w['size']}" for w in current_rest_cache}
        
        # Also track main dashboard cache for whale-grade additions
        main_cache = CACHE["whales"]["data"]
        main_sigs = {f"{w.get('symbol', w.get('ticker'))}_{w.get('timestamp')}_{w.get('volume', w.get('size'))}" for w in main_cache}
        
        added_count = 0
        main_added_count = 0
        
        for w in new_whales:
            sig = f"{w['ticker']}_{w['timestamp']}_{w['size']}"
            if sig not in existing_sigs:
                current_rest_cache.append(w)
                existing_sigs.add(sig)
                added_count += 1
            
            # Check if this trade meets MAIN DASHBOARD whale thresholds
            # Premium thresholds: $500k base, $6M for TSLA, $8M for SPY/QQQ
            premium = w.get('premium', 0)
            base_symbol = w.get('baseSymbol', '')
            
            if base_symbol in ['SPY', 'QQQ']:
                min_premium = 8_000_000
            elif base_symbol == 'TSLA':
                min_premium = 6_000_000
            else:
                min_premium = 500_000
            
            if premium >= min_premium:
                # Convert to main dashboard format if needed
                main_sig = f"{w.get('ticker')}_{w.get('timestamp')}_{w.get('size')}"
                if main_sig not in main_sigs:
                    # Create whale object in main dashboard format
                    main_whale = {
                        "baseSymbol": w.get('baseSymbol'),
                        "symbol": w.get('ticker'),
                        "strikePrice": w.get('strikePrice'),
                        "expirationDate": w.get('expirationDate'),
                        "putCall": w.get('putCall'),
                        "openInterest": int(w.get('size', 0) / (w.get('vol_oi', 1) or 1)),
                        "lastPrice": w.get('price'),
                        "tradeTime": datetime.fromtimestamp(w.get('timestamp', 0), tz=pytz.timezone('US/Eastern')).strftime("%H:%M:%S"),
                        "timestamp": w.get('timestamp'),
                        "vol_oi": w.get('vol_oi', 0),
                        "premium": f"${premium:,.0f}",
                        "notional_value": premium,
                        "volume": w.get('size'),
                        "moneyness": w.get('moneyness'),
                        "is_mega_whale": w.get('is_mega_whale', False),
                        "is_sweep": w.get('is_sweep', False),
                        "delta": w.get('delta', 0),
                        "is_lotto": w.get('is_lotto', False),
                        "iv": 0,
                        "source": "rest_snapshot",
                        "side": None,
                        "bid": 0,
                        "ask": 0
                    }
                    main_cache.append(main_whale)
                    main_sigs.add(main_sig)
                    main_added_count += 1
                
        # Keep cache size manageable (last 1000 items)
        current_rest_cache.sort(key=lambda x: x['timestamp'], reverse=True)
        CACHE["whales_rest"]["data"] = current_rest_cache[:1000]
        CACHE["whales_rest"]["timestamp"] = time.time()
        
        # Update main cache too (last 50 items for main dashboard)
        main_cache.sort(key=lambda x: x['timestamp'], reverse=True)
        CACHE["whales"]["data"] = main_cache[:50]
        CACHE["whales"]["timestamp"] = time.time()
        
        # Also update 30 DTE cache
        CACHE["whales_30dte"]["data"] = main_cache[:200]
        CACHE["whales_30dte"]["timestamp"] = time.time()
        
        if added_count > 0 or main_added_count > 0:
            print(f"🐳 REST: Added {added_count} to expanded, {main_added_count} to main dashboard for {symbol}")

    except Exception as e:
        print(f"REST Whale Scan Error ({symbol}): {e}")

def fetch_polygon_trades_rest(ticker, limit=50):
    """
    Fetch recent trades for a specific option contract using Polygon REST API.
    Used for the Expanded View (REST Polling).
    """
    if not POLYGON_API_KEY:
        return []
        
    url = f"https://api.polygon.io/v3/trades/{ticker}"
    params = {
        "apiKey": POLYGON_API_KEY,
        "limit": limit,
        "sort": "timestamp",
        "order": "desc"
    }
    
    try:
        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code != 200:
            return []
            
        data = resp.json()
        return data.get("results", [])
    except Exception as e:
        print(f"REST Trade Fetch Error ({ticker}): {e}")
        return []

def refresh_single_whale_polygon(symbol):
    """
    Polls Polygon for unusual activity using REST API (Snapshot + Trades).
    Populates CACHE["whales_rest"] for the Expanded View.
    """
    if not POLYGON_API_KEY:
        return

    try:
        # 1. Get Snapshot to find active contracts
        # Use existing logic but filter for high volume
        snapshot_data = fetch_unusual_options_polygon(symbol)
        if not snapshot_data or not snapshot_data.get("results"):
            return

        current_price = snapshot_data.get("_current_price", 0)
        results = snapshot_data.get("results", [])
        
        # Filter for active contracts (Volume > 500 OR High Vol/OI)
        active_contracts = []
        for r in results:
            day = r.get("day", {})
            volume = day.get("v", 0)
            oi = r.get("open_interest", 0)
            
            # Basic Noise Filter
            if volume < 100: 
                continue
                
            # Interesting Criteria
            if volume > 500 or (oi > 0 and volume > oi * 1.2):
                active_contracts.append(r)
                
        # Limit to top 5 most active to save API calls
        active_contracts.sort(key=lambda x: x.get("day", {}).get("v", 0), reverse=True)
        active_contracts = active_contracts[:5]
        
        new_whales = []
        
        # 2. Fetch Trades for Active Contracts
        for contract in active_contracts:
            ticker = contract.get("details", {}).get("ticker")
            strike = contract.get("details", {}).get("strike_price")
            contract_type = contract.get("details", {}).get("contract_type")
            expiry = contract.get("details", {}).get("expiration_date")
            
            trades = fetch_polygon_trades_rest(ticker)
            
            for t in trades:
                # Filter for Size/Premium
                size = t.get("size", 0)
                price = t.get("price", 0)
                premium = size * price * 100
                
                if premium < 25000: # $25k Minimum
                    continue
                    
                # Build Whale Object
                whale = {
                    "ticker": ticker,
                    "baseSymbol": symbol,
                    "strikePrice": strike,
                    "putCall": "C" if contract_type == "call" else "P",
                    "expirationDate": expiry,
                    "price": price,
                    "size": size,
                    "premium": int(premium),
                    "timestamp": t.get("participant_timestamp") / 1e9, # Nanoseconds to Seconds
                    "vol_oi": size / (contract.get("open_interest", 1) or 1), # Approx
                    "delta": contract.get("greeks", {}).get("delta", 0),
                    "moneyness": "ITM" if (contract_type == "call" and current_price > strike) or (contract_type == "put" and current_price < strike) else "OTM",
                    "is_sweep": False, # Hard to detect via REST without conditions map
                    "is_lotto": abs(contract.get("greeks", {}).get("delta", 0)) < 0.2,
                    "is_mega_whale": premium > 1000000
                }
                new_whales.append(whale)
                
        # 3. Update Cache (Deduplicate)
        # We use a composite key to avoid duplicates
        current_rest_cache = CACHE["whales_rest"]["data"]
        existing_sigs = {f"{w['ticker']}_{w['timestamp']}_{w['size']}" for w in current_rest_cache}
        
        added_count = 0
        for w in new_whales:
            sig = f"{w['ticker']}_{w['timestamp']}_{w['size']}"
            if sig not in existing_sigs:
                current_rest_cache.append(w)
                existing_sigs.add(sig)
                added_count += 1
                
        # Keep cache size manageable (last 1000 items)
        current_rest_cache.sort(key=lambda x: x['timestamp'], reverse=True)
        CACHE["whales_rest"]["data"] = current_rest_cache[:1000]
        CACHE["whales_rest"]["timestamp"] = time.time()
        
        # 4. Update Main Dashboard Cache (High Value Only)
        # Filter for significant whales to show on the main HUD (Unusual Whales Feed)
        main_cache = CACHE["whales"]["data"]
        main_sigs = {f"{w.get('symbol', w.get('ticker'))}_{w.get('timestamp')}_{w.get('volume', w.get('size'))}" for w in main_cache}
        main_added_count = 0
        
        for w in new_whales:
            # Main HUD Thresholds (Stricter than Expanded Flow)
            premium = w.get('premium', 0)
            base_symbol = w.get('baseSymbol', '')
            
            if base_symbol in ['SPY', 'QQQ']:
                min_premium = 8_000_000
            elif base_symbol == 'TSLA':
                min_premium = 6_000_000
            else:
                min_premium = 500_000
            
            if premium >= min_premium:
                # Convert to main dashboard format
                main_sig = f"{w.get('ticker')}_{w.get('timestamp')}_{w.get('size')}"
                if main_sig not in main_sigs:
                    main_whale = {
                        "baseSymbol": w.get('baseSymbol'),
                        "symbol": w.get('ticker'),
                        "strikePrice": w.get('strikePrice'),
                        "expirationDate": w.get('expirationDate'),
                        "putCall": w.get('putCall'),
                        "openInterest": int(w.get('size', 0) / (w.get('vol_oi', 1) or 1)),
                        "lastPrice": w.get('price'),
                        "tradeTime": datetime.fromtimestamp(w.get('timestamp', 0), tz=pytz.timezone('US/Eastern')).strftime("%H:%M:%S"),
                        "timestamp": w.get('timestamp'),
                        "vol_oi": w.get('vol_oi', 0),
                        "premium": f"${premium:,.0f}",
                        "notional_value": premium,
                        "volume": w.get('size'),
                        "moneyness": w.get('moneyness'),
                        "is_mega_whale": w.get('is_mega_whale', False),
                        "is_sweep": w.get('is_sweep', False),
                        "delta": w.get('delta', 0),
                        "is_lotto": w.get('is_lotto', False),
                        "iv": 0,
                        "source": "rest_snapshot",
                        "side": None,
                        "bid": 0,
                        "ask": 0
                    }
                    main_cache.append(main_whale)
                    main_sigs.add(main_sig)
                    main_added_count += 1
        
        # Keep main cache size manageable (last 50 items)
        main_cache.sort(key=lambda x: x['timestamp'], reverse=True)
        CACHE["whales"]["data"] = main_cache[:50]
        CACHE["whales"]["timestamp"] = time.time()
        
        if main_added_count > 0:
            print(f"🐳 Main Feed: Added {main_added_count} high-value whales for {symbol}")
        
        if added_count > 0:
            print(f"🐳 REST: Added {added_count} new whales for {symbol}")

    except Exception as e:
        print(f"REST Whale Scan Error ({symbol}): {e}")

def process_ws_trade(trade_data):
    """
    Process a single trade from the WebSocket stream.
    Apply whale filters and add to cache if qualifying.
    """
    global CACHE, WHALE_HISTORY
    
    try:
        symbol = trade_data.get("sym", "")  # O:TSLA260117C00400000
        price = float(trade_data.get("p", 0))  # Trade price
        size = int(trade_data.get("s", 0))  # Trade size (contracts)
        timestamp_ns = trade_data.get("t", 0)  # SIP timestamp in nanoseconds
        conditions = trade_data.get("c", [])  # Trade conditions
        
        if not symbol or price <= 0 or size <= 0:
            return None
        
        # Parse the OCC symbol
        parsed = parse_occ_symbol_ws(symbol)
        if not parsed:
            return None
        
        underlying = parsed["underlying"]
        
        # Check if in watchlist
        if underlying not in WHALE_WATCHLIST:
            return None
        
        # Calculate premium
        notional = size * price * 100
        
        # Check threshold (same as snapshot logic)
        if underlying in ['SPY', 'QQQ']:
            min_whale_val = 8_000_000
        elif underlying == 'TSLA':
            min_whale_val = 6_000_000
        else:
            min_whale_val = 500_000
        
        # Quick filter - skip small trades
        if notional < min_whale_val:
            return None
        
        # Volume filter (single trade must be significant)
        if size < 100:  # At least 100 contracts for a whale trade
            return None
        
        # Convert timestamp
        tz_eastern = pytz.timezone('US/Eastern')
        if timestamp_ns > 1e15:  # Nanoseconds
            trade_dt = datetime.fromtimestamp(timestamp_ns / 1e9, tz=tz_eastern)
        else:
            trade_dt = datetime.fromtimestamp(timestamp_ns, tz=tz_eastern)
        
        trade_time_display = trade_dt.strftime("%H:%M:%S")
        timestamp_val = trade_dt.timestamp()
        
        # Deduplication
        trade_id = f"{symbol}_{timestamp_ns}_{size}"
        if trade_id in WHALE_HISTORY:
            return None
        WHALE_HISTORY[trade_id] = timestamp_val
        
        # Fetch Greeks from snapshot API (enrichment)
        poly_details = get_polygon_contract_details(symbol)
        open_interest = poly_details.get("open_interest", 0)
        delta_val = poly_details.get("delta", 0)
        iv_val = poly_details.get("iv", 0)
        
        # Vol/OI check (use size as proxy for "volume" in this single trade)
        # For streaming, we relax this since we see individual trades
        vol_oi_ratio = size / open_interest if open_interest > 0 else 999
        
        # Moneyness
        underlying_price = get_cached_price(underlying) or 0
        if underlying_price > 0:
            price_diff_pct = abs(underlying_price - parsed["strike"]) / underlying_price
            if price_diff_pct <= 0.005:
                moneyness = "ATM"
            elif parsed["put_call"] == "C":
                moneyness = "ITM" if underlying_price > parsed["strike"] else "OTM"
            else:
                moneyness = "ITM" if underlying_price < parsed["strike"] else "OTM"
        else:
            moneyness = "ATM"
        
        # Determine side from conditions (if available)
        # Condition codes: https://polygon.io/docs/options/get_v3_trades__optionsticker
        is_sweep = 'I' in conditions  # Intermarket Sweep
        
        # Mega whale check
        mega_threshold = MEGA_WHALE_THRESHOLD_TSLA if underlying == 'TSLA' else MEGA_WHALE_THRESHOLD
        is_mega = notional >= mega_threshold
        
        whale_data = {
            "baseSymbol": underlying,
            "symbol": symbol,
            "strikePrice": parsed["strike"],
            "expirationDate": parsed["expiry"],
            "putCall": parsed["put_call"],
            "openInterest": open_interest,
            "lastPrice": price,
            "tradeTime": trade_time_display,
            "timestamp": timestamp_val,
            "vol_oi": vol_oi_ratio,
            "premium": format_money_ws(notional),
            "notional_value": notional,
            "volume": size,
            "moneyness": moneyness,
            "is_mega_whale": is_mega,
            "is_sweep": is_sweep,
            "delta": delta_val,
            "is_lotto": abs(delta_val) < 0.20,
            "iv": iv_val,
            "source": "polygon_ws",
            "side": None,  # WS doesn't provide side easily
            "bid": 0,
            "ask": 0
        }
        
        print(f"🐳 WS WHALE: {underlying} {parsed['put_call']} ${parsed['strike']} | {format_money_ws(notional)} | {size} contracts")
        
        return whale_data
        
    except Exception as e:
        print(f"⚠️ WS Trade Processing Error: {e}")
        return None

def on_polygon_ws_message(ws, message):
    """Handle incoming WebSocket messages."""
    global POLYGON_WS_STATUS, CACHE
    
    try:
        data = json.loads(message)
        
        if isinstance(data, list):
            for item in data:
                ev = item.get("ev", "")
                
                if ev == "status":
                    status = item.get("status", "")
                    msg = item.get("message", "")
                    
                    if status == "connected":
                        print("✅ Polygon WS: Connected")
                        POLYGON_WS_STATUS["connected"] = True
                        POLYGON_WS_STATUS["error"] = None
                    elif status == "auth_success":
                        print("✅ Polygon WS: Authenticated")
                        # Subscribe to all watchlist symbols
                        symbols = ",".join([f"T.O:{sym}*" for sym in WHALE_WATCHLIST])
                        sub_msg = json.dumps({"action": "subscribe", "params": symbols})
                        ws.send(sub_msg)
                        print(f"📡 Polygon WS: Subscribed to {len(WHALE_WATCHLIST)} symbols")
                    elif status == "error":
                        print(f"⚠️ Polygon WS Error: {msg}")
                        POLYGON_WS_STATUS["error"] = msg
                    elif status == "success":
                        print(f"✅ Polygon WS: {msg}")
                
                elif ev == "T":  # Trade event
                    whale = process_ws_trade(item)
                    if whale:
                        # Add to cache
                        with CACHE_LOCK:
                            current_data = CACHE["whales"]["data"]
                            updated_data = [whale] + current_data  # Prepend new trade
                            updated_data.sort(key=lambda x: x['timestamp'], reverse=True)
                            CACHE["whales"]["data"] = updated_data[:50]
                            CACHE["whales"]["timestamp"] = time.time()
                            
                            # Also update 30 DTE cache
                            current_30dte = CACHE["whales_30dte"]["data"]
                            updated_30dte = [whale] + current_30dte
                            updated_30dte.sort(key=lambda x: x['timestamp'], reverse=True)
                            CACHE["whales_30dte"]["data"] = updated_30dte[:200]
                            CACHE["whales_30dte"]["timestamp"] = time.time()
                        
                        POLYGON_WS_STATUS["last_trade"] = time.time()
                        
    except Exception as e:
        print(f"⚠️ Polygon WS Message Error: {e}")

def on_polygon_ws_error(ws, error):
    """Handle WebSocket errors."""
    global POLYGON_WS_STATUS
    print(f"❌ Polygon WS Error: {error}")
    POLYGON_WS_STATUS["error"] = str(error)
    POLYGON_WS_STATUS["connected"] = False

def on_polygon_ws_close(ws, close_status_code, close_msg):
    """Handle WebSocket close."""
    global POLYGON_WS_STATUS
    print(f"🔌 Polygon WS Closed: {close_status_code} - {close_msg}")
    POLYGON_WS_STATUS["connected"] = False

def on_polygon_ws_open(ws):
    """Handle WebSocket open - authenticate."""
    print("🔗 Polygon WS: Connection opened, authenticating...")
    auth_msg = json.dumps({"action": "auth", "params": POLYGON_API_KEY})
    ws.send(auth_msg)

def handle_polygon_msg(msgs):
    """
    Callback for polygon-api-client WebSocket messages.
    Processes incoming trade messages and updates the cache.
    """
    global POLYGON_WS_STATUS, CACHE
    
    # Debug: Log message count
    if msgs:
        print(f"📨 WS Received {len(msgs)} messages")
    
    for msg in msgs:
        try:
            # The polygon client provides parsed message objects (EquityTrade)
            # Attributes: event_type, symbol, price, size, timestamp, conditions, exchange, etc.
            if hasattr(msg, 'event_type') and msg.event_type == 'T':  # Trade event
                trade_data = {
                    "ev": "T",
                    "sym": msg.symbol,
                    "p": msg.price,
                    "s": msg.size,
                    "t": msg.timestamp,  # Unix nanoseconds
                    "c": msg.conditions if hasattr(msg, 'conditions') and msg.conditions else []
                }
                
                whale = process_ws_trade(trade_data)
                if whale:
                    with CACHE_LOCK:
                        current_data = CACHE["whales"]["data"]
                        updated_data = [whale] + current_data
                        updated_data.sort(key=lambda x: x['timestamp'], reverse=True)
                        CACHE["whales"]["data"] = updated_data[:50]
                        CACHE["whales"]["timestamp"] = time.time()
                        
                        current_30dte = CACHE["whales_30dte"]["data"]
                        updated_30dte = [whale] + current_30dte
                        updated_30dte.sort(key=lambda x: x['timestamp'], reverse=True)
                        CACHE["whales_30dte"]["data"] = updated_30dte[:200]
                        CACHE["whales_30dte"]["timestamp"] = time.time()
                    
                    POLYGON_WS_STATUS["last_trade"] = time.time()
                    
        except Exception as e:
            print(f"⚠️ Polygon Msg Processing Error: {e}")

def start_polygon_ws_thread():
    """
    Start the Polygon WebSocket using the official polygon-api-client.
    This handles connection, authentication, and SSL properly.
    """
    global POLYGON_WS_STATUS
    
    # DISABLED: WebSocket causes SSL conflicts with other network calls
    if DISABLE_WEBSOCKET:
        print("🔌 Polygon WebSocket DISABLED - using REST polling instead")
        POLYGON_WS_STATUS["error"] = "Disabled (using REST)"
        return
    
    if not POLYGON_API_KEY:
        print("⚠️ Polygon WS: No API key configured")
        POLYGON_WS_STATUS["error"] = "No API key"
        return

    
    def run_ws():
        while True:
            try:
                print("🚀 Starting Polygon WebSocket (official client, delayed)...")
                
                # Build subscription list for all watchlist symbols
                # Format: T.O:SYMBOL* for options trades
                subscriptions = [f"T.O:{sym}*" for sym in WHALE_WATCHLIST]
                print(f"📡 Subscribing to {len(WHALE_WATCHLIST)} symbols: {subscriptions[:3]}...")
                
                # Create client with delayed feed (free tier)
                client = WebSocketClient(
                    api_key=POLYGON_API_KEY,
                    feed=Feed.Delayed,
                    market=Market.Options,
                    subscriptions=subscriptions,
                    verbose=True  # Log connection status
                )
                
                # Mark as connected
                POLYGON_WS_STATUS["connected"] = True
                POLYGON_WS_STATUS["error"] = None
                print("✅ Polygon WS: Connected and subscribed")
                
                # Run synchronously (blocks in this thread)
                # The client handles auth, reconnects, and SSL properly
                client.run(handle_polygon_msg)
                
            except Exception as e:
                print(f"⚠️ Polygon WS Thread Error: {e}")
                POLYGON_WS_STATUS["error"] = str(e)
                POLYGON_WS_STATUS["connected"] = False
            
            # Wait before reconnecting
            print("⏳ Polygon WS: Reconnecting in 10s...")
            time.sleep(10)
    
    thread = threading.Thread(target=run_ws, daemon=True)
    thread.start()
    print("🧵 Polygon WS Thread Started")

# API endpoint to check WS status
@app.route('/api/ws/status')
def get_ws_status():
    """Return WebSocket connection status."""
    return jsonify(POLYGON_WS_STATUS)


def get_polygon_contract_details(contract_symbol):
    """
    Fetch Open Interest and Greeks (Delta, IV) for a single option contract from Polygon.
    Used to enrich Alpaca whale data.
    """
    if not POLYGON_API_KEY:
        return {"open_interest": 0, "delta": 0, "iv": 0}
        
    try:
        # Parse OCC symbol to get underlying and format for Polygon
        # Alpaca: SPY251219C00500000 -> Polygon: O:SPY251219C00500000
        # Polygon actually accepts the OCC symbol directly in the v3 endpoint
        
        # v3 Options Contract Endpoint
        # https://api.polygon.io/v3/snapshot/options/{underlying}/{contract}
        
        # Extract underlying from OCC (e.g. SPY from SPY25...)
        # Simple parsing: assume letters at start
        clean_symbol = contract_symbol.replace("O:", "")
        underlying = ""
        for char in clean_symbol:
            if char.isalpha():
                underlying += char
            else:
                break
                
        url = f"https://api.polygon.io/v3/snapshot/options/{underlying}/{contract_symbol}"
        params = {"apiKey": POLYGON_API_KEY}
        
        resp = requests.get(url, params=params, timeout=3)
        
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", {})
            greeks = results.get("greeks", {})
            
            return {
                "open_interest": int(results.get("open_interest", 0) or 0),
                "delta": float(greeks.get("delta", 0) or 0),
                "iv": float(results.get("implied_volatility", 0) or 0)
            }
            
    except Exception as e:
        print(f"⚠️ Polygon Details Fetch Error ({contract_symbol}): {e}")
    
    return {"open_interest": 0, "delta": 0, "iv": 0}


def fetch_options_chain_marketdata(symbol, expiry=None, dte=None, strike_limit=None, min_volume=None):
    """
    Fetch options chain from MarketData.app API.
    
    Args:
        symbol: Underlying ticker
        expiry: Specific expiration date
        dte: Days to expiration filter (e.g., 7 for weekly)
        strike_limit: Max number of strikes to return (centered around ATM)
        min_volume: Minimum volume filter
    
    Returns parsed data or None if failed.
    """
    global MARKETDATA_LAST_REQUEST
    
    if not MARKETDATA_TOKEN:
        return None
    
    # Rate limit: wait at least 250ms between requests
    elapsed = time.time() - MARKETDATA_LAST_REQUEST
    if elapsed < MARKETDATA_MIN_INTERVAL:
        time.sleep(MARKETDATA_MIN_INTERVAL - elapsed)
        
    try:
        url = f"https://api.marketdata.app/v1/options/chain/{symbol}/"
        headers = {"Authorization": f"Bearer {MARKETDATA_TOKEN}"}
        params = {}
        
        # Apply filters
        if expiry:
            params["expiration"] = expiry
        if dte:
            params["dte"] = dte
        if strike_limit:
            params["strikeLimit"] = strike_limit
        if min_volume:
            params["minVolume"] = min_volume
            
        MARKETDATA_LAST_REQUEST = time.time()
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        
        # Accept any 2xx status (MarketData.app returns 203 for cached/trial data)
        if 200 <= resp.status_code < 300:
            data = resp.json()
            if data.get("s") == "ok":
                return data
        
        # Rate limited - return None silently to fall back to yfinance
        if resp.status_code == 429:
            print(f"MarketData.app Rate Limit ({symbol}) - falling back")
            return None
        
        print(f"MarketData.app Error ({symbol}): Status {resp.status_code}")
        return None
        
    except Exception as e:
        print(f"MarketData.app Fetch Failed ({symbol}): {e}")
        return None

# Track last reported volume to simulate "stream" feel
WHALE_HISTORY = {} 
VOLUME_THRESHOLD = 100 # Only show update if volume increases by this much

def refresh_single_whale(symbol):
    """
    Fetch unusual options activity for a single ticker.
    Uses Polygon.io exclusively for whale detection.
    """
    if not POLYGON_API_KEY:
        print("Whale scan requires POLYGON_API_KEY - skipping")
        return
    
    refresh_single_whale_polygon(symbol)


def refresh_heatmap_logic():
    global CACHE

    
    # Tickers mapped to their "Size" category and "Sector" for filtering
    HEATMAP_TICKERS = {
        # Indices
        "SPY": {"size": "mega", "sector": "INDICES"},
        "QQQ": {"size": "mega", "sector": "INDICES"},
        "IWM": {"size": "large", "sector": "INDICES"},
        "DIA": {"size": "large", "sector": "INDICES"},
        
        # Mag 7 (Tech)
        "NVDA": {"size": "mega", "sector": "TECH"},
        "AAPL": {"size": "mega", "sector": "TECH"},
        "MSFT": {"size": "mega", "sector": "TECH"},
        "GOOGL": {"size": "large", "sector": "TECH"},
        "GOOG": {"size": "large", "sector": "TECH"},
        "AMZN": {"size": "large", "sector": "CONSUMER"},
        "META": {"size": "large", "sector": "TECH"},
        "TSLA": {"size": "large", "sector": "CONSUMER"},
        
        # Others
        "AMD": {"size": "medium", "sector": "TECH"},
        "NFLX": {"size": "medium", "sector": "CONSUMER"},
        "AVGO": {"size": "medium", "sector": "TECH"},
        "PLTR": {"size": "small", "sector": "TECH"},
        "COIN": {"size": "small", "sector": "CRYPTO"},
        "MSTR": {"size": "small", "sector": "CRYPTO"},
        "RIOT": {"size": "small", "sector": "CRYPTO"},
        "BTC-USD": {"size": "mega", "sector": "CRYPTO"}
    }
    
    try:
        heatmap_data = []
        
        # Wrap yf.Tickers to prevent hanging
        def fetch_tickers():
            return yf.Tickers(" ".join(HEATMAP_TICKERS.keys()))
        
        tickers_obj = with_timeout(fetch_tickers, timeout_seconds=10)
        if not tickers_obj:
            print("⏰ Heatmap tickers fetch timed out")
            return
        
        for symbol, meta in HEATMAP_TICKERS.items():
            try:
                t = tickers_obj.tickers[symbol]
                
                # Try to get extended hours data from .info (slower but richer)
                try:
                    # Use fast_info primarily for speed
                    price = t.fast_info.last_price
                    prev_close = t.fast_info.previous_close
                except:
                    continue

                if price and prev_close:
                    change = ((price - prev_close) / prev_close) * 100
                    heatmap_data.append({
                        "symbol": symbol,
                        "change": round(change, 2),
                        "price": round(price, 2),
                        "size": meta["size"],
                        "sector": meta["sector"]
                    })
            except Exception as e:
                continue
            
            # Small jitter to be polite
            time.sleep(random.uniform(0.1, 0.3))
        
        # Update Cache
        if heatmap_data:
            CACHE["heatmap"]["data"] = heatmap_data
            CACHE["heatmap"]["timestamp"] = time.time()
            SERVICE_STATUS["HEATMAP"] = {"status": "ONLINE", "last_updated": time.time()}

            
    except Exception as e:
        print(f"Heatmap Update Failed: {e}")
        SERVICE_STATUS["HEATMAP"] = {"status": "OFFLINE", "last_updated": time.time()}

# --- FLASK ROUTES ---

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

# --- STRIPE SUBSCRIPTION ENDPOINTS ---

@app.route('/api/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        data = request.get_json()
        user_email = data.get('email')
        
        checkout_session = stripe.checkout.Session.create(
            customer_email=user_email,
            payment_method_types=['card'],
            line_items=[{
                'price': STRIPE_PRICE_ID,
                'quantity': 1,
            }],
            mode='subscription',
            success_url='https://pigmentos.onrender.com/index.html?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='https://pigmentos.onrender.com/upgrade.html',
        )
        
        return jsonify({'sessionId': checkout_session.id})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/subscription-status', methods=['POST'])
@limiter.limit("30 per minute")
def subscription_status():
    """Check if user has active subscription or valid trial - SERVER-SIDE VERIFIED"""
    try:
        # 1. VERIFY FIREBASE TOKEN (don't trust client-sent email)
        auth_header = request.headers.get('Authorization', '')
        
        # BYPASS: If Firestore is not initialized (Local Dev / Missing Creds), trust the client
        # This prevents "Trial Ended" lockout when running locally without Admin SDK
        if not firestore_db:
            print("⚠️ Firestore not initialized - Bypassing token verification (Dev Mode)")
            # We can't verify the token, so we assume the client is honest for trial check
            # In a real paid scenario, we'd check Stripe, which doesn't need Firebase Admin
            pass
        elif not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
        else:
            id_token = auth_header.split('Bearer ')[1]
            try:
                decoded_token = firebase_auth.verify_id_token(id_token)
                user_email = decoded_token.get('email')
                user_uid = decoded_token.get('uid')
            except Exception as auth_error:
                print(f"Firebase token verification failed: {auth_error}")
                return jsonify({'error': 'Invalid authentication token'}), 401
            
            if not user_email:
                return jsonify({'error': 'No email in token'}), 401
        
        # Track login count in Firestore
        login_count = 1
        if firestore_db and user_uid:
            try:
                user_ref = firestore_db.collection('users').document(user_uid)
                user_ref.set({'login_count': firestore.Increment(1)}, merge=True)
                user_doc = user_ref.get()
                if user_doc.exists:
                    login_count = user_doc.to_dict().get('login_count', 1)
            except Exception as e:
                print(f"Login count update failed: {e}")
        
        # If we bypassed, we need to get email/uid from request body as fallback
        if not firestore_db:
            data = request.get_json() or {}
            user_email = data.get('email')
            if user_email:
                user_uid = "dev_user_" + user_email
            
            # If no email provided in body, we can't check Stripe, so we default to Trialing
            if not user_email:
                 return jsonify({
                    'status': 'trialing',
                    'days_remaining': TRIAL_DAYS,
                    'has_access': True
                })
            
        # 3. CHECK VIP/ADMIN LIST (Bypass all checks)
        ADMIN_EMAILS = ['sam.juarez092678@gmail.com', 'jaxnailedit@gmail.com', 'Gtmichael9218@gmail.com']
        if user_email in ADMIN_EMAILS:
            return jsonify({
                'status': 'active',
                'has_access': True,
                'is_vip': True
            })
            
        # 3. CHECK VIP/ADMIN LIST (Bypass all checks)
        ADMIN_EMAILS = ['sam.juarez092678@gmail.com', 'jaxnailedit@gmail.com', 'gtmichael9218@gmail.com']
        
        if user_email.lower().strip() in [e.lower() for e in ADMIN_EMAILS]:
            return jsonify({
                'status': 'active',
                'has_access': True,
                'is_vip': True
            })
        
        # 2. FIRESTORE IS SOURCE OF TRUTH FOR TRIAL COUNTDOWN
        # We use Firestore for the countdown to avoid Stripe latency/sync issues
        days_remaining = TRIAL_DAYS
        is_premium = False
        
        if firestore_db and user_uid:
            try:
                user_ref = firestore_db.collection('users').document(user_uid)
                user_doc = user_ref.get()
                
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    trial_start = user_data.get('trialStartDate')
                    
                    if trial_start:
                        # Calculate days remaining
                        # trial_start is a Firestore timestamp (datetime object)
                        if isinstance(trial_start, datetime):
                            start_ts = trial_start.timestamp()
                        else:
                            # Fallback if it's already a timestamp or other format
                            start_ts = trial_start
                            
                        now_ts = datetime.now().timestamp()
                        elapsed_days = int((now_ts - start_ts) / 86400)
                        days_remaining = max(0, TRIAL_DAYS - elapsed_days)
                    else:
                        # Initialize trialStartDate if missing
                        user_ref.update({'trialStartDate': firestore.SERVER_TIMESTAMP})
                        print(f"Initialized missing trialStartDate for {user_email}")
                else:
                    # Create document if it doesn't exist (should be handled by login.html but safe fallback)
                    user_ref.set({
                        'email': user_email,
                        'trialStartDate': firestore.SERVER_TIMESTAMP,
                        'subscriptionStatus': 'trialing',
                        'login_count': 1
                    })
                    print(f"Created missing user document for {user_email}")
            except Exception as e:
                print(f"Firestore trial check failed: {e}")

        # 3. STRIPE IS SOURCE OF TRUTH FOR PAYMENTS
        try:
            customers = stripe.Customer.list(email=user_email, limit=1)
            if customers.data:
                customer = customers.data[0]
                subscriptions = stripe.Subscription.list(customer=customer.id, limit=1, status='all')
                
                if subscriptions.data:
                    sub = subscriptions.data[0]
                    print(f"Stripe Status for {user_email}: {sub.status}")
                    
                    if sub.status in ['active', 'trialing']:
                        # If Stripe says active, they are premium
                        if sub.status == 'active':
                            is_premium = True
                        
                        # If Stripe has a more accurate trial_end, we could use it, 
                        # but per requirements we stick to Firestore for the countdown.
                        return jsonify({
                            'status': sub.status,
                            'days_remaining': days_remaining,
                            'has_access': True,
                            'login_count': login_count,
                            'is_premium': is_premium
                        })
                    else:
                        # Hard Lockout for expired/bad status
                        return jsonify({
                            'status': sub.status,
                            'has_access': False
                        })
                else:
                    print("Customer exists but no subscription found -> Auto-Migrating")
            else:
                print("No Stripe customer found -> Auto-Migrating")
                
            # AUTO-MIGRATION LOGIC (Background)
            # If we are here, the user has NO active subscription in Stripe.
            # We return the Firestore-calculated trial status immediately.
            
            def create_stripe_subscription_async(email, uid, cust_data):
                """Background task to create Stripe customer and subscription"""
                try:
                    if cust_data:
                        customer = cust_data
                    else:
                        customer = stripe.Customer.create(
                            email=email,
                            metadata={'firebase_uid': uid}
                        )
                    
                    stripe.Subscription.create(
                        customer=customer.id,
                        items=[{'price': STRIPE_PRICE_ID}],
                        trial_period_days=TRIAL_DAYS,
                        payment_behavior='default_incomplete',
                        metadata={'firebase_uid': uid, 'source': 'auto_migration'}
                    )
                    
                    if firestore_db:
                        firestore_db.collection('users').document(uid).update({
                            'stripeCustomerId': customer.id,
                            'subscriptionStatus': 'trialing'
                        })
                except Exception as e:
                    print(f"Background Stripe migration error: {e}")
            
            existing_customer = customers.data[0] if customers.data else None
            threading.Thread(
                target=create_stripe_subscription_async,
                args=(user_email, user_uid, existing_customer),
                daemon=True
            ).start()
            
            return jsonify({
                'status': 'trialing',
                'days_remaining': days_remaining,
                'has_access': True,
                'login_count': login_count,
                'is_premium': False
            })

        except Exception as stripe_e:
            print(f"Stripe Auto-Migration Error: {stripe_e}")
            # Fail Open if Stripe is down
            return jsonify({
                'status': 'trialing',
                'days_remaining': 1,
                'has_access': True,
                'error': str(stripe_e)
            })
        
    except Exception as e:
        print(f"Subscription status error: {e}")
        # Fail OPEN on general error to prevent lockout
        return jsonify({
            'status': 'trialing',
            'days_remaining': 1,
            'has_access': True,
            'error': str(e)
        })

@app.route('/api/start-trial', methods=['POST'])
@limiter.limit("5 per minute")
def start_trial():
    """Initialize Stripe Trial for New User"""
    try:
        # 1. VERIFY FIREBASE TOKEN
        auth_header = request.headers.get('Authorization', '')
        
        # Dev Bypass
        if not firestore_db:
            print("⚠️ Dev Mode: Bypassing token verification for start-trial")
            data = request.get_json()
            user_email = data.get('email')
            user_uid = "dev_user_" + user_email
        elif not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing Authorization header'}), 401
        else:
            id_token = auth_header.split('Bearer ')[1]
            decoded_token = firebase_auth.verify_id_token(id_token)
            user_email = decoded_token.get('email')
            user_uid = decoded_token.get('uid')

        if not user_email:
            return jsonify({'error': 'No email found'}), 400

        print(f"Starting trial for: {user_email}")

        # 2. CREATE/GET STRIPE CUSTOMER
        customers = stripe.Customer.list(email=user_email, limit=1)
        if customers.data:
            customer = customers.data[0]
            print(f"Found existing customer: {customer.id}")
        else:
            customer = stripe.Customer.create(
                email=user_email,
                metadata={'firebase_uid': user_uid}
            )
            print(f"Created new customer: {customer.id}")

        # 3. CHECK FOR EXISTING SUBSCRIPTION
        subscriptions = stripe.Subscription.list(
            customer=customer.id,
            limit=1,
            status='all' # Check everything
        )
        
        active_sub = None
        for sub in subscriptions.data:
            if sub.status in ['active', 'trialing']:
                active_sub = sub
                break
        
        if active_sub:
            print(f"User already has active subscription: {active_sub.id}")
            # Update Firestore just in case
            if firestore_db:
                firestore_db.collection('users').document(user_uid).set({
                    'stripeCustomerId': customer.id,
                    'stripeSubscriptionId': active_sub.id,
                    'subscriptionStatus': active_sub.status,
                    'email': user_email
                }, merge=True)
            
            return jsonify({'status': 'success', 'message': 'Subscription already exists'})

        # 4. CREATE TRIAL SUBSCRIPTION
        # 14 Days Free Trial
        try:
            new_sub = stripe.Subscription.create(
                customer=customer.id,
                items=[{'price': STRIPE_PRICE_ID}],
                trial_period_days=TRIAL_DAYS,
                payment_behavior='default_incomplete',
                metadata={'firebase_uid': user_uid}
            )
            print(f"Created new trial subscription: {new_sub.id}")
            
            # 5. SAVE TO FIRESTORE
            if firestore_db:
                firestore_db.collection('users').document(user_uid).set({
                    'stripeCustomerId': customer.id,
                    'stripeSubscriptionId': new_sub.id,
                    'subscriptionStatus': new_sub.status,
                    'trialStartDate': firestore.SERVER_TIMESTAMP, # Keep for legacy/backup
                    'email': user_email
                }, merge=True)
                
            return jsonify({'status': 'success', 'subscription_id': new_sub.id})
            
        except Exception as stripe_error:
            print(f"Stripe Error: {stripe_error}")
            return jsonify({'error': str(stripe_error)}), 500

    except Exception as e:
        print(f"Start Trial Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/create-portal-session', methods=['POST'])
@limiter.limit("5 per minute")
def create_portal_session():
    """Create a Stripe Customer Portal session for subscription management"""
    try:
        # 1. VERIFY FIREBASE TOKEN
        auth_header = request.headers.get('Authorization', '')
        
        # Dev Bypass
        if not firestore_db:
            print("⚠️ Dev Mode: Bypassing token verification for portal session")
            data = request.get_json()
            user_email = data.get('email')
        elif not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing Authorization header'}), 401
        else:
            id_token = auth_header.split('Bearer ')[1]
            try:
                decoded_token = firebase_auth.verify_id_token(id_token)
                user_email = decoded_token.get('email')
                user_uid = decoded_token.get('uid')
            except Exception as auth_error:
                print(f"Token verification failed: {auth_error}")
                return jsonify({'error': 'Invalid token'}), 401

        if not user_email:
            return jsonify({'error': 'No email found'}), 400

        # 2. GET STRIPE CUSTOMER ID
        stripe_customer_id = None
        
        # Try Firestore first
        if firestore_db and user_uid:
            try:
                user_doc = firestore_db.collection('users').document(user_uid).get()
                if user_doc.exists:
                    stripe_customer_id = user_doc.to_dict().get('stripeCustomerId')
            except Exception as e:
                print(f"Firestore lookup failed: {e}")

        # Fallback to Stripe lookup by email
        if not stripe_customer_id:
            customers = stripe.Customer.list(email=user_email, limit=1)
            if customers.data:
                stripe_customer_id = customers.data[0].id
        
        if not stripe_customer_id:
            # Create new customer if none exists (e.g. trial user accessing billing first time)
            try:
                print(f"Creating new Stripe Customer for {user_email}")
                new_customer = stripe.Customer.create(email=user_email)
                stripe_customer_id = new_customer.id
                
                # Save to Firestore if available
                if firestore_db and user_uid:
                    try:
                        firestore_db.collection('users').document(user_uid).set(
                            {'stripeCustomerId': stripe_customer_id}, merge=True
                        )
                    except Exception as db_err:
                        print(f"Failed to save new customer ID to Firestore: {db_err}")
                        
            except Exception as stripe_err:
                 print(f"Failed to create new Stripe customer: {stripe_err}")
                 return jsonify({'error': 'Could not create billing profile'}), 500

        # 3. CREATE PORTAL SESSION
        # Redirect back to dashboard after managing subscription
        return_url = "https://pigmentos.onrender.com/index.html"
        
        portal_session = stripe.billing_portal.Session.create(
            customer=stripe_customer_id,
            return_url=return_url,
        )

        return jsonify({'url': portal_session.url})

    except Exception as e:
        print(f"Portal Session Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stripe-webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events to update Firestore subscription status"""
    payload = request.get_data(as_text=True)
    
    # Verify webhook signature (skip in development if no secret configured)
    if STRIPE_WEBHOOK_SECRET:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
        except ValueError as e:
            print(f"Webhook Error: Invalid payload - {e}")
            return jsonify({'error': 'Invalid payload'}), 400
        except stripe.error.SignatureVerificationError as e:
            print(f"Webhook Error: Invalid signature - {e}")
            return jsonify({'error': 'Invalid signature'}), 400
    else:
        # Development mode - parse without verification
        event = json.loads(payload)
        print("⚠️ Webhook signature verification skipped (no secret configured)")
    
    event_type = event.get('type')
    print(f"📨 Stripe Webhook received: {event_type}")
    
    # Handle the event
    if event_type == 'checkout.session.completed':
        session = event['data']['object']
        customer_email = session.get('customer_email')
        subscription_id = session.get('subscription')
        
        if customer_email and firestore_db:
            try:
                # Find user by email in Firestore
                users_ref = firestore_db.collection('users')
                query = users_ref.where('email', '==', customer_email).limit(1)
                docs = query.stream()
                
                for doc in docs:
                    # Update subscription status
                    doc.reference.update({
                        'subscriptionStatus': 'active',
                        'stripeSubscriptionId': subscription_id,
                        'subscriptionUpdatedAt': firestore.SERVER_TIMESTAMP
                    })
                    print(f"✅ Updated Firestore for {customer_email}: subscriptionStatus = active")
                    break
            except Exception as e:
                print(f"❌ Firestore update failed: {e}")
        else:
            print(f"⚠️ Cannot update Firestore: email={customer_email}, db={firestore_db is not None}")
    
    elif event_type == 'customer.subscription.deleted':
        subscription = event['data']['object']
        customer_id = subscription.get('customer')
        
        # Look up customer email from Stripe
        try:
            customer = stripe.Customer.retrieve(customer_id)
            customer_email = customer.get('email')
            
            if customer_email and firestore_db:
                users_ref = firestore_db.collection('users')
                query = users_ref.where('email', '==', customer_email).limit(1)
                docs = query.stream()
                
                for doc in docs:
                    doc.reference.update({
                        'subscriptionStatus': 'expired',
                        'subscriptionUpdatedAt': firestore.SERVER_TIMESTAMP
                    })
                    print(f"✅ Updated Firestore for {customer_email}: subscriptionStatus = expired")
                    break
        except Exception as e:
            print(f"❌ Subscription deletion handling failed: {e}")
    
    elif event_type == 'customer.subscription.updated':
        subscription = event['data']['object']
        status = subscription.get('status')  # 'active', 'past_due', 'canceled', etc.
        customer_id = subscription.get('customer')
        
        try:
            customer = stripe.Customer.retrieve(customer_id)
            customer_email = customer.get('email')
            
            if customer_email and firestore_db:
                # Map Stripe status to our status
                firestore_status = 'active' if status == 'active' else 'expired'
                
                users_ref = firestore_db.collection('users')
                query = users_ref.where('email', '==', customer_email).limit(1)
                docs = query.stream()
                
                for doc in docs:
                    doc.reference.update({
                        'subscriptionStatus': firestore_status,
                        'subscriptionUpdatedAt': firestore.SERVER_TIMESTAMP
                    })
                    print(f"✅ Updated Firestore for {customer_email}: subscriptionStatus = {firestore_status}")
                    break
        except Exception as e:
            print(f"❌ Subscription update handling failed: {e}")

    elif event_type == 'invoice.paid':
        invoice = event['data']['object']
        customer_id = invoice.get('customer')
        subscription_id = invoice.get('subscription')
        
        try:
            customer = stripe.Customer.retrieve(customer_id)
            customer_email = customer.get('email')
            
            if customer_email and firestore_db:
                users_ref = firestore_db.collection('users')
                query = users_ref.where('email', '==', customer_email).limit(1)
                docs = query.stream()
                
                for doc in docs:
                    doc.reference.update({
                        'subscriptionStatus': 'active',
                        'stripeSubscriptionId': subscription_id,
                        'subscriptionUpdatedAt': firestore.SERVER_TIMESTAMP
                    })
                    print(f"💰 Invoice Paid for {customer_email}: Status -> active")
                    break
        except Exception as e:
            print(f"❌ Invoice paid handling failed: {e}")

    elif event_type == 'invoice.payment_failed':
        invoice = event['data']['object']
        customer_id = invoice.get('customer')
        
        try:
            customer = stripe.Customer.retrieve(customer_id)
            customer_email = customer.get('email')
            
            if customer_email and firestore_db:
                users_ref = firestore_db.collection('users')
                query = users_ref.where('email', '==', customer_email).limit(1)
                docs = query.stream()
                
                for doc in docs:
                    doc.reference.update({
                        'subscriptionStatus': 'past_due',
                        'subscriptionUpdatedAt': firestore.SERVER_TIMESTAMP
                    })
                    print(f"⚠️ Payment Failed for {customer_email}: Status -> past_due")
                    break
        except Exception as e:
            print(f"❌ Invoice payment failed handling failed: {e}")
    
    return jsonify({'status': 'success'}), 200

# --- User Saved Whales ---

@app.route('/api/whales/save', methods=['POST'])
def api_save_whale():
    """
    Save a whale trade to Firestore (user-initiated via long-press).
    """
    if not firestore_db:
        return jsonify({"error": "Database not available"}), 500
    
    try:
        trade = request.get_json()
        if not trade:
            return jsonify({"error": "No trade data provided"}), 400
        
        # Create a unique ID for the trade
        doc_id = f"{trade.get('ticker', '')}_{trade.get('strike', '')}_{trade.get('type', '')}_{trade.get('expiry', '')}_{trade.get('timestamp', '')}"
        doc_id = doc_id.replace("/", "-").replace(":", "").replace(" ", "")
        
        # Add saved timestamp
        trade['savedAt'] = time.time()
        
        # Save to Firestore
        doc_ref = firestore_db.collection('saved_whales').document(doc_id)
        doc_ref.set(trade, merge=True)
        
        return jsonify({"success": True, "id": doc_id})
        
    except Exception as e:
        print(f"❌ Failed to save whale: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/whales/saved')
def api_get_saved_whales():
    """
    Fetch user-saved whale trades from Firestore.
    """
    if not firestore_db:
        return jsonify({"data": []})
    
    try:
        start_time = time.time()
        def fetch_saved():
            saved_ref = firestore_db.collection('saved_whales')
            query = saved_ref.order_by('savedAt', direction=firestore.Query.DESCENDING).limit(100)
            return [doc.to_dict() for doc in query.stream()]
        
        # Reduced timeout from 5s to 2s to prevent hanging
        results = with_timeout(fetch_saved, timeout_seconds=2)
        
        duration = time.time() - start_time
        if duration > 1.0:
            print(f"⚠️ Slow Firebase Fetch: {duration:.2f}s")
            
        if results is None:
            print("❌ Firebase Fetch Timed Out (2s)")
            return jsonify({"data": []})
        
        return jsonify({"data": results})
        
    except Exception as e:
        print(f"❌ Failed to fetch saved whales: {e}")
        return jsonify({"data": []})

@app.route('/api/whales/delete', methods=['POST'])
def api_delete_whale():
    """
    Delete a saved whale trade from Firestore.
    """
    if not firestore_db:
        return jsonify({"error": "Database not available"}), 500
    
    try:
        data = request.get_json()
        doc_id = data.get('id')
        
        if not doc_id:
            return jsonify({"error": "No trade ID provided"}), 400
        
        firestore_db.collection('saved_whales').document(doc_id).delete()
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"❌ Failed to delete whale: {e}")
        return jsonify({"error": str(e)}), 500









@app.route('/api/polymarket')
def api_polymarket():
    global CACHE, POLY_STATE
    current_time = time.time()
    
    if current_time - CACHE["polymarket"]["timestamp"] < CACHE_DURATION:
        return jsonify({"data": CACHE["polymarket"]["data"], "is_mock": CACHE["polymarket"]["is_mock"]})

    try:
        # FETCH OPTIMIZATION:
        # 1. limit=200: Fetch more to allow for filtering
        # 2. order=volume24hr: Prioritize what's actually trading (12h-1d window)
        # 3. active=true & closed=false: Strict liveness check
        url = "https://gamma-api.polymarket.com/events?limit=200&active=true&closed=false&order=volume24hr&ascending=false"
        
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        
        # Optional: Use API Key if provided (helps with rate limits)
        api_key = os.environ.get("POLYMARKET_API_KEY")
        if api_key:
            headers['Authorization'] = f"Bearer {api_key}"

            
        resp = requests.get(url, headers=headers, verify=False, timeout=5)
        
        if resp.status_code == 200:
            events = resp.json()
            
            # FALLBACK: Explicitly fetch important FOMC events that may not appear in main query
            # (New events might not be indexed immediately after previous month resolves)
            important_slugs = [
                'fed-decision-in-january',
                'fed-decision-in-february', 
                'fed-decision-in-march',
                'fed-decisions-dec-mar'
            ]
            for slug in important_slugs:
                try:
                    slug_resp = requests.get(f'https://gamma-api.polymarket.com/events?slug={slug}', headers=headers, verify=False, timeout=3)
                    if slug_resp.status_code == 200:
                        slug_events = slug_resp.json()
                        for se in slug_events:
                            # Only add if not closed and not already in events
                            if not se.get('closed') and not any(e.get('slug') == se.get('slug') for e in events):
                                events.append(se)
                except:
                    pass
            
            # --- NEW LOGIC START ---
            import math # Import locally to avoid changing top of file
            
            CATEGORY_KEYWORDS = {
                "GEOPOL": [
                    "war", "invasion", "strike", "china", "russia", "israel", "iran", 
                    "taiwan", "ukraine", "gaza", "military", "ceasefire", "regime", 
                    "syria", "korea", "venezuela", "heutih"
                ],
                "MACRO": [
                    "fed", "rate", "inflation", "cpi", "recession", "powell", "gold", 
                    "treasury", "trump", "cabinet", "nominate", "tariff"
                ],
                "TECH": [
                    "nvidia", "apple", "microsoft", "google", "tesla", "openai", "gemini", 
                    "grok", "deepseek", "claude", "spacex", "starship", "robotaxi"
                ],
                "CULTURE": [
                    "spotify", "youtube", "mrbeast", "swift", "beyonce", "grammy"
                ]
            }

            BLACKLIST_WORDS = [
                # Structural (Enforce Yes/No UI)
                "who will", "which company", "what will", "price on", "how many", 
                "highest", "lowest", "above/below",
                
                # Sports/Entertainment Noise
                "nfl", "nba", "super bowl", "sport", "football", "basketball", 
                "soccer", "tennis", "golf", "box office", "cinema", "rotten tomatoes",
                
                # Crypto/Asset Noise
                "solana", "memecoin", "pepe", "doge", 
                
                # General
                "searched", "daily", "weekly"
            ]
            
            candidates = []
            seen_stems = {}

            def get_title_stem(t):
                # Lowercase first
                s = t.lower()
                # Remove currency amounts (e.g. $100k, $95,000)
                s = re.sub(r'\$[\d,]+(\.\d+)?[kKmM]?', '', s)
                # Remove years (2024-2029)
                s = re.sub(r'\b202[4-9]\b', '', s)
                # Remove specific date patterns: "on December 5", "by Jan 1", "in March"
                # Matches: on/by/in + optional space + Month + optional space + optional Day
                months = r"(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)"
                s = re.sub(r'\b(on|by|in)?\s*' + months + r'\s*(\d{1,2})?(st|nd|rd|th)?\b', '', s)
                # Remove "above" or "below" if followed by space (common in price targets)
                s = re.sub(r'\b(above|below|hit|reach)\b', '', s)
                # Remove placeholders
                s = s.replace("___", "")
                # Collapse whitespace and non-alphanumeric (keep only letters for strict topic matching)
                s = re.sub(r'[^a-z\s]', '', s)
                return ' '.join(s.split())

            for event in events:
                title = event.get('title', '')
                title_lower = title.lower()
                
                # 0. Skip CLOSED markets (API sometimes returns them despite closed=false)
                if event.get('closed', False):
                    continue
                
                # 0b. Skip markets whose end date has passed
                end_date = event.get('endDate', '')
                if end_date and end_date < datetime.now(pytz.UTC).isoformat():
                    continue

                # 1. Blacklist Check
                if any(bad in title_lower for bad in BLACKLIST_WORDS): continue
                
                # 2. Filter out markets with specific times of day (e.g., "11AM ET", "7PM ET")
                # This regex matches patterns like: 11AM, 11:30AM, 7PM, 3:45PM (with optional ET/EST/PST)
                time_pattern = r'\b\d{1,2}(:\d{2})?\s*(AM|PM|am|pm)\s*(ET|EST|PST|CST)?\b'
                if re.search(time_pattern, title):
                    continue  # Skip markets with time-of-day mentions
                
                # 3. Determine Category
                category = "OTHER"
                for cat, keys in CATEGORY_KEYWORDS.items():
                    if any(re.search(r'\b' + re.escape(k) + r'\b', title_lower) for k in keys):
                        category = cat
                        break
                
                if category == "OTHER": continue
                
                # 4. Filter out multi-range markets (temperature, views, prices, etc.)
                # These markets have 3+ outcomes and don't display well in binary format
                multi_range_patterns = [
                    r'temperature',
                    r'how many',
                    r'# of views',
                    r'number of',
                    r'what price',
                    r'how much',
                    r'what will.*close at',
                    r'highest.*on',
                    r'lowest.*on'
                ]
                if any(re.search(pattern, title_lower) for pattern in multi_range_patterns):
                    continue

                # 5. Market Data Extraction
                markets = event.get('markets', [])
                if not markets: continue
                
                # For multi-outcome events (e.g., 'Next CEO', 'Republican Nominee'),
                # pick the sub-market with the HIGHEST ABSOLUTE 24h CHANGE.
                # This shows where the action is, not just the boring favorite.
                # Tie-breaker: If delta is equal (or all 0), fall back to highest probability.
                if len(markets) > 1:
                    def get_lead_outcome(outcomes):
                        """
                        Select the sub-market with highest |24h_change|.
                        Tie-breaker: highest probability.
                        """
                        if not outcomes:
                            return None
                        
                        scored = []
                        for mkt in outcomes:
                            try:
                                # Get 24h change (delta)
                                delta = abs(float(mkt.get('oneDayPriceChange', 0) or 0))
                                
                                # Get probability for tie-breaker
                                prices = json.loads(mkt['outcomePrices']) if isinstance(mkt['outcomePrices'], str) else mkt['outcomePrices']
                                prob = float(prices[0]) if prices else 0
                                
                                scored.append({
                                    'market': mkt,
                                    'abs_delta': delta,
                                    'prob': prob
                                })
                            except:
                                continue
                        
                        if not scored:
                            return outcomes[0]
                        
                        # Sort by |delta| DESC, then probability DESC as tie-breaker
                        scored.sort(key=lambda x: (x['abs_delta'], x['prob']), reverse=True)
                        return scored[0]['market']
                    
                    m = get_lead_outcome(markets) or markets[0]
                else:
                    m = markets[0] 
                
                # Calculate Metrics
                try:
                    vol = float(m.get('volume', 0))
                    liq = float(m.get('liquidity', 0))
                    delta = float(m.get('oneDayPriceChange', 0))
                except: continue

                # Thresholds
                if vol < 1000 or liq < 500: continue
                
                # 4. Deduplication Logic
                stem = get_title_stem(title)
                
                # If we've seen this stem, only keep the one with higher volume
                if stem in seen_stems:
                    existing_idx = seen_stems[stem]
                    if vol > candidates[existing_idx]['volume']:
                        # Replace existing with this one (mark existing as skipped)
                        candidates[existing_idx]['skip'] = True
                        seen_stems[stem] = len(candidates) # Update pointer
                    else:
                        continue # Skip this one, existing is better
                else:
                    seen_stems[stem] = len(candidates)

                # 5. Weighted Score
                score = math.log(vol + 1) * (abs(delta) * 100)
                
                # 6. Process Outcomes (for Display)
                # This part is from the original code, adapted for the new loop
                try:
                    # Fix Template Titles
                    if "___" in title:
                        val = m.get('groupItemTitle', '')
                        if val: title = title.replace("___", val)

                    # MULTI-OUTCOME HANDLING:
                    # For events with multiple sub-markets (e.g., Fed decisions),
                    # aggregate all sub-market probabilities to show proper outcomes.
                    if len(markets) > 1 and markets[0].get('groupItemTitle'):
                        outcome_data = []
                        for mkt in markets:
                            gt = mkt.get('groupItemTitle', '')
                            if not gt: continue
                            try:
                                prices = json.loads(mkt['outcomePrices']) if isinstance(mkt['outcomePrices'], str) else mkt['outcomePrices']
                                yes_prob = float(prices[0]) if prices else 0
                                outcome_data.append({"label": gt, "price": yes_prob})
                            except:
                                continue
                        
                        if len(outcome_data) < 2:
                            # Fallback to single market logic
                            outcomes = json.loads(m['outcomes']) if isinstance(m['outcomes'], str) else m['outcomes']
                            prices = json.loads(m['outcomePrices']) if isinstance(m['outcomePrices'], str) else m['outcomePrices']
                            outcome_data = [{"label": str(outcomes[i]), "price": float(prices[i])} for i in range(len(outcomes))]
                    else:
                        # Single market or non-grouped: use standard Yes/No outcomes
                        outcomes = json.loads(m['outcomes']) if isinstance(m['outcomes'], str) else m['outcomes']
                        prices = json.loads(m['outcomePrices']) if isinstance(m['outcomePrices'], str) else m['outcomePrices']
                        
                        outcome_data = []
                        for i in range(len(outcomes)):
                            try:
                                price = float(prices[i])
                                label = str(outcomes[i])
                                outcome_data.append({"label": label, "price": price})
                            except: continue
                        
                        # OVERRIDE LABEL for grouped markets
                        group_title = m.get('groupItemTitle')
                        if group_title and len(outcome_data) > 0 and outcome_data[0]['label'].lower() == "yes":
                            outcome_data[0]['label'] = group_title
                    
                    outcome_data.sort(key=lambda x: x['price'], reverse=True)
                    if len(outcome_data) < 2: continue
                    
                    top1 = outcome_data[0]
                    top2 = outcome_data[1]
                    
                    def format_money(val):
                        if val >= 1_000_000: return f"${val/1_000_000:.1f}M"
                        if val >= 1_000: return f"${val/1_000:.0f}k"
                        return f"${val:.0f}"

                    candidates.append({
                        "event": title,
                        "category": category,
                        "is_volatile": abs(delta) >= 0.05,
                        "volume": vol, # Keep raw for sorting
                        "volume_fmt": format_money(vol),
                        "liquidity": format_money(liq),
                        "outcome_1_label": top1['label'],
                        "outcome_1_prob": int(top1['price'] * 100),
                        "outcome_2_label": top2['label'],
                        "outcome_2_prob": int(top2['price'] * 100),
                        "slug": event.get('slug', ''),
                        "delta": delta,
                        "score": score,
                        "skip": False
                    })
                except Exception as e:
                    continue

            # Filter and Sort
            final_list = [c for c in candidates if not c['skip']]
            final_list.sort(key=lambda x: x['score'], reverse=True)
            
            # Format for Frontend (remove raw fields)
            clean_markets = []
            for c in final_list[:50]:
                clean_markets.append({
                    "event": c['event'],
                    "category": c['category'],
                    "is_volatile": c['is_volatile'],
                    "volume": c['volume_fmt'],
                    "liquidity": c['liquidity'],
                    "outcome_1_label": c['outcome_1_label'],
                    "outcome_1_prob": c['outcome_1_prob'],
                    "outcome_2_label": c['outcome_2_prob'],
                    "outcome_2_prob": c['outcome_2_prob'],
                    "slug": c['slug'],
                    "delta": c['delta']
                })
            
            CACHE["polymarket"]["data"] = clean_markets
            CACHE["polymarket"]["timestamp"] = current_time
            CACHE["polymarket"]["is_mock"] = False
            SERVICE_STATUS["POLY"] = {"status": "ONLINE", "last_updated": time.time()}
        else:
            raise Exception("API Error")
            
    except Exception as e:
        print(f"Polymarket Error: {e}")
        SERVICE_STATUS["POLY"] = {"status": "OFFLINE", "last_updated": time.time()}
        # Mock Fallback
        CACHE["polymarket"]["data"] = [
            {"event": "Will Bitcoin hit $100k in 2024?", "outcome_1_label": "Yes", "outcome_1_prob": 68, "outcome_2_label": "No", "outcome_2_prob": 32, "slug": "btc-100k", "delta": 0.06},
            {"event": "Fed rate cut in December?", "outcome_1_label": "Yes", "outcome_1_prob": 75, "outcome_2_label": "No", "outcome_2_prob": 25, "slug": "fed-cut", "delta": -0.02}
        ]
        CACHE["polymarket"]["is_mock"] = True

    return jsonify({"data": CACHE["polymarket"]["data"], "is_mock": CACHE["polymarket"]["is_mock"]})

# VIX endpoint removed - not used (TFI uses CNN+VIX composite instead)

@app.route('/api/cnn-fear-greed')
def api_fear_greed():
    """
    Fetch Trader Fear Index (TFI) - 50/50 weighted composite:
    1. CNN Anchor (50%): CNN Fear & Greed Index via fear-and-greed library
    2. VIX Pulse (50%): Intraday VIX on linear scale (12→100, 17→50, 22→0)
    """
    global CACHE
    current_time = time.time()
    
    # Cache for 15 minutes
    if current_time - CACHE["cnn_fear_greed"]["timestamp"] < 900:
        return jsonify(CACHE["cnn_fear_greed"]["data"])
        
    try:
        # Import the composite module
        from fetch_composite_tfi import get_composite_score
        
        result = get_composite_score()
        
        # Map to expected frontend format
        data = {
            "value": result["score"],
            "rating": result["rating"],
            "source": f"CNN:{result['cnn_anchor']:.0f} VIX:{result['vix_value']:.1f}",
            "cnn_anchor": result["cnn_anchor"],
            "vix_score": result["vix_score"],
            "vix_value": result["vix_value"],
            "mode": result["mode"]
        }
        
        CACHE["cnn_fear_greed"] = {"data": data, "timestamp": current_time}
        return jsonify(data)
        
    except Exception as e:
        print(f"TFI Composite Error: {e}")
        # Return cached data if available, else fallback
        if CACHE["cnn_fear_greed"]["data"]:
            return jsonify(CACHE["cnn_fear_greed"]["data"])
        return jsonify({"value": 50, "rating": "Neutral", "source": "Fallback"})


@app.route('/api/movers')
def api_movers():
    global CACHE
    current_time = time.time()
    
    if current_time - CACHE["movers"]["timestamp"] < 3600 and CACHE["movers"]["data"]:
        return jsonify(CACHE["movers"]["data"])
    
    MOVERS_TICKERS = [
        # Mag 7 & Tech Giants
        "NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META", "GOOGL",
        
        # Semiconductors & AI
        "AMD", "INTC", "AVGO", "MU", "ARM", "SMCI",
        
        # FinTwit Meme Stocks & High Volume
        "PLTR",
        
        # Growth Tech & SaaS
        "CRWD",
        
        # Consumer & Entertainment
        "NFLX", "DIS", "UBER", "DASH", "ABNB", "PTON", "NKE", "SBUX",
    ]
    
    try:
        movers = []
        
        # Use yfinance for movers (Polygon rate limits at 50+ tickers)
        def fetch_movers_tickers():
            return yf.Tickers(" ".join(MOVERS_TICKERS))
        
        tickers_obj = with_timeout(fetch_movers_tickers, timeout_seconds=10)
        if not tickers_obj:
            print("⏰ Movers tickers fetch timed out")
            return jsonify({"error": "timeout"})
        
        def fetch_ticker_data(symbol):
            try:
                time.sleep(random.uniform(0.01, 0.05))  # Small jitter
                t = tickers_obj.tickers[symbol]
                last = t.fast_info.last_price
                prev = t.fast_info.previous_close
                if last and prev:
                    change = ((last - prev) / prev) * 100
                    return {
                        "symbol": symbol,
                        "change": round(change, 2),
                        "type": "gain" if change >= 0 else "loss"
                    }
            except:
                return None
            return None
        
        # Parallel fetch
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(fetch_ticker_data, MOVERS_TICKERS))
        
        movers = [r for r in results if r is not None]
        movers.sort(key=lambda x: x['change'], reverse=True)
        
        CACHE["movers"]["data"] = movers
        CACHE["movers"]["timestamp"] = current_time
        print(f"📊 Movers: Fetched {len(movers)} tickers via yfinance")
        return jsonify(movers)
        
    except Exception as e:
        print(f"Movers Error: {e}")
        return jsonify({"error": str(e)})


@app.route('/api/economic-calendar')
def api_economic_calendar():
    global CACHE
    current_time = time.time()
    
    # Cache for 1 hour for economic calendar
    if current_time - CACHE["economic_calendar"]["timestamp"] < 3600:
        return jsonify(CACHE["economic_calendar"]["data"])
        
    try:
        # Fetch releases for the next 3 weeks using FRED API
        start_date = datetime.now().strftime('%Y-%m-%d')
        end_date = (datetime.now() + timedelta(days=21)).strftime('%Y-%m-%d')
        
        url = f"https://api.stlouisfed.org/fred/releases/dates?api_key={FRED_API_KEY}&file_type=json&realtime_start={start_date}&realtime_end={end_date}&include_release_dates_with_no_data=true&limit=50&sort_order=asc"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            print(f"⚠️ FRED API Error: {response.status_code}")
            return jsonify(CACHE["economic_calendar"]["data"])
            
        data = response.json()
        release_dates = data.get('release_dates', [])
        
        # High-impact releases (FOMC, Jobs, GDP)
        HIGH_IMPACT_KEYWORDS = ['FOMC', 'Employment', 'GDP', 'Nonfarm', 'Jobless', 'Retail Sales', 'Federal Reserve']
        MEDIUM_IMPACT_KEYWORDS = ['ADP', 'PMI', 'Housing', 'Durable', 'Industrial', 'Trade Balance', 'Treasury']
        
        formatted_events = []
        for item in release_dates:
            release_name = item.get('release_name', 'Unknown')
            release_date = item.get('date', '')
            
            # Determine impact level based on keywords
            stars = 1
            critical = False
            event_type = "STANDARD"
            
            if any(kw.lower() in release_name.lower() for kw in HIGH_IMPACT_KEYWORDS):
                stars = 3
                critical = True
                event_type = "BOSS ENCOUNTER"
            elif any(kw.lower() in release_name.lower() for kw in MEDIUM_IMPACT_KEYWORDS):
                stars = 2
                event_type = "CRITICAL DATA"
            
            # Format time for display (e.g. "TUE JAN 07")
            try:
                dt = datetime.strptime(release_date, '%Y-%m-%d')
                display_time = dt.strftime('%a %b %d').upper()
            except:
                display_time = release_date
                dt = datetime.now()
                
            formatted_events.append({
                "title": release_name.upper(),
                "time": display_time,
                "type": event_type,
                "status": "UPCOMING",
                "critical": critical,
                "stars": stars,
                "rawDate": release_date,
                "country": "US"
            })
        
        # Filter to only high-impact (3-star BOSS ENCOUNTER) events
        formatted_events = [e for e in formatted_events if e['stars'] >= 3]
        
        # Sort by date and limit to top 6
        formatted_events.sort(key=lambda x: x['rawDate'])
        formatted_events = formatted_events[:6]
        
        CACHE["economic_calendar"]["data"] = formatted_events
        CACHE["economic_calendar"]["timestamp"] = current_time
        
        return jsonify(formatted_events)
        
    except Exception as e:
        print(f"⚠️ Economic Calendar Error: {e}")
        return jsonify(CACHE["economic_calendar"]["data"])


@app.route('/api/news')
def api_news():
    global CACHE
    # Check if data has been hydrated (timestamp > 0 means we've fetched at least once)
    if CACHE["news"]["timestamp"] == 0:
        return jsonify({"loading": True, "data": []})
    
    # STALE DATA DETECTION: Clear cache if ALL news is older than 12 hours
    # This prevents showing "NO RECENT NEWS FOUND" - instead triggers fresh fetch
    news_data = CACHE["news"]["data"]
    if news_data:
        current_time = time.time()
        max_age = 12 * 60 * 60  # 12 hours in seconds
        freshness_threshold = current_time - max_age
        
        # Check if ANY news item is within the last 12 hours
        has_fresh_news = any(item.get("time", 0) >= freshness_threshold for item in news_data)
        
        if not has_fresh_news:
            print(f"⚠️ All {len(news_data)} news items are stale (>12h old). Clearing cache to trigger refresh.", flush=True)
            CACHE["news"]["data"] = []
            CACHE["news"]["timestamp"] = 0  # Reset to trigger hydration
            return jsonify({"loading": True, "data": []})
    
    return jsonify(CACHE["news"]["data"])



def refresh_news_logic():
    global CACHE

    RSS_FEEDS = [
        "https://www.investing.com/rss/news.rss",
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
        "https://techcrunch.com/feed/",
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"
    ]
    
    all_news = []
    current_time = time.time()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
    }

    def fetch_single_feed(url):
        try:
            # Individual timeout of 3s (reduced from 10s for faster page loads)
            response = requests.get(url, headers=headers, verify=False, timeout=3)
            
            if response.status_code != 200:
                print(f"⚠️ Feed Error {url}: Status {response.status_code}", flush=True)
                return []
            
            feed = feedparser.parse(response.content)
            
            if not feed.entries:
                print(f"⚠️ Feed Empty {url}", flush=True)
                return []
            
            print(f"✅ Feed Success {url}: Found {len(feed.entries)} entries", flush=True)
            
            feed_items = []
            for entry in feed.entries[:5]:
                pub_ts = int(time.time())
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_ts = int(calendar.timegm(entry.published_parsed))
                
                publisher = "Market Wire"
                domain = "google.com" # Default fallback
                
                if "cnbc" in url: 
                    publisher = "CNBC"
                    domain = "cnbc.com"
                elif "techcrunch" in url: 
                    publisher = "TechCrunch"
                    domain = "techcrunch.com"
                elif "investing.com" in url: 
                    publisher = "Investing.com"
                    domain = "investing.com"
                elif "wsj.com" in url or "dj.com" in url: 
                    publisher = "WSJ"
                    domain = "wsj.com"
                
                feed_items.append({
                    "title": entry.get('title', ''),
                    "publisher": publisher,
                    "domain": domain,
                    "link": entry.get('link', ''),
                    "time": pub_ts,
                    "ticker": "NEWS"
                })
            return feed_items
            
        except Exception as e:
            print(f"⚠️ Feed Error {url}: {e}", flush=True)
            return []

    try:
        # PARALLEL FETCHING (RSS)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(fetch_single_feed, RSS_FEEDS))
        
        # Flatten results
        for r in results:
            all_news.extend(r)
        
        # === FINNHUB SUPPLEMENTAL NEWS ===
        # Adds market news from Finnhub API (1 call, ~100 items)
        if FINNHUB_API_KEY:
            try:
                finnhub_url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}"
                resp = requests.get(finnhub_url, timeout=10)
                if resp.status_code == 200:
                    finnhub_data = resp.json()
                    
                    # Filter to last 12 hours and take top 10
                    freshness_threshold = current_time - (12 * 60 * 60)
                    fresh_items = [item for item in finnhub_data if item.get('datetime', 0) >= freshness_threshold][:10]
                    
                    # Build set of existing titles for deduplication (lowercase, first 50 chars)
                    existing_titles = set(item['title'][:50].lower() for item in all_news)
                    
                    finnhub_added = 0
                    for item in fresh_items:
                        headline = item.get('headline', '')
                        # Skip if similar title already exists
                        if headline[:50].lower() in existing_titles:
                            continue
                        
                        source = item.get('source', 'Finnhub')
                        # Map source to domain for favicon
                        domain = "finnhub.io"
                        if 'marketwatch' in source.lower():
                            domain = "marketwatch.com"
                        elif 'cnbc' in source.lower():
                            domain = "cnbc.com"
                        elif 'reuters' in source.lower():
                            domain = "reuters.com"
                        elif 'bloomberg' in source.lower():
                            domain = "bloomberg.com"
                        
                        all_news.append({
                            "title": headline,
                            "publisher": source,
                            "domain": domain,
                            "link": item.get('url', ''),
                            "time": item.get('datetime', int(current_time)),
                            "ticker": "NEWS"
                        })
                        finnhub_added += 1
                        existing_titles.add(headline[:50].lower())
                    
                    print(f"✅ Finnhub News: Added {finnhub_added} unique items (filtered from {len(fresh_items)} fresh)", flush=True)
                else:
                    print(f"⚠️ Finnhub News: HTTP {resp.status_code}", flush=True)
            except Exception as e:
                print(f"⚠️ Finnhub News Error: {e}", flush=True)
        
        all_news.sort(key=lambda x: x['time'], reverse=True)
        
        if all_news:
            CACHE["news"]["data"] = all_news
            CACHE["news"]["timestamp"] = current_time
            CACHE["news"]["last_error"] = None
        else:
            print("⚠️ No news found from any RSS feed", flush=True)
            CACHE["news"]["last_error"] = "All RSS feeds empty or blocked"
            
    except Exception as e:
        print(f"News Update Failed: {e}")
        CACHE["news"]["last_error"] = str(e)



@app.route('/api/debug/force-news')
def debug_news():
    try:
        # Capture stdout to see print logs
        import io
        import sys
        old_stdout = sys.stdout
        new_stdout = io.StringIO()
        sys.stdout = new_stdout
        
        refresh_news_logic()
        
        sys.stdout = old_stdout
        logs = new_stdout.getvalue()
        
        return jsonify({
            "status": "success",
            "count": len(CACHE["news"]["data"]),
            "data": CACHE["news"]["data"],
            "last_error": CACHE["news"]["last_error"],
            "logs": logs
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/debug/force-heatmap')
def debug_heatmap():
    try:
        # Capture stdout
        import io
        import sys
        old_stdout = sys.stdout
        new_stdout = io.StringIO()
        sys.stdout = new_stdout
        
        refresh_heatmap_logic()
        
        sys.stdout = old_stdout
        logs = new_stdout.getvalue()
        
        return jsonify({
            "status": "success",
            "count": len(CACHE["heatmap"]["data"]),
            "data": CACHE["heatmap"]["data"],
            "logs": logs
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/debug/force-whales')
def debug_force_whales():
    """Force a whale scan on a single ticker and show raw results."""
    import io, sys
    symbol = request.args.get('symbol', 'NVDA')
    
    old_stdout = sys.stdout
    new_stdout = io.StringIO()
    sys.stdout = new_stdout
    
    try:
        # Run the whale scan
        refresh_single_whale(symbol)
        
        sys.stdout = old_stdout
        logs = new_stdout.getvalue()
        
        return jsonify({
            "status": "success",
            "symbol": symbol,
            "cache_count": len(CACHE["whales"]["data"]),
            "cache_timestamp": CACHE["whales"]["timestamp"],
            "cache_data": CACHE["whales"]["data"][:5],  # First 5
            "logs": logs
        })
    except Exception as e:
        sys.stdout = old_stdout
        import traceback
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500



@app.route('/api/debug/sources')
def debug_sources():
    """
    Production diagnostic: Test each external data source individually.
    Call this on production to identify which service is rate limiting.
    """
    results = {
        "timestamp": datetime.now().isoformat(),
        "sources": {}
    }
    
    # 1. Test RSS Feeds
    rss_feeds = {
        "investing.com": "https://www.investing.com/rss/news.rss",
        "cnbc": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
        "techcrunch": "https://techcrunch.com/feed/",
        "wsj": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }
    
    for name, url in rss_feeds.items():
        start = time.time()
        try:
            resp = requests.get(url, headers=headers, verify=False, timeout=3)
            duration = time.time() - start
            feed = feedparser.parse(resp.content)
            results["sources"][f"rss_{name}"] = {
                "status": "OK" if resp.status_code == 200 else f"HTTP {resp.status_code}",
                "duration_ms": round(duration * 1000),
                "items_found": len(feed.entries) if feed.entries else 0,
                "rate_limited": resp.status_code == 429 or "too many" in resp.text.lower()
            }
        except Exception as e:
            results["sources"][f"rss_{name}"] = {
                "status": "ERROR",
                "error": str(e)[:100],
                "rate_limited": "rate" in str(e).lower() or "429" in str(e)
            }
    
    # 2. Test yfinance (single ticker to minimize impact)
    start = time.time()
    try:
        def test_yf():
            t = yf.Ticker("SPY")
            return t.fast_info.last_price
        price = with_timeout(test_yf, timeout_seconds=5)
        duration = time.time() - start
        results["sources"]["yfinance"] = {
            "status": "OK" if price else "NO DATA",
            "duration_ms": round(duration * 1000),
            "spy_price": round(price, 2) if price else None,
            "rate_limited": price is None
        }
    except Exception as e:
        err_str = str(e)
        results["sources"]["yfinance"] = {
            "status": "ERROR",
            "error": err_str[:100],
            "rate_limited": "Too Many Requests" in err_str or "429" in err_str
        }
    
    # 3. Test Polygon API (should never rate limit on Starter plan)
    if POLYGON_API_KEY:
        start = time.time()
        try:
            url = f"https://api.polygon.io/v2/aggs/ticker/SPY/prev?apiKey={POLYGON_API_KEY}"
            resp = requests.get(url, timeout=5)
            duration = time.time() - start
            data = resp.json()
            results["sources"]["polygon"] = {
                "status": "OK" if resp.status_code == 200 else f"HTTP {resp.status_code}",
                "duration_ms": round(duration * 1000),
                "has_data": bool(data.get("results")),
                "rate_limited": resp.status_code == 429
            }
        except Exception as e:
            results["sources"]["polygon"] = {
                "status": "ERROR",
                "error": str(e)[:100]
            }
    
    # 4. Summary
    failing = [k for k, v in results["sources"].items() 
               if v.get("status") != "OK" or v.get("rate_limited")]
    results["summary"] = {
        "failing_sources": failing,
        "recommendation": "Remove or replace failing sources" if failing else "All sources OK"
    }
    
    return jsonify(results)


def refresh_gamma_logic(symbol="SPY"):

    global CACHE
    
    from datetime import timedelta
    tz_eastern = pytz.timezone('US/Eastern')
    now_eastern = datetime.now(tz_eastern)
    today_date = now_eastern.date()
    weekday = today_date.weekday()
    is_weekend = weekday >= 5
    
    # Calculate time of day
    hour = now_eastern.hour
    minute = now_eastern.minute
    
    # Determine Time Period
    # market_hours = 9:30-16:00, after_hours = 16:00-20:00, evening = 20:00-midnight
    # pre_market = 4:00-9:30, weekend = Sat/Sun
    
    time_period = "overnight"
    if is_weekend:
        time_period = "weekend"
    elif 4 <= hour < 9 or (hour == 9 and minute < 30):
        time_period = "pre_market"
    elif (hour == 9 and minute >= 30) or (10 <= hour < 16):
        time_period = "market_hours"
    elif 16 <= hour < 20:
        time_period = "after_hours"
        
    # === PRIORITY 1: Polygon.io (Unlimited API calls, 15-min delayed) ===
    polygon_data = fetch_options_chain_polygon(symbol, strike_limit=40)
    
    if polygon_data and polygon_data.get("results"):
        try:
            print(f"Gamma: Using Polygon.io for {symbol}")
            
            # Parse Polygon response to gamma format
            # Get current price from fetch response (already queried)
            fetched_price = polygon_data.get("_current_price")
            gamma_data, current_price = parse_polygon_to_gamma_format(polygon_data, fetched_price)
            
            if not current_price or not gamma_data:
                raise ValueError("Failed to parse Polygon response")
            
            # Polygon API already filters strikes to ±10% of ATM
            # Apply industry-standard filters to remove noise
            MIN_VOLUME = 100  # Minimum combined volume for visibility
            # Dynamic OI threshold based on ticker liquidity
            # Indices = higher bar (extremely liquid), single stocks = lower bar
            INDEX_ETFS = ['SPY', 'QQQ', 'IWM', 'DIA']
            MIN_OI = 500  # Same threshold for all tickers (indices and single stocks)
            
            final_data = []
            for strike, data in gamma_data.items():
                # Calculate totals
                total_vol = data["call_vol"] + data["put_vol"]
                total_oi = data["call_oi"] + data["put_oi"]
                
                # Skip strikes with low OI (no meaningful gamma impact)
                # This is the key filter - MMs only hedge significant OI
                if total_oi < MIN_OI:
                    continue
                    
                # Relax volume filter for Indices:
                # For SPY/QQQ, we want to see the structure regardless of today's volume
                # For single stocks, we still require some volume to prove activity
                is_index = symbol in INDEX_ETFS
                
                # If it's NOT an index, enforce volume filter
                if not is_index and total_vol < MIN_VOLUME:
                    continue
                final_data.append({
                    "strike": strike,
                    "call_vol": data["call_vol"],
                    "put_vol": data["put_vol"],
                    "call_oi": data["call_oi"],
                    "put_oi": data["put_oi"],
                    "call_premium": data.get("call_premium", 0),
                    "put_premium": data.get("put_premium", 0),
                    "call_gex": data.get("call_gex", 0),
                    "put_gex": data.get("put_gex", 0),
                    "net_gex": data.get("net_gex", 0)  # Industry-standard net GEX
                })
            
            final_data.sort(key=lambda x: x['strike'], reverse=True)  # High → Low (pre-sorted for client)
            
            result = {
                "symbol": symbol,
                "current_price": current_price,
                "expiry": "Weekly",
                "strikes": final_data,
                "time_period": time_period,  # For smart badge display
                "source": "polygon.io",
                "_expiry_date": polygon_data.get("_expiry_date"),  # Pass through for TOMORROW badge
                "_is_next_trading_day": polygon_data.get("_is_next_trading_day", False),
                "_date_label": polygon_data.get("_date_label", "TODAY")
            }
            
            cache_key = f"gamma_{symbol}"
            CACHE[cache_key] = {"data": result, "timestamp": time.time()}
            SERVICE_STATUS["GAMMA"] = {"status": "ONLINE", "last_updated": time.time()}
            return
            
        except Exception as e:
            print(f"Gamma Polygon Parse Error ({symbol}): {e}")
    
    # No fallbacks - if Polygon fails, mark as OFFLINE
    print(f"Gamma: No data available for {symbol} (Polygon failed)")
    SERVICE_STATUS["GAMMA"] = {"status": "OFFLINE", "last_updated": time.time()}

@app.route('/api/gamma')
def api_gamma():
    global CACHE
    symbol = request.args.get('symbol', 'SPY').upper()
    cache_key = f"gamma_{symbol}"
    
    # Serve directly from cache if fresh (< 5 mins)
    if cache_key in CACHE and CACHE[cache_key]["data"]:
        age = time.time() - CACHE[cache_key]["timestamp"]
        if age < 300:
            return jsonify(CACHE[cache_key]["data"])
            
    # If missing or stale, fetch immediately (On-Demand)
    # Note: This might block for 1-2s, but ensures data availability
    try:
        refresh_gamma_logic(symbol)
        if cache_key in CACHE and CACHE[cache_key]["data"]:
            return jsonify(CACHE[cache_key]["data"])
    except Exception as e:
        print(f"On-Demand Gamma Fetch Error: {e}")
        
    return jsonify({"error": "Loading or Failed..."})

@app.route('/api/price')
def api_price():
    """
    Lightweight endpoint to get just the current price.
    Used for frequent UI updates (e.g. Gamma Wall ATM indicator) without heavy data fetching.
    """
    symbol = request.args.get('symbol', 'SPY').upper()
    
    # Try Finnhub first (Gamma Wall source)
    price = get_finnhub_price(symbol)
    source = "finnhub"
    
    # Fallback to YFinance/Cache
    if not price:
        price = get_cached_price(symbol)
        source = "yfinance"
        
    if price:
        return jsonify({"symbol": symbol, "price": price, "source": source, "timestamp": time.time()})
    else:
        return jsonify({"error": "Price unavailable"}), 404

@app.route('/api/ping')
def api_ping():
    return jsonify({"status": "ok", "timestamp": time.time()})

# === FINNHUB MARKET STATUS ===
# Cache for market status (refresh every 60 seconds)
MARKET_STATUS_CACHE = {"data": None, "timestamp": 0}
MARKET_STATUS_CACHE_TTL = 60  # 1 minute

@app.route('/api/market-status')
def api_market_status():
    """
    Get real-time market status from Finnhub API.
    Returns: isOpen, session (pre-market/regular/post-market), holiday info
    Fallback to time-based calculation if API fails.
    """
    global MARKET_STATUS_CACHE
    
    now = time.time()
    
    # Return cached data if fresh
    if MARKET_STATUS_CACHE["data"] and (now - MARKET_STATUS_CACHE["timestamp"] < MARKET_STATUS_CACHE_TTL):
        return jsonify(MARKET_STATUS_CACHE["data"])
    
    # Fetch from Finnhub
    try:
        if FINNHUB_API_KEY:
            url = f"https://finnhub.io/api/v1/stock/market-status?exchange=US&token={FINNHUB_API_KEY}"
            resp = requests.get(url, timeout=5)
            
            if resp.status_code == 200:
                data = resp.json()
                # Finnhub returns: {exchange, holiday, isOpen, session, t, timezone}
                # session can be: "pre-market", "regular", "post-market", or null
                
                result = {
                    "isOpen": data.get("isOpen", False),
                    "session": data.get("session"),  # pre-market, regular, post-market, or null
                    "holiday": data.get("holiday"),  # Holiday name if applicable
                    "timestamp": data.get("t", int(now)),
                    "source": "finnhub"
                }
                
                # Map session to display status
                if data.get("session") == "pre-market":
                    result["status"] = "PRE MARKET"
                elif data.get("session") == "regular" and data.get("isOpen"):
                    result["status"] = "OPEN"
                elif data.get("session") == "post-market":
                    result["status"] = "AFTER MARKET"
                elif data.get("holiday"):
                    result["status"] = "HOLIDAY"
                else:
                    # Check for weekend
                    tz_eastern = pytz.timezone('US/Eastern')
                    now_et = datetime.now(tz_eastern)
                    if now_et.weekday() >= 5:
                        result["status"] = "WEEKEND"
                    else:
                        result["status"] = "CLOSED"
                
                MARKET_STATUS_CACHE["data"] = result
                MARKET_STATUS_CACHE["timestamp"] = now
                print(f"📊 Finnhub Market Status: {result['status']}")
                return jsonify(result)
    except Exception as e:
        print(f"⚠️ Finnhub Market Status Error: {e}")
    
    # Fallback: Calculate based on time
    tz_eastern = pytz.timezone('US/Eastern')
    now_et = datetime.now(tz_eastern)
    current_minutes = now_et.hour * 60 + now_et.minute
    
    market_open = 9 * 60 + 30  # 9:30 AM
    market_close = 16 * 60     # 4:00 PM
    pre_market_start = 4 * 60  # 4:00 AM
    post_market_end = 20 * 60  # 8:00 PM
    
    is_weekend = now_et.weekday() >= 5
    
    if is_weekend:
        status = "WEEKEND"
        session = None
        is_open = False
    elif current_minutes >= market_open and current_minutes < market_close:
        status = "OPEN"
        session = "regular"
        is_open = True
    elif current_minutes >= pre_market_start and current_minutes < market_open:
        status = "PRE MARKET"
        session = "pre-market"
        is_open = False
    elif current_minutes >= market_close and current_minutes < post_market_end:
        status = "AFTER MARKET"
        session = "post-market"
        is_open = False
    else:
        status = "CLOSED"
        session = None
        is_open = False
    
    result = {
        "isOpen": is_open,
        "session": session,
        "status": status,
        "holiday": None,
        "timestamp": int(now),
        "source": "calculated"
    }
    
    MARKET_STATUS_CACHE["data"] = result
    MARKET_STATUS_CACHE["timestamp"] = now
    return jsonify(result)

@app.route('/api/debug/system')
def api_debug_system():
    """
    Debug endpoint to check server time, IP, and connectivity.
    """
    try:
        import socket
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
    except:
        hostname = "unknown"
        ip_address = "unknown"
        
    tz_eastern = pytz.timezone('US/Eastern')
    now_utc = datetime.now(pytz.utc)
    now_eastern = datetime.now(tz_eastern)
    
    # Test Connectivity to Yahoo Finance
    yf_status = "unknown"
    yf_error = None
    sample_data = None
    
    try:
        # Try to fetch SPY info
        ticker = yf.Ticker("SPY")
        # fast_info triggers the request
        price = ticker.fast_info.last_price
        yf_status = "ok"
        sample_data = {"symbol": "SPY", "price": price}
    except Exception as e:
        yf_status = "error"
        yf_error = str(e)
        
    return jsonify({
        "server_time_utc": str(now_utc),
        "server_time_eastern": str(now_eastern),
        "hostname": hostname,
        "ip_address": ip_address, # Internal IP
        "yfinance_status": yf_status,
        "yfinance_error": yf_error,
        "sample_data": sample_data
    })

@app.route('/api/debug/news')
def api_debug_news():
    global CACHE
    data = CACHE.get("news", {})
    news_items = data.get("data", [])
    
    return jsonify({
        "timestamp": data.get("timestamp", 0),
        "timestamp_human": datetime.fromtimestamp(data.get("timestamp", 0)).strftime('%Y-%m-%d %H:%M:%S'),
        "item_count": len(news_items),
        "sample_item": news_items[0] if news_items else None,
        "last_error": data.get("last_error", None),
        "server_time": time.time()
    })


@app.route('/api/heatmap')
def api_heatmap():
    global CACHE
    if CACHE["heatmap"]["timestamp"] == 0:
        return jsonify({"loading": True, "data": []})
    return jsonify(CACHE["heatmap"]["data"])



def start_background_worker():
    def hydrate_on_startup():

        # Check if market is closed (skip heavy whale fetching on weekends)
        tz_eastern = pytz.timezone('US/Eastern')
        now_et = datetime.now(tz_eastern)
        is_weekend = now_et.weekday() >= 5
        is_market_hours = 4 <= now_et.hour < 20  # Extended hours: 4am-8pm
        
        if is_weekend:
            print("📅 Weekend - skipping whale fetch (using cached data)")
            print(f"   Cached whale trades available: {len(CACHE.get('whales', {}).get('data', []))}")
        elif not is_market_hours:
            print("🌙 Market closed - minimal startup (using cached data)")
        else:
            # Market hours - warm price cache, whale scan runs via main worker loop
            print("📈 Market hours - warming price cache...")
            for symbol in WHALE_WATCHLIST[:5]:
                try:
                    get_cached_price(symbol)
                except Exception as e:
                    print(f"Startup Price Cache Error ({symbol}): {e}")
        
        # 2. Fetch Gamma & Heatmap (lightweight on weekends) - WITH TIMEOUT
        # 2. Fetch Gamma & Heatmap & News - WITH RETRY & ROBUST TIMEOUT
        def retry_fetch(func, name, retries=3):
            for i in range(retries):
                try:
                    print(f"🔄 Hydrating {name} (Attempt {i+1}/{retries})...")
                    # DIRECT CALL - No with_timeout to prevent deadlock
                    func()
                    # Check if data actually populated
                    if name == "News" and not CACHE.get("news", {}).get("data"):
                        raise Exception("News data still empty after fetch")
                    if name == "Heatmap" and not CACHE.get("heatmap", {}).get("data"):
                        raise Exception("Heatmap data still empty after fetch")
                        
                    print(f"✅ {name} Hydrated!")
                    return
                except Exception as e:
                    print(f"⚠️ {name} Hydration Failed (Attempt {i+1}): {e}")
                    time.sleep(2) # Wait a bit before retry
            print(f"❌ {name} Hydration GAVE UP after {retries} attempts.")

        # retry_fetch(refresh_gamma_logic, "Gamma")
        # retry_fetch(refresh_heatmap_logic, "Heatmap")
        # retry_fetch(refresh_news_logic, "News")
        

    def worker():
        # Run Hydration ONCE on startup (Background)
        try:
            hydrate_on_startup()
        except Exception as e:
            print(f"⚠️ Hydration Failed: {e}", flush=True)
        

        
        last_gamma_update = 0
        last_heatmap_update = 0
        last_news_update = 0
        last_snapshot_save = 0 # Track day of last save
        
        while True:
            # === MARKET HOURS CHECK ===
            tz_eastern = pytz.timezone('US/Eastern')
            now = datetime.now(tz_eastern)
            
            # Market Hours: 9:30 AM - 4:00 PM ET, Mon-Fri
            is_weekday = now.weekday() < 5
            is_weekend = not is_weekday
            # Extended Hours for Heatmap/News: 4:00 AM - 8:00 PM ET (Weekdays)
            is_extended_hours = (is_weekday and (
                (now.hour > 4 or (now.hour == 4 and now.minute >= 0)) and 
                (now.hour < 20)
            ))
            # Core Market Hours for Options (Whales/Gamma): 9:30 AM - 4:15 PM ET (ETFs trade til 4:15)
            is_market_open = is_weekday and (
                (now.hour > 9 or (now.hour == 9 and now.minute >= 30)) and 
                (now.hour < 16 or (now.hour == 16 and now.minute < 15))
            )
            
            # Daily Snapshot Save Trigger (4:30 PM ET)
            # Check if it's a weekday, time is past 16:30, and we haven't saved today
            today_date_str = now.strftime("%Y-%m-%d")
            last_save_date_str = datetime.fromtimestamp(last_snapshot_save, tz=tz_eastern).strftime("%Y-%m-%d") if last_snapshot_save > 0 else ""
            
            if is_weekday and now.hour == 16 and now.minute >= 30:
                if today_date_str != last_save_date_str:
                    print(f"⏰ Triggering Daily Snapshot Save for {today_date_str}...")
                    try:
                        whales_service.save_daily_snapshot()
                        last_snapshot_save = time.time()
                    except Exception as e:
                        print(f"❌ Scheduler Snapshot Error: {e}")
            
            # News Slowdown: After 9 PM ET or Weekends
            is_late_night = now.hour >= 21 or now.hour < 4
            is_slow_news_time = (not is_weekday) or is_late_night

            # 1. Heatmap (Runs in Extended Hours OR if cache is empty)
            # Core Hours: 30 mins (1800s) | Extended Hours: 30 mins (1800s)
            heatmap_interval = 1800
            
            # Force hydration if cache is empty (e.g. server restart at night/weekend)
            heatmap_needs_hydration = not CACHE.get("heatmap", {}).get("data")
            
            # LOGIC FIX: If we need hydration, run it regardless of hours!
            should_run_heatmap = is_extended_hours or heatmap_needs_hydration
            
            if should_run_heatmap and (time.time() - last_heatmap_update > heatmap_interval):
                try: 
                    # DIRECT CALL - Internal with_timeout handles yfinance hanging
                    refresh_heatmap_logic()
                    last_heatmap_update = time.time()
                except Exception as e: print(f"Worker Error (Heatmap): {e}")
                time.sleep(0.2)  # Polygon: unlimited API - faster polling
            
            # 2. News (Always Runs, but slower at night)
            # Normal: 5 mins (300s) | Slow: 15 mins (900s)
            news_interval = 900 if is_slow_news_time else 300
            
            # Force hydration if cache is empty
            news_needs_hydration = not CACHE.get("news", {}).get("data")
            should_run_news = news_needs_hydration or (time.time() - last_news_update > news_interval)
            
            if should_run_news:
                    try: 
                        # DIRECT CALL - Has internal ThreadPool
                        refresh_news_logic()
                        # Check if we actually got news
                        news_data = CACHE.get("news", {}).get("data", [])
                        if news_data:
                            last_news_update = time.time()
                        else:
                            print("⚠️ News Fetch Empty - Retrying in 60s", flush=True)
                            last_news_update = time.time() - (news_interval - 60)
                    except Exception as e: 
                        print(f"Worker Error (News): {e}")
                        last_news_update = time.time() - (news_interval - 60)
                
            # 3. Gamma (Market Hours OR Empty Cache) - THROTTLED TO 2 MINS (was 5)
            # If cache is empty (server restart), we MUST fetch data even if closed
            gamma_needs_hydration = not CACHE.get("gamma_SPY", {}).get("data")
            
            if (is_market_open or gamma_needs_hydration) and (time.time() - last_gamma_update > 120):
                try: 
                    # DIRECT CALL - Requests have timeouts
                    refresh_gamma_logic()
                    last_gamma_update = time.time()
                except Exception as e: print(f"Worker Error (Gamma): {e}")
                time.sleep(0.2)  # Polygon: unlimited API - faster polling
            
            # 4. Whales (Market Hours Only - No hydration after hours, Finnhub won't return data)
            # Hydration only during extended hours (4 AM - 8 PM) when there's actual trading activity
            # UPDATE: Allow hydration if cache is empty, even on weekends (to show Friday's data)
            # BYPASS: Always scan during extended hours (until 8 PM) to show late prints
            whales_needs_hydration = not CACHE.get("whales", {}).get("data")
            can_hydrate_whales = is_extended_hours or (whales_needs_hydration and is_weekend)
            
            # 4. Whales - REST Polling (Expanded View)
            # Run this loop to populate CACHE["whales_rest"]
            rest_needs_hydration = not CACHE.get("whales_rest", {}).get("data")
            
            if can_hydrate_whales or rest_needs_hydration:
                 # Cycle through watchlist
                 # for symbol in WHALE_WATCHLIST:
                 #     refresh_single_whale_polygon(symbol)
                 #     time.sleep(1) # Pace API calls
                 pass

            time.sleep(60)

    t = threading.Thread(target=worker, daemon=True)
    t.start()

# Start the background worker immediately on import
# Guard ensures it only runs once even if module is imported multiple times
if not hasattr(start_background_worker, '_started'):
    # load_whale_cache() handled by setup_whales
    whales_service.mark_whale_cache_cleared()  # Mark this session's start time
    start_background_worker()  # Enabled for local dev (production uses gunicorn_config.py)
    start_background_worker._started = True




# Setup Whales Service
whales_service.setup_whales(app, CACHE, POLYGON_API_KEY, firestore_db, WHALE_WATCHLIST, get_cached_price, get_finnhub_price)

if __name__ == "__main__":
    # Background worker is already started at module level (line 4795)
    # start_background_worker()
    
    # Polygon WebSocket disabled - using REST snapshot polling instead
    # (Polygon only allows 1 WS connection per asset class, production uses it)
    # start_polygon_ws_thread()
    
    port = int(os.environ.get('PORT', 8001))
    print(f"🚀 PigmentOS Server running on port {port}")
    # Disable debug mode for stability
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
