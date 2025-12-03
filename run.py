import json
import time
import random
import threading
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
MACRO_CACHE_DURATION = 1800
POLY_STATE = {}

CACHE = {
    "barchart": {"data": [], "timestamp": 0},
    "vix": {"data": {"value": 0, "rating": "Neutral"}, "timestamp": 0},
    "cnn_fear_greed": {"data": {"value": 50, "rating": "Neutral"}, "timestamp": 0},
    "polymarket": {"data": [], "timestamp": 0, "is_mock": False},
    "movers": {"data": [], "timestamp": 0},
    "movers": {"data": [], "timestamp": 0},
    "news": {"data": [], "timestamp": 0},
    "heatmap": {"data": [], "timestamp": 0},
    "gamma_SPY": {"data": None, "timestamp": 0}
}

# --- HELPER FUNCTIONS ---

# === CONFIGURATION ===
WHALE_WATCHLIST = [
    'NVDA', 'TSLA', 'SPY', 'QQQ', 'IWM', 'AAPL', 'AMD', 'MSFT', 'AMZN', 
    'GOOGL', 'META', 'NFLX', 'COIN', 'GME', 'PLTR', 'HOOD', 'ROKU'
]

# Track last reported volume to simulate "stream" feel
WHALE_HISTORY = {} 
VOLUME_THRESHOLD = 100 # Only show update if volume increases by this much

def refresh_single_whale(symbol):
    global CACHE
    # print(f"🐳 Checking {symbol}...", flush=True)
    
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
                opts = ticker.option_chain(expiry)
                calls = opts.calls; calls['type'] = 'CALL'
                puts = opts.puts; puts['type'] = 'PUT'
                chain = pd.concat([calls, puts])
                
                # UNUSUAL CRITERIA
                unusual = chain[
                    (chain['volume'] > (chain['openInterest'] * 3)) & 
                    (chain['volume'] > 500) & 
                    (chain['lastPrice'] > 0.10)
                ]
                
                for _, row in unusual.iterrows():
                    notional = row['volume'] * row['lastPrice'] * 100
                    
                    # FILTER: MINIMUM WHALE SIZE
                    min_whale_val = 500_000
                    if symbol in ['SPY', 'QQQ', 'IWM']: min_whale_val = 1_500_000
                        
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

        # Update Cache safely
        if new_whales:
            # Merge with existing cache
            current_data = CACHE["barchart"]["data"]
            # Filter out THIS symbol's old data to avoid duplicates
            other_data = [w for w in current_data if w['baseSymbol'] != symbol]
            updated_data = other_data + new_whales
            
            # Sort all
            updated_data.sort(key=lambda x: x['timestamp'], reverse=True)
            
            CACHE["barchart"]["data"] = updated_data
            CACHE["barchart"]["timestamp"] = time.time()
            print(f"🐳 {symbol}: Found {len(new_whales)} whales.", flush=True)
            
    except Exception as e:
        print(f"Whale Scan Failed ({symbol}): {e}")

def refresh_heatmap_logic():
    global CACHE
    print("🔥 Scanning Heatmap...", flush=True)
    
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
        "RIOT": {"size": "small", "sector": "CRYPTO"}
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
            print(f"🔥 Heatmap Updated ({len(heatmap_data)} items)", flush=True)
            
    except Exception as e:
        print(f"Heatmap Update Failed: {e}")

# --- FLASK ROUTES ---

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

@app.route('/api/whales')
def api_whales():
    global CACHE
    limit = int(request.args.get('limit', 25))
    offset = int(request.args.get('offset', 0))
    
    current_time = time.time()
    stale = False
    
    data = CACHE["barchart"]["data"]
    sliced = data[offset:offset+limit]
    
    return jsonify({
        "data": sliced,
        "stale": False, # Always served from cache
        "timestamp": int(CACHE["barchart"]["timestamp"])
    })

