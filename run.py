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
    default_limits=["200 per day", "50 per hour"],
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
    'GOOGL', 'GOOG', 'META', 'PLTR', 'MU', 'NBIS', 'VIX', 'AVGO'
]

# Track last reported volume to simulate "stream" feel
WHALE_HISTORY = {} 
VOLUME_THRESHOLD = 100 # Only show update if volume increases by this much

def refresh_single_whale(symbol):
    global CACHE

    
    try:
        ticker = yf.Ticker(symbol)
        
        # Get underlying price
        try:
            current_price = ticker.fast_info.last_price
        except:
            current_price = ticker.info.get('regularMarketPrice', 0)
        
        if not current_price: return

        # Get expiration dates
        expirations = ticker.options
        if not expirations: return
            
        # Check next 2 expirations (approx 2 weeks out)
        target_expirations = expirations[:2]
        
        new_whales = []
        
        for expiry in target_expirations:
            try:
                # FILTER: 0DTE for Indices (SPY, QQQ, IWM)
                # 0DTE is mostly noise/hedging. We want strategic positioning.
                if symbol in ['SPY', 'QQQ', 'IWM']:
                    expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
                    # Use Eastern time for market date
                    today_date = datetime.now(pytz.timezone('US/Eastern')).date()
                    if expiry_date <= today_date:
                        continue

                opts = ticker.option_chain(expiry)
                calls = opts.calls; calls['type'] = 'CALL'
                puts = opts.puts; puts['type'] = 'PUT'
                chain = pd.concat([calls, puts])
                
                # UNUSUAL CRITERIA - Vol/OI ratio varies by symbol type
                # For indices: 4x ratio to filter noise
                # For stocks: 3x ratio
                vol_oi_multiplier = 4 if symbol in ['SPY', 'QQQ', 'IWM'] else 3
                unusual = chain[
                    (chain['volume'] > (chain['openInterest'] * vol_oi_multiplier)) & 
                    (chain['volume'] > 500) & 
                    (chain['lastPrice'] > 0.10)
                ]
                
                for _, row in unusual.iterrows():
                    notional = row['volume'] * row['lastPrice'] * 100
                    
                    # FILTER: MINIMUM WHALE SIZE
                    min_whale_val = 500_000
                    if symbol in ['SPY', 'QQQ', 'IWM']: min_whale_val = 5_000_000
                        
                    if notional < min_whale_val: continue

                    # FILTER: STRICT DATE CHECK (US/Eastern)
                    tz_eastern = pytz.timezone('US/Eastern')
                    trade_ts = row['lastTradeDate']
                    if trade_ts.tzinfo is None: trade_ts = pytz.utc.localize(trade_ts)
                    
                    if trade_ts.astimezone(tz_eastern).date() != datetime.now(tz_eastern).date():
                        continue
                    
                    # FORMATTING
                    strike = float(row['strike'])
                    is_call = row['type'] == 'CALL'
                    
                    # FILTER: MONEYNESS (Industry Standard - within 10% of current price)
                    # Only show ATM and near-the-money options
                    price_diff_pct = abs(strike - current_price) / current_price
                    if price_diff_pct > 0.10:  # More than 10% away from current price
                        continue
                    
                    moneyness = "ITM" if (is_call and current_price > strike) or (not is_call and current_price < strike) else "OTM"
                    
                    # Format Premium
                    def format_money(val):
                        if val >= 1_000_000: return f"${val/1_000_000:.1f}M"
                        if val >= 1_000: return f"${val/1_000:.0f}k"
                        return f"${val:.0f}"
                    
                    # Handle Timestamp
                    trade_time_obj = row['lastTradeDate']
                    if hasattr(trade_time_obj, 'strftime'):
                        trade_time_str = trade_time_obj.strftime("%H:%M:%S")
                        timestamp_val = trade_time_obj.timestamp()
                    else:
                        trade_time_str = str(trade_time_obj)
                        timestamp_val = time.time()

                    # VOLUME THRESHOLD LOGIC
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
                        # Report OLD volume to prevent animation
                        whale_data["volume"] = last_vol
                        whale_data["premium"] = format_money(last_vol * row['lastPrice'] * 100)
                        whale_data["notional_value"] = last_vol * row['lastPrice'] * 100
                        whale_data["is_mega_whale"] = whale_data["notional_value"] > MEGA_WHALE_THRESHOLD
                        new_whales.append(whale_data)

            except Exception: continue

        # Update Cache safely (Always update to allow clearing old data)
        with CACHE_LOCK:
            # Merge with existing cache
            current_data = CACHE["whales"]["data"]
            # Filter out THIS symbol's old data to avoid duplicates (or to clear it if new_whales is empty)
            other_data = [w for w in current_data if w['baseSymbol'] != symbol]
            updated_data = other_data + new_whales
            
            # Sort all
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
    today_date = datetime.now(tz_eastern).date()
    
    clean_data = []
    for whale in raw_data:
        # 'timestamp' is unix epoch
        trade_dt = datetime.fromtimestamp(whale['timestamp'], tz_eastern)
        if trade_dt.date() == today_date:
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
            time.sleep(5) # Check for updates every 5s (lightweight)

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

