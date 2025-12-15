from gevent import monkey
monkey.patch_all()

import json
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

import ssl
import calendar
from datetime import datetime, date
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

# Watchlist for "Whale" Scan
WATCHLIST = [
    "NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META", "GOOGL",
    "AMD", "AVGO", "ARM", "SMCI", "MU", "INTC",
    "PLTR", "SOFI", "RKLB",
    "SPY", "QQQ", "IWM"
]

MEGA_WHALE_THRESHOLD = 8_000_000  # $8M

# Cache structure
CACHE_DURATION = 120 # 2 minutes (was 300)
MACRO_CACHE_DURATION = 120 # 2 minutes (was 300)
CACHE_LOCK = threading.Lock()
POLY_STATE = {}

CACHE = {
    "whales": {"data": [], "timestamp": 0},
    "vix": {"data": {"value": 0, "rating": "Neutral"}, "timestamp": 0},
    "cnn_fear_greed": {"data": {"value": 50, "rating": "Neutral"}, "timestamp": 0},
    "polymarket": {"data": [], "timestamp": 0, "is_mock": False},
    "movers": {"data": [], "timestamp": 0},
    "movers": {"data": [], "timestamp": 0},
    "news": {"data": [], "timestamp": 0},
    "heatmap": {"data": [], "timestamp": 0},
    "gamma_SPY": {"data": None, "timestamp": 0}
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
    'NVDA', 'TSLA', 'SPY', 'QQQ', 'AAPL', 'AMD', 'MSFT', 'AMZN', 
    'GOOGL', 'GOOG', 'META', 'PLTR', 'MU', 'NBIS'
]

# MarketData.app API Token (for enhanced options data)
MARKETDATA_TOKEN = os.environ.get("MARKETDATA_TOKEN")
# Rate limit tracking for MarketData.app
MARKETDATA_LAST_REQUEST = 0
MARKETDATA_MIN_INTERVAL = 0.25  # 250ms between requests

# Polygon.io API Key (primary options data source - unlimited calls)
POLYGON_API_KEY = os.environ.get("POLYGON_API_KEY")

# Price cache to reduce redundant API calls (TTL: 60 seconds)
PRICE_CACHE = {}  # {symbol: {"price": float, "timestamp": float}}
PRICE_CACHE_TTL = 60  # seconds

# === WHALE CACHE PERSISTENCE ===
WHALE_CACHE_FILE = "/tmp/pigmentos_whale_cache.json"
WHALE_CACHE_LAST_CLEAR = 0  # Track when we last cleared

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
                CACHE["whales"]["data"] = data.get("whales", [])
                CACHE["whales"]["timestamp"] = data.get("timestamp", 0)
            WHALE_CACHE_LAST_CLEAR = data.get("last_clear", 0)
            print(f"📂 Loaded {len(data.get('whales', []))} whale trades from cache")
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