@app.route('/api/whales/stream')
def api_whales_stream():
    def generate():
        print("🐳 SSE Client Connected")
        # Initial Data
        current_time = time.time()
        # Just yield the cache periodically
        while True:
            # Send immediately on connect
            data = CACHE["barchart"]["data"]
            yield f"data: {json.dumps({'data': data, 'stale': False, 'timestamp': int(CACHE['barchart']['timestamp'])})}\n\n"
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
            print("🔑 Using Polymarket API Key", flush=True)
            
        resp = requests.get(url, headers=headers, verify=False, timeout=5)
        
        if resp.status_code == 200:
            events = resp.json()
            
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

            BLACKLIST = ['nfl', 'nba', 'super bowl', 'sport', 'football', 'basketball', 'soccer', 'tennis', 'golf', 'searched', 'election', 'solana', 'microstrategy', 'mstr', 'zootopia', 'wicked', 'movie', 'film', 'box office', 'cinema']
            
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

                # 1. Blacklist Check
                if any(bad in title_lower for bad in BLACKLIST): continue
                
                # 2. Determine Category
                category = "OTHER"
                for cat, keys in KEYWORDS.items():
                    if any(re.search(r'\b' + re.escape(k) + r'\b', title_lower) for k in keys):
                        category = cat
                        break
                
                if category == "OTHER": continue

                # 3. Market Data Extraction
                markets = event.get('markets', [])
                if not markets: continue
                
                # Find best market (highest volume or main)
                # For the actual widget, we need more data than the audit script (outcomes, prices)
                # We'll pick the first market for now, but we could search for the "Yes" market
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

                    outcomes = json.loads(m['outcomes']) if isinstance(m['outcomes'], str) else m['outcomes']
                    prices = json.loads(m['outcomePrices']) if isinstance(m['outcomePrices'], str) else m['outcomePrices']
                    
                    if len(outcomes) >= 2 and len(prices) >= 2:
                        outcome_data = []
                        for i in range(len(outcomes)):
                            try:
                                price = float(prices[i])
                                label = str(outcomes[i])
                                outcome_data.append({"label": label, "price": price})
                            except: continue
                        
                        outcome_data.sort(key=lambda x: x['price'], reverse=True)
                        if len(outcome_data) < 2: continue
                        
                        top1 = outcome_data[0]
                        top2 = outcome_data[1]
                        
                        # OVERRIDE LABEL
                        group_title = m.get('groupItemTitle')
                        if group_title and top1['label'].lower() == "yes":
                            top1['label'] = group_title
                        
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
            for c in final_list[:15]:
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
        else:
            raise Exception("API Error")
            
    except Exception as e:
        print(f"Polymarket Error: {e}")
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
    global CACHE
    current_time = time.time()
    
    if current_time - CACHE["cnn_fear_greed"]["timestamp"] < 300:
        return jsonify(CACHE["cnn_fear_greed"]["data"])
        
    try:
        # 1. VIX Component (Volatility) - 50% Weight
        vix = yf.Ticker("^VIX")
        try:
            vix_val = vix.fast_info['last_price']
        except:
            vix_val = vix.history(period="1d")['Close'].iloc[-1]
            
        # VIX Score: Hyper-Sensitive Calibration
        # The user wants "Extreme Fear" (Score ~22) at VIX ~16.8.
        # We map VIX 12 -> 100 (Greed)
        # We map VIX 16 -> 0 (Extreme Fear)
        # Formula: 100 - (VIX - 12) * 25
        vix_score = 100 - ((vix_val - 12) * 25)
        vix_score = max(0, min(100, vix_score))

        # 2. Momentum Component (SPY vs 5d MA) - 30% Weight
        # Reduced weight because price can be sticky/bullish even in fear.
        spy = yf.Ticker("SPY")
        hist = spy.history(period="10d")
        current_price = hist['Close'].iloc[-1]
        ma_5 = hist['Close'].tail(5).mean()
        
        pct_diff = (current_price - ma_5) / ma_5
        
        # Map -1% to +1% range to 0-100 score
        mom_score = 50 + (pct_diff * 5000)
        mom_score = max(0, min(100, mom_score))

        # 3. Composite Score (70% VIX, 30% Momentum)
        final_score = (vix_score * 0.7) + (mom_score * 0.3)
        
        if final_score >= 75: rating = "Extreme Greed"
        elif final_score >= 55: rating = "Greed"
        elif final_score >= 45: rating = "Neutral"
        elif final_score >= 25: rating = "Fear"
        else: rating = "Extreme Fear"
        
        data = {
            "value": round(final_score), 
            "rating": rating, 
            "vix_reference": round(vix_val, 2),
            "momentum_reference": f"{round(pct_diff * 100, 2)}%"
        }
        CACHE["cnn_fear_greed"] = {"data": data, "timestamp": current_time}
        return jsonify(data)
    except Exception as e:
        print(f"Fear/Greed Error: {e}")
        return jsonify({"value": 50, "rating": "Neutral"})

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
        
        # FinTech & Payments
        "SQ", "PYPL", "AFRM",
        
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
        for symbol in MOVERS_TICKERS:
            try:
                t = tickers_obj.tickers[symbol]
                last = t.fast_info.last_price
                prev = t.fast_info.previous_close
                if last and prev:
                    change = ((last - prev) / prev) * 100
                    movers.append({
                        "symbol": symbol,
                        "change": round(change, 2),
                        "type": "gain" if change >= 0 else "loss"
                    })
            except: continue
            
        movers.sort(key=lambda x: x['change'], reverse=True)
        CACHE["movers"]["data"] = movers
        CACHE["movers"]["timestamp"] = current_time
        return jsonify(movers)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/api/news')