@app.route('/api/vix')
def api_vix():
    global CACHE
    current_time = time.time()
    FRED_KEY = os.environ.get("FRED_API_KEY", "9832f887b004951ec7d53cb78f1063a0")
    
    if current_time - CACHE["vix"]["timestamp"] >= MACRO_CACHE_DURATION:
        try:
            url = f"https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&api_key={FRED_KEY}&file_type=json&sort_order=desc&limit=1"
            resp = requests.get(url, timeout=5)
            CACHE["vix"]["data"] = resp.json()
            CACHE["vix"]["timestamp"] = current_time
        except Exception as e:
            return jsonify({"error": str(e)})
            
    return jsonify(CACHE["vix"]["data"])

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



def refresh_gamma_logic(symbol="SPY"):
    global CACHE

    try:
        ticker = yf.Ticker(symbol)
        
        # Get Current Price
        try:
            current_price = ticker.fast_info.last_price
        except:
            current_price = ticker.info.get('regularMarketPrice', 0)
            
        if not current_price:
            print(f"Gamma Scan Failed: No price for {symbol}")
            SERVICE_STATUS["GAMMA"] = {"status": "OFFLINE", "last_updated": time.time()}
            return
            
        # Get Nearest Expiration
        expirations = ticker.options
        if not expirations:
            print(f"Gamma Scan Failed: No options for {symbol}")
            SERVICE_STATUS["GAMMA"] = {"status": "OFFLINE", "last_updated": time.time()}
            return
            
        # Use the first expiration (0DTE/Weekly)
        expiry = expirations[0]

        # Fetch Chain
        opts = ticker.option_chain(expiry)
        calls = opts.calls
        puts = opts.puts
        
        # Aggregate Volume and Open Interest by Strike
        gamma_data = {}
        
        # Helper to check if trade is from today (or Friday if weekend)
        from datetime import timedelta # Import locally
        tz_eastern = pytz.timezone('US/Eastern')
        now_eastern = datetime.now(tz_eastern)
        today_date = now_eastern.date()
        weekday = today_date.weekday() # 0=Mon, 6=Sun
        
        # Weekend Logic: If Sat(5) or Sun(6), allow trades from last Friday
        is_weekend = weekday >= 5
        allowed_date = today_date
        
        if is_weekend:
            # If Sat(5), Friday is today-1
            # If Sun(6), Friday is today-2
            days_back = 1 if weekday == 5 else 2
            allowed_date = today_date - timedelta(days=days_back)
            print(f"Gamma: Weekend Mode ({weekday}). Using data from {allowed_date}")

        def is_valid_trade_date(ts):
            if pd.isna(ts): return False
            if ts.tzinfo is None: ts = pytz.utc.localize(ts)
            trade_date = ts.astimezone(tz_eastern).date()
            
            if is_weekend:
                # On weekend, accept Friday's data
                return trade_date == allowed_date
            else:
                # On weekday, strict "today" check
                return trade_date == today_date

        # Process Calls
        for _, row in calls.iterrows():
            strike = float(row['strike'])
            # Only count volume if trade is from VALID DATE
            vol = int(row['volume']) if (not pd.isna(row['volume']) and is_valid_trade_date(row['lastTradeDate'])) else 0
            oi = int(row['openInterest']) if not pd.isna(row['openInterest']) else 0
            
            if strike not in gamma_data: gamma_data[strike] = {"call_vol": 0, "put_vol": 0, "call_oi": 0, "put_oi": 0}
            gamma_data[strike]["call_vol"] += vol
            gamma_data[strike]["call_oi"] += oi
            
        # Process Puts
        for _, row in puts.iterrows():
            strike = float(row['strike'])
            # Only count volume if trade is from VALID DATE
            vol = int(row['volume']) if (not pd.isna(row['volume']) and is_valid_trade_date(row['lastTradeDate'])) else 0
            oi = int(row['openInterest']) if not pd.isna(row['openInterest']) else 0
            
            if strike not in gamma_data: gamma_data[strike] = {"call_vol": 0, "put_vol": 0, "call_oi": 0, "put_oi": 0}
            gamma_data[strike]["put_vol"] += vol
            gamma_data[strike]["put_oi"] += oi
            
        # Convert to List for Frontend
        # Filter for relevant range (e.g. +/- 20% of current price) to keep chart readable
        lower_bound = current_price * 0.80
        upper_bound = current_price * 1.20
        
        final_data = []
        for strike, data in gamma_data.items():
            if lower_bound <= strike <= upper_bound:
                final_data.append({
                    "strike": strike,
                    "call_vol": data["call_vol"],
                    "put_vol": data["put_vol"],
                    "call_oi": data["call_oi"],
                    "put_oi": data["put_oi"]
                })
                
        # Sort by strike
        final_data.sort(key=lambda x: x['strike'])
        
        result = {
            "symbol": symbol,
            "current_price": current_price,
            "expiry": expiry,
            "strikes": final_data,
            "is_weekend_data": is_weekend # Flag for frontend
        }
        
        # Update Cache
        cache_key = f"gamma_{symbol}"
        CACHE[cache_key] = {"data": result, "timestamp": time.time()}
        SERVICE_STATUS["GAMMA"] = {"status": "ONLINE", "last_updated": time.time()}
        SERVICE_STATUS["YFIN"] = {"status": "ONLINE", "last_updated": time.time()} # Gamma implies YFIN is up

    except Exception as e:
        print(f"Gamma Scan Failed ({symbol}): {e}")
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

        # 1. Fetch Whales Sequentially (Fix for Gevent/Threading Conflict)
        # ThreadPoolExecutor causes KeyError in gevent-patched environments
        for symbol in WHALE_WATCHLIST:
            try:
                refresh_single_whale(symbol)
            except Exception as e:
                print(f"Startup Whale Error ({symbol}): {e}")
        
        # 2. Fetch Gamma & Heatmap
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
            # Extended Hours for Heatmap/News: 4:00 AM - 8:00 PM ET
            is_extended_hours = is_weekday and (
                (now.hour > 4 or (now.hour == 4 and now.minute >= 0)) and 
                (now.hour < 20)
            )
            # Core Market Hours for Options (Whales/Gamma): 9:30 AM - 4:00 PM ET
            is_market_open = is_weekday and (
                (now.hour > 9 or (now.hour == 9 and now.minute >= 30)) and 
                (now.hour < 16)
            )

            # 1. Heatmap (Runs in Extended Hours) - THROTTLED TO 10 MINS
            # Force hydration if cache is empty (e.g. server restart at night)
            heatmap_needs_hydration = not CACHE.get("heatmap", {}).get("data")
            
            if (is_extended_hours or heatmap_needs_hydration) and (time.time() - last_heatmap_update > 600):
                try: 
                    refresh_heatmap_logic()
                    last_heatmap_update = time.time()
                except Exception as e: print(f"Worker Error (Heatmap): {e}")
                time.sleep(3)
            
            # 2. News (Always Runs, but slower at night) - THROTTLED TO 5 MINS
            if time.time() - last_news_update > 300:
                try: 
                    refresh_news_logic()
                    # Check if we actually got news
                    news_data = CACHE.get("news", {}).get("data", [])
                    if news_data:
                        last_news_update = time.time() # Success: Wait 5 mins
                    else:
                        print("⚠️ News Fetch Empty - Retrying in 60s", flush=True)
                        last_news_update = time.time() - 240 # Failure: Wait only 60s (300 - 240 = 60)
                except Exception as e: 
                    print(f"Worker Error (News): {e}")
                    last_news_update = time.time() - 240 # Error: Wait only 60s
                time.sleep(3)
            
            # 3. Gamma (Market Hours OR Empty Cache) - THROTTLED TO 5 MINS
            # If cache is empty (server restart), we MUST fetch data even if closed
            gamma_needs_hydration = not CACHE.get("gamma_SPY", {}).get("data")
            
            if (is_market_open or gamma_needs_hydration) and (time.time() - last_gamma_update > 300):
                try: 
                    refresh_gamma_logic()
                    last_gamma_update = time.time()
                except Exception as e: print(f"Worker Error (Gamma): {e}")
                time.sleep(3)
            
            # 4. Whales (Market Hours OR Empty Cache)
            whales_needs_hydration = not CACHE.get("whales", {}).get("data")
            
            if is_market_open or whales_needs_hydration:
                for symbol in WHALE_WATCHLIST:
                    try: refresh_single_whale(symbol)
                    except Exception as e: print(f"Worker Error (Whale {symbol}): {e}")
                    time.sleep(3)
            else:
                # If market closed AND cache populated, sleep longer
                time.sleep(60)

    t = threading.Thread(target=worker, daemon=True)
    t.start()

# Start the background worker immediately on import
# Guard ensures it only runs once even if module is imported multiple times
if not hasattr(start_background_worker, '_started'):
    start_background_worker()
    start_background_worker._started = True

if __name__ == "__main__":
    
    port = int(os.environ.get("PORT", 8001))
    print(f"🚀 PigmentOS Flask Server running on port {port}", flush=True)
    app.run(host='0.0.0.0', port=port, threaded=True)