def get_cached_price(symbol):
    """Get price from cache or fetch from Polygon if stale/missing."""
    global PRICE_CACHE
    
    now = time.time()
    
    # Check cache
    if symbol in PRICE_CACHE:
        cached = PRICE_CACHE[symbol]
        if now - cached["timestamp"] < PRICE_CACHE_TTL:
            return cached["price"]
    
    # Fetch from Polygon
    if not POLYGON_API_KEY:
        return None
    
    try:
        # Use Snapshot API for real-time price (includes pre-market/after-hours)
        price_url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}"
        price_resp = requests.get(price_url, params={"apiKey": POLYGON_API_KEY}, timeout=5)
        
        if price_resp.status_code == 200:
            price_data = price_resp.json()
            # Snapshot response structure: { ticker: { lastTrade: { p: ... }, ... } }
            if price_data.get("ticker"):
                ticker_data = price_data["ticker"]
                # Try lastTrade first (most recent), then min (minute bar), then day (daily bar), then prevDay
                price = None
                if ticker_data.get("lastTrade"):
                    price = ticker_data["lastTrade"].get("p")
                elif ticker_data.get("min"):
                    price = ticker_data["min"].get("c")
                elif ticker_data.get("day"):
                    price = ticker_data["day"].get("c")
                elif ticker_data.get("prevDay"):
                    price = ticker_data["prevDay"].get("c")
                
                if price:
                    PRICE_CACHE[symbol] = {"price": price, "timestamp": now}
                    return price
        else:
            # Fallback to Previous Close if Snapshot fails
            print(f"Snapshot failed for {symbol}, trying prev close...")
            price_url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/prev"
            price_resp = requests.get(price_url, params={"apiKey": POLYGON_API_KEY}, timeout=5)
            
            if price_resp.status_code == 200:
                price_data = price_resp.json()
                if price_data.get("results"):
                    price = price_data["results"][0].get("c", 0)
                    if price:
                        PRICE_CACHE[symbol] = {"price": price, "timestamp": now}
                        return price

            # Rate limited or error - return cached if available (even if stale)
            if symbol in PRICE_CACHE:
                return PRICE_CACHE[symbol]["price"]
    except Exception as e:
        print(f"Price fetch error ({symbol}): {e}")
        if symbol in PRICE_CACHE:
            return PRICE_CACHE[symbol]["price"]
    
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
        # Get current price from cache (shared with whale detection)
        from datetime import timedelta
        
        current_price = get_cached_price(symbol)
        
        if not current_price:
            print(f"Polygon: Could not get price for {symbol}, skipping gamma fetch")
            return None
        
        # Calculate strike range (±20% of current price - focused on ATM action)
        strike_low = int(current_price * 0.80)
        strike_high = int(current_price * 1.20)
        
        # Smart expiration selection for SPY/QQQ/IWM/DIA:
        # - Weekend: use Monday
        # - Pre-market (4am-9:30am): use TODAY (plan for today)
        # - Market hours (9:30am-4pm): use TODAY (0DTE)
        # - Post-market (4pm-8pm): use TOMORROW (preview next day)
        # Other tickers always use next Friday
        tz_eastern = pytz.timezone('US/Eastern')
        now_et = datetime.now(tz_eastern)
        today_weekday = now_et.weekday()  # 0=Mon, 4=Fri, 5=Sat, 6=Sun
        
        pre_market_start = now_et.replace(hour=4, minute=0, second=0, microsecond=0)
        market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
        post_market_end = now_et.replace(hour=20, minute=0, second=0, microsecond=0)
        
        is_weekend = today_weekday >= 5
        is_pre_market = pre_market_start <= now_et < market_open
        is_market_hours = market_open <= now_et <= market_close
        is_post_market = market_close < now_et <= post_market_end
        
        # Tickers with daily expirations (0DTE available)
        daily_expiry_tickers = ['SPY', 'QQQ', 'IWM', 'DIA']
        has_daily = symbol.upper() in daily_expiry_tickers
        
        if is_weekend:
            if has_daily:
                # Weekend + daily ticker: use next Monday (Polygon has Monday options ready)
                days_until_monday = (7 - today_weekday) % 7
                if days_until_monday == 0:
                    days_until_monday = 1
                expiry_date = (now_et + timedelta(days=days_until_monday)).strftime("%Y-%m-%d")
                print(f"Polygon: Weekend - using Monday {expiry_date} for {symbol}")
            else:
                # Weekend + non-daily ticker: use next Friday
                days_until_friday = (4 - today_weekday + 7) % 7
                if days_until_friday == 0:
                    days_until_friday = 7
                expiry_date = (now_et + timedelta(days=days_until_friday)).strftime("%Y-%m-%d")
                print(f"Polygon: Weekend - using Friday {expiry_date} for {symbol}")
        elif has_daily:
            if is_pre_market or is_market_hours:
                # Pre-market or market hours: use TODAY
                expiry_date = now_et.strftime("%Y-%m-%d")
                mode = "0DTE" if is_market_hours else "Pre-market"
                print(f"Polygon: {mode} - using today {expiry_date} for {symbol}")
            elif is_post_market:
                # Post-market: use TOMORROW (or Monday if Friday)
                if today_weekday == 4:  # Friday
                    days_ahead = 3  # Skip to Monday
                else:
                    days_ahead = 1
                expiry_date = (now_et + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
                print(f"Polygon: Post-market - using tomorrow {expiry_date} for {symbol}")
            else:
                # Late night / early morning: use next trading day
                expiry_date = now_et.strftime("%Y-%m-%d")
                print(f"Polygon: Off-hours - using today {expiry_date} for {symbol}")
        else:
            # Non-daily tickers: always use next Friday
            days_until_friday = (4 - today_weekday) % 7
            if days_until_friday == 0 and now_et.hour >= 16:
                days_until_friday = 7
            expiry_date = (now_et + timedelta(days=days_until_friday)).strftime("%Y-%m-%d")
            print(f"Polygon: Using Friday {expiry_date} for {symbol}")
        
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
            gamma_data[strike] = {"call_vol": 0, "put_vol": 0, "call_oi": 0, "put_oi": 0, "call_premium": 0, "put_premium": 0}
        
        day_data = contract.get("day", {})
        vol = int(day_data.get("volume", 0) or 0)
        oi = int(contract.get("open_interest", 0) or 0)
        price = float(day_data.get("close", 0) or day_data.get("vwap", 0) or 0)  # Contract price
        
        if side == "call":
            gamma_data[strike]["call_vol"] += vol
            gamma_data[strike]["call_oi"] += oi
            gamma_data[strike]["call_premium"] = max(gamma_data[strike]["call_premium"], price)  # Track highest premium
        else:
            gamma_data[strike]["put_vol"] += vol
            gamma_data[strike]["put_oi"] += oi
            gamma_data[strike]["put_premium"] = max(gamma_data[strike]["put_premium"], price)
    
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
        
        # Get current price from cache (reduces API calls)
        current_price = get_cached_price(symbol)
        
        if not current_price:
            print(f"Polygon: Could not get price for {symbol}, skipping whale scan")
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


def refresh_single_whale_polygon(symbol):
    """
    Fetch unusual options activity for a single ticker using Polygon.io.
    Drop-in replacement for yfinance version with same output format.
    """
    global CACHE, WHALE_HISTORY
    
    tz_eastern = pytz.timezone('US/Eastern')
    now_et = datetime.now(tz_eastern)
    
    def format_money(val):
        if val >= 1_000_000: return f"${val/1_000_000:.1f}M"
        if val >= 1_000: return f"${val/1_000:.0f}k"
        return f"${val:.0f}"
    
    # Check for daily reset (if server runs overnight)
    global WHALE_CACHE_LAST_CLEAR
    if should_clear_whale_cache(WHALE_CACHE_LAST_CLEAR):
        print("🧹 Clearing stale whale history (new trading day)")
        WHALE_HISTORY.clear()
        mark_whale_cache_cleared()
    
    new_whales = []
    
    try:
        polygon_data = fetch_unusual_options_polygon(symbol)
        
        if not polygon_data or not polygon_data.get("results"):
            print(f"Polygon: No data for {symbol}, skipping")
            return
        
        current_price = polygon_data.get("_current_price", 0)
        
        # Thresholds (same as yfinance version)
        vol_oi_multiplier = 4 if symbol.upper() in ['SPY', 'QQQ', 'IWM'] else 3
        min_whale_val = 5_000_000 if symbol.upper() in ['SPY', 'QQQ', 'IWM'] else 500_000
        
        for contract in polygon_data.get("results", []):
            details = contract.get("details", {})
            day_data = contract.get("day", {})
            greeks = contract.get("greeks", {})
            
            volume = int(day_data.get("volume", 0) or 0)
            open_interest = int(contract.get("open_interest", 0) or 0)
            last_price = float(day_data.get("close", 0) or 0)
            strike = float(details.get("strike_price", 0))
            contract_type = details.get("contract_type", "").upper()  # "CALL" or "PUT"
            expiry = details.get("expiration_date", "")
            ticker_symbol = details.get("ticker", "")
            
            # Skip if no volume
            if volume == 0 or last_price == 0:
                continue
            
            # Calculate premium (notional value)
            notional = volume * last_price * 100
            
            # Vol/OI ratio - KEY indicator of unusual activity
            vol_oi_ratio = volume / open_interest if open_interest > 0 else 999
            
            # INDUSTRY-STANDARD FILTERS (aligned with Unusual Whales, Cheddar Flow)
            # 1. Vol/OI > 1.05 = Fresh positioning exceeds existing open interest
            # 2. Premium > $100,000 = Institutional-size trade (not retail)
            # 3. Volume > 500 = Block-level contract count
            # 4. DTE <= 7 = Short-term conviction (industry standard for flow detection)
            
            is_unusual = vol_oi_ratio > 1.05
            is_significant_premium = notional >= 100_000
            is_meaningful_volume = volume >= 500
            
            # Calculate DTE (Days to Expiration)
            try:
                exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
                dte = (exp_date - now_et.date()).days
                is_short_term = 0 <= dte <= 7
            except:
                is_short_term = False
            
            # Must pass ALL criteria to be "unusual"
            if not (is_unusual and is_significant_premium and is_meaningful_volume and is_short_term):
                continue
            
            # Moneyness calculation
            is_call = contract_type == "CALL"
            if is_call:
                moneyness = "ITM" if current_price > strike else "OTM"
            else:
                moneyness = "ITM" if current_price < strike else "OTM"
            
            # Get delta from Greeks
            delta_val = greeks.get("delta", 0) or 0
            iv_val = contract.get("implied_volatility", 0) or 0
            
            # Trade time (from last_updated)
            last_updated = day_data.get("last_updated", 0)
            if last_updated:
                trade_time_obj = datetime.fromtimestamp(last_updated / 1_000_000_000, tz=tz_eastern)
                
                # CRITICAL: Filter out stale trades from previous days
                # At 9:30 AM, we only want TODAY's trades
                if trade_time_obj.date() != now_et.date():
                    continue
                    
                trade_time_str = trade_time_obj.strftime("%H:%M:%S")
                timestamp_val = trade_time_obj.timestamp()
            else:
                # If no timestamp, skip it to be safe (or assume now? No, safe is better)
                continue
            
            # Volume tracking (same as yfinance version)
            contract_id = ticker_symbol
            current_vol = volume
            last_vol = WHALE_HISTORY.get(contract_id, 0)
            delta = current_vol - last_vol
            
            whale_data = {
                "baseSymbol": symbol,
                "symbol": ticker_symbol,
                "strikePrice": strike,
                "expirationDate": expiry,
                "putCall": 'C' if is_call else 'P',
                "openInterest": open_interest,
                "lastPrice": last_price,
                "tradeTime": trade_time_str,
                "timestamp": timestamp_val,
                "vol_oi": round(vol_oi_ratio, 1),
                "premium": format_money(notional),
                "notional_value": notional,
                "moneyness": moneyness,
                "is_mega_whale": notional > MEGA_WHALE_THRESHOLD,
                "delta": round(delta_val, 2),
                "iv": round(iv_val, 2),
                "source": "polygon"
            }
            
            if last_vol == 0 or delta >= VOLUME_THRESHOLD:
                WHALE_HISTORY[contract_id] = current_vol
                whale_data["volume"] = current_vol
                new_whales.append(whale_data)
        
        # Update cache
        with CACHE_LOCK:
            current_data = CACHE["whales"]["data"]
            other_data = [w for w in current_data if w['baseSymbol'] != symbol]
            updated_data = other_data + new_whales
            updated_data.sort(key=lambda x: x['timestamp'], reverse=True)
            # Keep only top 50 trades for a clean feed
            CACHE["whales"]["data"] = updated_data[:100]
            CACHE["whales"]["timestamp"] = time.time()
        
        if new_whales:
            print(f"Polygon Whales: {len(new_whales)} unusual trades for {symbol} (cache: {len(CACHE['whales']['data'])})")
            save_whale_cache()  # Persist to file
        
    except Exception as e:
        print(f"Polygon Whale Scan Failed ({symbol}): {e}")

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
    Uses Polygon.io if API key is set, otherwise falls back to yfinance.
    """
    global CACHE
    
    # Use Polygon if available (preferred - unlimited API calls, includes Greeks)
    if POLYGON_API_KEY:
        refresh_single_whale_polygon(symbol)
        return
    
    # Fallback to yfinance if no Polygon key
    tz_eastern = pytz.timezone('US/Eastern')
    today_date = datetime.now(tz_eastern).date()
    
    def format_money(val):
        if val >= 1_000_000: return f"${val/1_000_000:.1f}M"
        if val >= 1_000: return f"${val/1_000:.0f}k"
        return f"${val:.0f}"
    
    new_whales = []
    
    try:
        ticker = yf.Ticker(symbol)
        
        try:
            current_price = ticker.fast_info.last_price
        except:
            current_price = ticker.info.get('regularMarketPrice', 0)
        
        if not current_price: return

        expirations = ticker.options
        if not expirations: return
            
        target_expirations = expirations[:2]
        
        for expiry in target_expirations:
            try:
                if symbol in ['SPY', 'QQQ', 'IWM']:
                    expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
                    if expiry_date <= today_date:
                        continue

                opts = ticker.option_chain(expiry)
                calls = opts.calls; calls['type'] = 'CALL'
                puts = opts.puts; puts['type'] = 'PUT'
                chain = pd.concat([calls, puts])
                
                vol_oi_multiplier = 4 if symbol in ['SPY', 'QQQ', 'IWM'] else 3
                unusual = chain[
                    (chain['volume'] > (chain['openInterest'] * vol_oi_multiplier)) & 
                    (chain['volume'] > 500) & 
                    (chain['lastPrice'] > 0.10)
                ]
                
                for _, row in unusual.iterrows():
                    notional = row['volume'] * row['lastPrice'] * 100
                    
                    min_whale_val = 500_000
                    if symbol in ['SPY', 'QQQ', 'IWM']: min_whale_val = 5_000_000
                        
                    if notional < min_whale_val: continue

                    trade_ts = row['lastTradeDate']
                    if trade_ts.tzinfo is None: trade_ts = pytz.utc.localize(trade_ts)
                    
                    if trade_ts.astimezone(tz_eastern).date() != today_date:
                        continue
                    
                    strike = float(row['strike'])
                    is_call = row['type'] == 'CALL'
                    
                    price_diff_pct = abs(strike - current_price) / current_price
                    if price_diff_pct > 0.10:
                        continue
                    
                    moneyness = "ITM" if (is_call and current_price > strike) or (not is_call and current_price < strike) else "OTM"
                    
                    trade_time_obj = row['lastTradeDate']
                    if hasattr(trade_time_obj, 'strftime'):
                        trade_time_str = trade_time_obj.strftime("%H:%M:%S")
                        timestamp_val = trade_time_obj.timestamp()
                    else:
                        trade_time_str = str(trade_time_obj)
                        timestamp_val = time.time()

                    contract_id = row['contractSymbol']
                    current_vol = int(row['volume'])
                    last_vol = WHALE_HISTORY.get(contract_id, 0)
                    delta = current_vol - last_vol
                    
                    whale_data = {
                        "baseSymbol": symbol,
                        "symbol": row['contractSymbol'],
                        "strikePrice": strike,
                        "expirationDate": expiry,
                        "putCall": 'C' if is_call else 'P',
                        "openInterest": int(row['openInterest']),
                        "lastPrice": float(row['lastPrice']),
                        "tradeTime": trade_time_str,
                        "timestamp": timestamp_val,
                        "vol_oi": round(row['volume'] / (row['openInterest'] if row['openInterest'] > 0 else 1), 1),
                        "premium": format_money(notional),
                        "notional_value": notional,
                        "moneyness": moneyness, 
                        "is_mega_whale": notional > MEGA_WHALE_THRESHOLD,
                        "delta": 0,
                        "iv": row['impliedVolatility']
                    }

                    if last_vol == 0 or delta >= VOLUME_THRESHOLD:
                        WHALE_HISTORY[contract_id] = current_vol
                        whale_data["volume"] = current_vol
                        new_whales.append(whale_data)
                    else:
                        whale_data["volume"] = last_vol
                        whale_data["premium"] = format_money(last_vol * row['lastPrice'] * 100)
                        whale_data["notional_value"] = last_vol * row['lastPrice'] * 100
                        whale_data["is_mega_whale"] = whale_data["notional_value"] > MEGA_WHALE_THRESHOLD
                        new_whales.append(whale_data)

            except Exception: continue

        with CACHE_LOCK:
            current_data = CACHE["whales"]["data"]
            other_data = [w for w in current_data if w['baseSymbol'] != symbol]
            updated_data = other_data + new_whales
            updated_data.sort(key=lambda x: x['timestamp'], reverse=True)
            CACHE["whales"]["data"] = updated_data
            CACHE["whales"]["timestamp"] = time.time()

    except Exception as e:
        print(f"Whale Scan Failed ({symbol}): {e}")

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
        tickers_obj = yf.Tickers(" ".join(HEATMAP_TICKERS.keys()))
        
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
@limiter.limit("10 per minute")
def subscription_status():
    """Check if user has active subscription or valid trial - SERVER-SIDE VERIFIED"""
    try:
        # 1. VERIFY FIREBASE TOKEN (don't trust client-sent email)
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
        
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
        
        # 2. FETCH TRIAL DATE FROM FIRESTORE (don't trust client-sent date)
        trial_start_date = None
        if firestore_db:
            try:
                user_doc = firestore_db.collection('users').document(user_uid).get()
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    trial_start_ts = user_data.get('trialStartDate')
                    subscription_status_db = user_data.get('subscriptionStatus', 'trialing')
                    
                    # If already marked as active in Firestore, trust it
                    if subscription_status_db == 'active':
                        return jsonify({
                            'status': 'active',
                            'has_access': True
                        })
                    
                    # If marked as expired or past_due
                    if subscription_status_db in ['expired', 'past_due']:
                        # Double-check with Stripe
                        customers = stripe.Customer.list(email=user_email, limit=1)
                        if customers.data:
                            subscriptions = stripe.Subscription.list(customer=customers.data[0].id, status='active', limit=1)
                            if subscriptions.data:
                                return jsonify({'status': 'active', 'has_access': True})
                        return jsonify({'status': 'expired', 'has_access': False})
                    
                    # Convert Firestore timestamp to datetime
                    if trial_start_ts:
                        trial_start_date = trial_start_ts
            except Exception as db_error:
                print(f"Firestore lookup error: {db_error}")
        
        if not trial_start_date:
            # New user, trial just started
            return jsonify({
                'status': 'trialing',
                'days_remaining': TRIAL_DAYS,
                'has_access': True
            })
        
        # 3. CALCULATE TRIAL EXPIRATION
        from datetime import datetime, timedelta
        
        # Handle Firestore Timestamp
        if hasattr(trial_start_date, 'timestamp'):
            trial_start = datetime.fromtimestamp(trial_start_date.timestamp(), tz=pytz.UTC)
        else:
            trial_start = trial_start_date
            
        trial_end = trial_start + timedelta(days=TRIAL_DAYS)
        now = datetime.now(pytz.UTC)
        days_remaining = (trial_end - now).days
        
        if days_remaining > 0:
            return jsonify({
                'status': 'trialing',
                'days_remaining': days_remaining,
                'has_access': True
            })
        
        # 4. TRIAL EXPIRED - CHECK STRIPE
        customers = stripe.Customer.list(email=user_email, limit=1)
        if customers.data:
            customer = customers.data[0]
            subscriptions = stripe.Subscription.list(customer=customer.id, status='active', limit=1)
            if subscriptions.data:
                return jsonify({
                    'status': 'active',
                    'has_access': True
                })
        
        return jsonify({
            'status': 'expired',
            'has_access': False
        })
        
    except Exception as e:
        print(f"Subscription status error: {e}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/stripe-webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events to update Firestore subscription status"""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    
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
    
    elif event_type == 'invoice.payment_failed':
        # Handle failed payment - mark as past_due
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
                    print(f"⚠️ Payment failed for {customer_email}: subscriptionStatus = past_due")
                    break
        except Exception as e:
            print(f"❌ Payment failed handling error: {e}")
    
    return jsonify({'status': 'success'}), 200

@app.route('/api/whales')
def api_whales():
    from datetime import timedelta
    global CACHE
    limit = int(request.args.get('limit', 25))
    offset = int(request.args.get('offset', 0))
    
    # Check if data has been hydrated
    if CACHE["whales"]["timestamp"] == 0:
        return jsonify({"loading": True, "data": [], "stale": False, "timestamp": 0})
    
    # FILTER: Ensure we only show TODAY'S trades (Server-side safety)
    # The worker might be sleeping (Pre-market), holding yesterday's data.
    # We filter it here to ensure the frontend sees a clean slate.
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
            clean_data.append(whale)
            
    sliced = clean_data[offset:offset+limit]
    
    return jsonify({
        "data": sliced,
        "stale": False,
        "timestamp": int(CACHE["whales"]["timestamp"])
    })

@app.route('/api/whales/stream')
def api_whales_stream():
    def generate():

        # Initial Data
        current_time = time.time()
        # Just yield the cache periodically
        while True:
            # Send immediately on connect
            data = CACHE["whales"]["data"]
            yield f"data: {json.dumps({'data': data, 'stale': False, 'timestamp': int(CACHE['whales']['timestamp'])})}\n\n"
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

@app.route('/api/polymarket')
def api_polymarket():
    global CACHE, POLY_STATE
    current_time = time.time()
    
    if current_time - CACHE["polymarket"]["timestamp"] < CACHE_DURATION:
        return jsonify({"data": CACHE["polymarket"]["data"], "is_mock": CACHE["polymarket"]["is_mock"]})

    try:
        # FETCH OPTIMIZATION:
        # 1. limit=200: Fetch more to allow for filtering
        # 2. order=volume24hr: Prioritize what's actually trading
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
            
            KEYWORDS = {
                "GEOPOL": ['war', 'invasion', 'strike', 'china', 'russia', 'israel', 'iran', 'taiwan', 'ukraine', 'gaza', 'border', 'military', 'ceasefire', 'capture', 'regime', 'clash', 'peace', 'khamenei', 'hezbollah', 'venezuela'],
                "MACRO": ['fed', 'rate', 'inflation', 'cpi', 'jobs', 'recession', 'gdp', 'fomc', 'powell', 'gold', 'reserve', 'ipo'],
                "CRYPTO": ['bitcoin', 'crypto', 'btc', 'eth', 'nft'],
                "TECH": ['apple', 'nvidia', 'microsoft', 'google', 'meta', 'tesla', 'amazon', 'ai', 'tech', 'openai', 'gemini'],
                "CULTURE": ['tweet', 'youtube', 'subscriber', 'mrbeast', 'logan paul', 'ksi', 'spotify', 'taylor swift', 'beyonce', 'film', 'movie', 'box office'],
                "SCIENCE": ['space', 'nasa', 'spacex', 'mars', 'moon', 'cancer', 'climate', 'temperature', 'fda', 'medicine']
            }

            BLACKLIST = ['nfl', 'nba', 'super bowl', 'sport', 'football', 'basketball', 'soccer', 'tennis', 'golf', 'searched', 'election', 'solana', 'microstrategy', 'mstr', 'zootopia', 'wicked', 'movie', 'film', 'box office', 'cinema', 'counterstrike', 'counter-strike', 'cs2', 'satoshi', 'in december']
            
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
                if any(bad in title_lower for bad in BLACKLIST): continue
                
                # 2. Filter out markets with specific times of day (e.g., "11AM ET", "7PM ET")
                # This regex matches patterns like: 11AM, 11:30AM, 7PM, 3:45PM (with optional ET/EST/PST)
                time_pattern = r'\b\d{1,2}(:\d{2})?\s*(AM|PM|am|pm)\s*(ET|EST|PST|CST)?\b'
                if re.search(time_pattern, title):
                    continue  # Skip markets with time-of-day mentions
                
                # 3. Determine Category
                category = "OTHER"
                for cat, keys in KEYWORDS.items():
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
                
                # For multi-outcome events (e.g., Fed decisions with 4+ options),
                # pick the sub-market with the HIGHEST "Yes" probability.
                # This shows the most likely outcome instead of a random low-probability one.
                if len(markets) > 1:
                    best_market = None
                    best_yes_prob = 0
                    for mkt in markets:
                        try:
                            prices = json.loads(mkt['outcomePrices']) if isinstance(mkt['outcomePrices'], str) else mkt['outcomePrices']
                            yes_prob = float(prices[0]) if prices else 0
                            if yes_prob > best_yes_prob:
                                best_yes_prob = yes_prob
                                best_market = mkt
                        except:
                            continue
                    m = best_market if best_market else markets[0]
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
                    "outcome_2_label": c['outcome_2_label'],
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

# VIX endpoint removed - not used (TFI uses Alternative.me Crypto F&G instead)

@app.route('/api/cnn-fear-greed')
def api_fear_greed():
    """Fetch Crypto Fear & Greed Index from Alternative.me"""
    global CACHE
    current_time = time.time()
    
    # Cache for 5 minutes (API updates once daily, so this is plenty)
    if current_time - CACHE["cnn_fear_greed"]["timestamp"] < 300:
        return jsonify(CACHE["cnn_fear_greed"]["data"])
        
    try:
        # Fetch from Alternative.me Crypto Fear & Greed Index
        url = "https://api.alternative.me/fng/"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        
        api_data = resp.json()
        fng_data = api_data.get("data", [{}])[0]
        
        value = int(fng_data.get("value", 50))
        classification = fng_data.get("value_classification", "Neutral")
        
        # Map to our rating format
        if value >= 75: rating = "Extreme Greed"
        elif value >= 55: rating = "Greed"
        elif value >= 45: rating = "Neutral"
        elif value >= 25: rating = "Fear"
        else: rating = "Extreme Fear"
        
        data = {
            "value": value, 
            "rating": rating, 
            "source": "Crypto F&G",
            "classification": classification
        }
        CACHE["cnn_fear_greed"] = {"data": data, "timestamp": current_time}
        return jsonify(data)
    except Exception as e:
        print(f"Crypto Fear/Greed Error: {e}")
        # Return cached data if available, else fallback
        if CACHE["cnn_fear_greed"]["data"]:
            return jsonify(CACHE["cnn_fear_greed"]["data"])
        return jsonify({"value": 50, "rating": "Neutral", "source": "Fallback"})


@app.route('/api/movers')
def api_movers():
    global CACHE
    current_time = time.time()
    
    if current_time - CACHE["movers"]["timestamp"] < 60 and CACHE["movers"]["data"]:
        return jsonify(CACHE["movers"]["data"])
    
    MOVERS_TICKERS = [
        # Mag 7 & Tech Giants
        "NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META", "GOOGL",
        
        # Semiconductors & AI
        "AMD", "INTC", "AVGO", "MU", "QCOM", "ARM", "SMCI",
        
        # FinTwit Meme Stocks & High Volume
        "PLTR", "COIN", "MSTR", "GME", "AMC", "SOFI", "HOOD", "BBBY",
        
        # Growth Tech & SaaS
        "SNOW", "DDOG", "NET", "CRWD", "ZS", "SHOP", "ROKU", "UPST",
        
        # FinTech & Payments (Removed SQ due to API errors)
        "PYPL", "AFRM",
        
        # Consumer & Entertainment
        "NFLX", "DIS", "UBER", "DASH", "ABNB", "PTON", "NKE", "SBUX",
        
        # EV & Space (High Vol)
        "RIVN", "LCID", "NIO", "RKLB",
        
        # Big Movers / Volatility
        "BA", "SNAP", "PINS", "SPOT",
        
        # Major Indices
        "SPY", "QQQ", "IWM", "DIA"
    ]
    
    try:
        movers = []
        tickers_obj = yf.Tickers(" ".join(MOVERS_TICKERS))
        
        def fetch_ticker_data(symbol):
            try:
                # Add small jitter to prevent thundering herd on API
                time.sleep(random.uniform(0.01, 0.1)) 
                
                t = tickers_obj.tickers[symbol]
                # Use fast_info for speed
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

        # Parallelize fetching but keep it safe (4 workers is conservative but faster than 1)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(fetch_ticker_data, MOVERS_TICKERS))
            
        movers = [r for r in results if r is not None]
            
        movers.sort(key=lambda x: x['change'], reverse=True)
        CACHE["movers"]["data"] = movers
        CACHE["movers"]["timestamp"] = current_time
        return jsonify(movers)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/api/news')
def api_news():
    global CACHE
    # Check if data has been hydrated (timestamp > 0 means we've fetched at least once)
    if CACHE["news"]["timestamp"] == 0:
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
    
    try:
        for url in RSS_FEEDS:
            try:

                time.sleep(1)
                
                response = requests.get(url, headers=headers, verify=False, timeout=10)

                
                if response.status_code != 200:
                    print(f"⚠️ Feed Error {url}: Status {response.status_code}", flush=True)
                    continue
                
                feed = feedparser.parse(response.content)

                
                if not feed.entries:
                    print(f"⚠️ Feed Empty {url}", flush=True)
                    continue
                
                print(f"✅ Feed Success {url}: Found {len(feed.entries)} entries", flush=True)

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
                    
                    
                    all_news.append({
                        "title": entry.get('title', ''),
                        "publisher": publisher,
                        "domain": domain,
                        "link": entry.get('link', ''),
                        "time": pub_ts,
                        "ticker": "NEWS"
                    })
            except Exception as e:
                print(f"⚠️ Feed Error {url}: {e}", flush=True)
                continue
            
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
    elif (hour > 9 or (hour == 9 and minute >= 30)) and hour < 16:
        time_period = "market"
    elif 16 <= hour < 24:
        time_period = "after_hours"
    elif 0 <= hour < 9 or (hour == 9 and minute < 30):
        time_period = "pre_market"
    
    # === PREMARKET LOGIC: Return Empty Data (Waiting for Open) ===
    # User Request: "our gamma wall should be fresh in premarket awaiting open"
    # Logic: Show empty state until 9:30 AM
    if time_period == "pre_market":
        # Still fetch price for the badge
        current_price = get_cached_price(symbol) or 0
        
        result = {
            "symbol": symbol,
            "current_price": current_price,
            "expiry": "Weekly",
            "strikes": [], # Empty list triggers "WAITING FOR OPEN"
            "time_period": time_period,
            "source": "premarket_wait"
        }
        
        cache_key = f"gamma_{symbol}"
        CACHE[cache_key] = {"data": result, "timestamp": time.time()}
        SERVICE_STATUS["GAMMA"] = {"status": "ONLINE", "last_updated": time.time()}
        print(f"Gamma: Premarket - Waiting for open (9:30 AM ET)")
        return

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
            # Just apply minimal volume filter to remove dead strikes
            MIN_VOLUME = 200  # Show only strikes with significant activity
            
            final_data = []
            for strike, data in gamma_data.items():
                # Skip strikes with zero total volume
                total_vol = data["call_vol"] + data["put_vol"]
                if total_vol < MIN_VOLUME:
                    continue
                final_data.append({
                    "strike": strike,
                    "call_vol": data["call_vol"],
                    "put_vol": data["put_vol"],
                    "call_oi": data["call_oi"],
                    "put_oi": data["put_oi"],
                    "call_premium": data.get("call_premium", 0),
                    "put_premium": data.get("put_premium", 0)
                })
            
            final_data.sort(key=lambda x: x['strike'], reverse=True)  # High → Low (pre-sorted for client)
            
            result = {
                "symbol": symbol,
                "current_price": current_price,
                "expiry": "Weekly",
                "strikes": final_data,
                "time_period": time_period,  # For smart badge display
                "source": "polygon.io"
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

@app.route('/api/ping')
def api_ping():
    return jsonify({"status": "ok", "timestamp": time.time()})

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
            # Market hours - do full whale refresh with rate limiting
            print("📈 Market hours - fetching live whale data...")
            for symbol in WHALE_WATCHLIST[:5]:  # First 5 most important on startup
                try:
                    get_cached_price(symbol)  # Warm cache
                    time.sleep(1)
                    refresh_single_whale(symbol)
                except Exception as e:
                    print(f"Startup Whale Error ({symbol}): {e}")
        
        # 2. Fetch Gamma & Heatmap (lightweight on weekends)
        try: refresh_gamma_logic()
        except: pass
        try: refresh_heatmap_logic()
        except: pass
        try: refresh_news_logic()
        except: pass
        


    def worker():
        # Run Hydration ONCE on startup (Background)
        try:
            hydrate_on_startup()
        except Exception as e:
            print(f"⚠️ Hydration Failed: {e}", flush=True)
        

        
        last_gamma_update = 0
        last_heatmap_update = 0
        last_news_update = 0
        
        while True:
            # === MARKET HOURS CHECK ===
            tz_eastern = pytz.timezone('US/Eastern')
            now = datetime.now(tz_eastern)
            
            # Market Hours: 9:30 AM - 4:00 PM ET, Mon-Fri
            is_weekday = now.weekday() < 5
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
            
            # News Slowdown: After 9 PM ET or Weekends
            is_late_night = now.hour >= 21 or now.hour < 4
            is_slow_news_time = (not is_weekday) or is_late_night

            # 1. Heatmap (Runs in Extended Hours OR if cache is empty)
            # Core Hours: 5 mins (300s) | Extended Hours: 15 mins (900s)
            heatmap_interval = 300 if is_market_open else 900
            
            # Force hydration if cache is empty (e.g. server restart at night/weekend)
            heatmap_needs_hydration = not CACHE.get("heatmap", {}).get("data")
            
            # LOGIC FIX: If we need hydration, run it regardless of hours!
            should_run_heatmap = is_extended_hours or heatmap_needs_hydration
            
            if should_run_heatmap and (time.time() - last_heatmap_update > heatmap_interval):
                try: 
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
                    refresh_gamma_logic()
                    last_gamma_update = time.time()
                except Exception as e: print(f"Worker Error (Gamma): {e}")
                time.sleep(0.2)  # Polygon: unlimited API - faster polling
            
            # 4. Whales (Market Hours OR Empty Cache)
            whales_needs_hydration = not CACHE.get("whales", {}).get("data")
            
            if is_market_open or whales_needs_hydration:
                for symbol in WHALE_WATCHLIST:
                    try: refresh_single_whale(symbol)
                    except Exception as e: print(f"Worker Error (Whale {symbol}): {e}")
                    time.sleep(0.2)  # Polygon: unlimited API - faster polling
            else:
                # If market closed AND cache populated, stop polling whales/gamma
                # Just sleep and check News/Heatmap occasionally
                
                # PRE-MARKET WAKEUP: If it's 9:25-9:30 AM, sleep only 1s to catch the open
                is_pre_market_wakeup = is_weekday and (now.hour == 9 and now.minute >= 25)
                
                sleep_time = 1 if is_pre_market_wakeup else 60
                time.sleep(sleep_time)

    t = threading.Thread(target=worker, daemon=True)
    t.start()

# Start the background worker immediately on import
# Guard ensures it only runs once even if module is imported multiple times
if not hasattr(start_background_worker, '_started'):
    load_whale_cache()  # Restore persisted whale data
    mark_whale_cache_cleared()  # Mark this session's start time
    start_background_worker()
    start_background_worker._started = True

if __name__ == "__main__":
    
    port = int(os.environ.get("PORT", 8001))
    print(f"🚀 PigmentOS Flask Server running on port {port}", flush=True)
    app.run(host='0.0.0.0', port=port, threaded=True)