def api_news():
    global CACHE
    # Serve directly from cache (background worker handles updates)
    return jsonify(CACHE["news"]["data"] if CACHE["news"]["data"] else [])



def refresh_news_logic():
    global CACHE
    print("📰 Fetching News...", flush=True)
    
    RSS_FEEDS = [
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", # Finance
        "https://techcrunch.com/feed/", # Tech
        "https://www.investing.com/rss/news.rss" # General Markets
    ]
    
    all_news = []
    current_time = time.time()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        for url in RSS_FEEDS:
            try:
                # Polite Delay
                time.sleep(1)
                
                # Use requests to handle headers and SSL
                response = requests.get(url, headers=headers, verify=False, timeout=5)
                if response.status_code != 200: continue
                
                feed = feedparser.parse(response.content)
                
                for entry in feed.entries[:5]:
                    pub_ts = int(time.time())
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_ts = int(calendar.timegm(entry.published_parsed))
                    
                    # Determine publisher from URL or Feed Title
                    publisher = "Market Wire"
                    if "cnbc" in url: publisher = "CNBC"
                    elif "techcrunch" in url: publisher = "TechCrunch"
                    elif "investing.com" in url: publisher = "Investing.com"
                    
                    all_news.append({
                        "title": entry.get('title', ''),
                        "publisher": publisher,
                        "link": entry.get('link', ''),
                        "time": pub_ts,
                        "ticker": "NEWS"
                    })
            except Exception as e:
                print(f"Feed Error {url}: {e}")
                continue
            
        all_news.sort(key=lambda x: x['time'], reverse=True)
        
        # Update Cache
        if all_news:
            CACHE["news"]["data"] = all_news
            CACHE["news"]["timestamp"] = current_time
            print(f"📰 News Updated ({len(all_news)} items)", flush=True)
            
    except Exception as e:
        print(f"News Update Failed: {e}")



def refresh_gamma_logic():
    global CACHE
    print("👾 Scanning Gamma (SPY)...", flush=True)
    
    symbol = "SPY"
    try:
        print(f"DEBUG: Gamma - Init Ticker {symbol}", flush=True)
        ticker = yf.Ticker(symbol)
        
        # Get Current Price
        print("DEBUG: Gamma - Getting Price", flush=True)
        try:
            current_price = ticker.fast_info.last_price
        except:
            current_price = ticker.info.get('regularMarketPrice', 0)
            
        if not current_price:
            print(f"Gamma Scan Failed: No price for {symbol}")
            return
            
        # Get Nearest Expiration
        print("DEBUG: Gamma - Getting Options", flush=True)
        expirations = ticker.options
        if not expirations:
            print(f"Gamma Scan Failed: No options for {symbol}")
            return
            
        # Use the first expiration (0DTE/Weekly)
        expiry = expirations[0]
        print(f"DEBUG: Gamma - Using Expiry {expiry}", flush=True)
        
        # Fetch Chain
        print("DEBUG: Gamma - Fetching Chain", flush=True)
        opts = ticker.option_chain(expiry)
        print("DEBUG: Gamma - Chain Fetched", flush=True)
        calls = opts.calls
        puts = opts.puts
        
        # Aggregate Volume and Open Interest by Strike
        gamma_data = {}
        
        # Process Calls
        for _, row in calls.iterrows():
            strike = float(row['strike'])
            vol = int(row['volume']) if not pd.isna(row['volume']) else 0
            oi = int(row['openInterest']) if not pd.isna(row['openInterest']) else 0
            
            if strike not in gamma_data: gamma_data[strike] = {"call_vol": 0, "put_vol": 0, "call_oi": 0, "put_oi": 0}
            gamma_data[strike]["call_vol"] += vol
            gamma_data[strike]["call_oi"] += oi
            
        # Process Puts
        for _, row in puts.iterrows():
            strike = float(row['strike'])
            vol = int(row['volume']) if not pd.isna(row['volume']) else 0
            oi = int(row['openInterest']) if not pd.isna(row['openInterest']) else 0
            
            if strike not in gamma_data: gamma_data[strike] = {"call_vol": 0, "put_vol": 0, "call_oi": 0, "put_oi": 0}
            gamma_data[strike]["put_vol"] += vol
            gamma_data[strike]["put_oi"] += oi
            
        # Convert to List for Frontend
        # Filter for relevant range (e.g. +/- 10% of current price) to keep chart readable
        lower_bound = current_price * 0.90
        upper_bound = current_price * 1.10
        
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
            "strikes": final_data
        }
        
        # Update Cache
        cache_key = f"gamma_{symbol}"
        CACHE[cache_key] = {"data": result, "timestamp": time.time()}
        print(f"👾 Gamma Updated for {symbol} ({len(final_data)} strikes)", flush=True)
        
    except Exception as e:
        print(f"Gamma Scan Failed: {e}")

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


@app.route('/api/heatmap')
def api_heatmap():
    global CACHE
    # Serve directly from cache (background worker handles updates)
    return jsonify(CACHE["heatmap"]["data"])

@app.route('/api/gamma')
def api_gamma():
    global CACHE
    symbol = request.args.get('symbol', 'SPY').upper()
    cache_key = f"gamma_{symbol}"
    
    # Serve directly from cache
    if cache_key in CACHE and CACHE[cache_key]["data"]:
        return jsonify(CACHE[cache_key]["data"])
        
    return jsonify({"error": "Loading..."})

def start_background_worker():
    def worker():
        print("🔧 Trickle Worker Started", flush=True)
        
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

            # 1. Heatmap (Runs in Extended Hours)
            if is_extended_hours:
                try: refresh_heatmap_logic()
                except Exception as e: print(f"Worker Error (Heatmap): {e}")
                time.sleep(3)
            
            # 2. News (Always Runs, but slower at night)
            try: refresh_news_logic()
            except Exception as e: print(f"Worker Error (News): {e}")
            time.sleep(3)
            
            # 3. Gamma (Only Market Hours)
            if is_market_open:
                try: refresh_gamma_logic()
                except Exception as e: print(f"Worker Error (Gamma): {e}")
                time.sleep(3)
            
            # 4. Whales (Only Market Hours)
            if is_market_open:
                for symbol in WHALE_WATCHLIST:
                    try: refresh_single_whale(symbol)
                    except Exception as e: print(f"Worker Error (Whale {symbol}): {e}")
                    time.sleep(3)
            else:
                # If market closed, sleep longer to save resources
                # But keep checking News/Heatmap occasionally
                time.sleep(60)

    t = threading.Thread(target=worker, daemon=True)
    t.start()

# Start the background worker immediately on import (for Gunicorn)
start_background_worker()

if __name__ == "__main__":
    
    port = int(os.environ.get("PORT", 8001))
    print(f"🚀 PigmentOS Flask Server running on port {port}", flush=True)
    app.run(host='0.0.0.0', port=port, threaded=True)
