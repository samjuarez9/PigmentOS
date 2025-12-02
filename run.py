import json
import time
import random
import threading
import requests
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
CACHE_DURATION = 120
MACRO_CACHE_DURATION = 1800
POLY_STATE = {}

CACHE = {
    "barchart": {"data": [], "timestamp": 0},
    "vix": {"data": {"value": 0, "rating": "Neutral"}, "timestamp": 0},
    "cnn_fear_greed": {"data": {"value": 50, "rating": "Neutral"}, "timestamp": 0},
    "polymarket": {"data": [], "timestamp": 0, "is_mock": False},
    "movers": {"data": [], "timestamp": 0},
    "news": {"data": [], "timestamp": 0}
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

def refresh_whales_logic():
    global CACHE
    print("🐳 Scanning for Unusual Whales (Yahoo Finance)...", flush=True)
    
    found_whales = []
    
    try:
        for symbol in WHALE_WATCHLIST:
            try:
                # print(f"  Checking {symbol}...", flush=True)
                ticker = yf.Ticker(symbol)
                
                # Get underlying price for Moneyness
                # Try fast_info first for speed
                try:
                    current_price = ticker.fast_info.last_price
                except:
                    current_price = ticker.info.get('regularMarketPrice', 0)
                
                if not current_price:
                    continue

                # Get expiration dates
                expirations = ticker.options
                if not expirations:
                    continue
                    
                # Check next 4 expirations (approx 1 month out)
                # This captures 0DTE, Weekly, and Monthly flows
                target_expirations = expirations[:4]
                
                for expiry in target_expirations:
                    try:
                        # Fetch Option Chain
                        opts = ticker.option_chain(expiry)
                        
                        # Combine Calls and Puts
                        calls = opts.calls
                        calls['type'] = 'CALL'
                        puts = opts.puts
                        puts['type'] = 'PUT'
                        
                        chain = pd.concat([calls, puts])
                        
                        # === UNUSUAL CRITERIA ===
                        # 1. Volume > Open Interest (The classic signal)
                        # 2. Volume > 500 (Filter out noise)
                        # 3. Last Price > 0.10 (Filter out dead OTMs)
                        
                        unusual = chain[
                            (chain['volume'] > (chain['openInterest'] * 3)) & 
                            (chain['volume'] > 500) & 
                            (chain['lastPrice'] > 0.10)
                        ]
                        
                        for _, row in unusual.iterrows():
                            # Calculate Notional Value (Premium)
                            notional = row['volume'] * row['lastPrice'] * 100
                            
                            # === FILTER: MINIMUM WHALE SIZE ===
                            # Tiered Thresholds:
                            # - ETFs (SPY, QQQ, IWM): $1.5M (Filter noise)
                            # - Individual Stocks: $500k (Catch specific bets)
                            
                            min_whale_val = 500_000
                            if symbol in ['SPY', 'QQQ', 'IWM']:
                                min_whale_val = 1_500_000
                                
                            if notional < min_whale_val:
                                continue

                            # === FILTER: STRICT DATE CHECK ===
                            # Ensure the trade happened TODAY
                            trade_date = row['lastTradeDate'].date()
                            today_date = datetime.now(pytz.timezone('US/Eastern')).date()
                            
                            if trade_date != today_date:
                                # Skip old data (yesterday's high volume)
                                continue
                            
                            # Calculate Moneyness (ITM/OTM)
                            strike = float(row['strike'])
                            is_call = row['type'] == 'CALL'
                            moneyness = "OTM"
                            
                            if is_call:
                                if current_price > strike: moneyness = "ITM"
                            else: # PUT
                                if current_price < strike: moneyness = "ITM"
                            
                            # Format Premium
                            def format_money(val):
                                if val >= 1_000_000: return f"${val/1_000_000:.1f}M"
                                if val >= 1_000: return f"${val/1_000:.0f}k"
                                return f"${val:.0f}"
                            
                            # Handle Timestamp
                            # yfinance returns a Timestamp object, convert to string for JSON
                            trade_time_obj = row['lastTradeDate']
                            if hasattr(trade_time_obj, 'strftime'):
                                trade_time_str = trade_time_obj.strftime("%H:%M:%S")
                                timestamp_val = trade_time_obj.timestamp()
                            else:
                                trade_time_str = str(trade_time_obj)
                                timestamp_val = time.time() # Fallback

                            # === VOLUME THRESHOLD LOGIC ===
                            # To mimic a "stream", we only update if volume grows significantly
                            contract_id = row['contractSymbol']
                            current_vol = int(row['volume'])
                            
                            last_vol = WHALE_HISTORY.get(contract_id, 0)
                            delta = current_vol - last_vol
                            
                            # If it's the first time seeing it, OR volume grew significantly
                            if last_vol == 0 or delta >= VOLUME_THRESHOLD:
                                # Update history
                                WHALE_HISTORY[contract_id] = current_vol
                                
                                # Add to list with NEW volume
                                found_whales.append({
                                    "baseSymbol": symbol,
                                    "symbol": row['contractSymbol'],
                                    "strikePrice": strike,
                                    "expirationDate": expiry,
                                    "putCall": 'C' if is_call else 'P',
                                    "volume": current_vol,
                                    "openInterest": int(row['openInterest']),
                                    "lastPrice": float(row['lastPrice']),
                                    "tradeTime": trade_time_str,
                                    "timestamp": timestamp_val, # For sorting
                                    "vol_oi": round(row['volume'] / (row['openInterest'] if row['openInterest'] > 0 else 1), 1),
                                    "premium": format_money(notional),
                                    "notional_value": notional,
                                    "moneyness": moneyness, 
                                    "is_mega_whale": notional > MEGA_WHALE_THRESHOLD,
                                    "delta": 0,
                                    "iv": row['impliedVolatility']
                                })
                            else:
                                # Volume didn't change enough. 
                                # We still want to include it in the list (so it doesn't disappear),
                                # BUT we report the OLD volume so the ID stays the same in frontend.
                                # This prevents "replacing" animation.
                                
                                # Re-calculate notional based on old volume? No, keep current price.
                                # Just force volume to be last_vol
                                
                                found_whales.append({
                                    "baseSymbol": symbol,
                                    "symbol": row['contractSymbol'],
                                    "strikePrice": strike,
                                    "expirationDate": expiry,
                                    "putCall": 'C' if is_call else 'P',
                                    "volume": last_vol, # <--- KEY: Report OLD volume
                                    "openInterest": int(row['openInterest']),
                                    "lastPrice": float(row['lastPrice']),
                                    "tradeTime": trade_time_str,
                                    "timestamp": timestamp_val,
                                    "vol_oi": round(last_vol / (row['openInterest'] if row['openInterest'] > 0 else 1), 1),
                                    "premium": format_money(last_vol * row['lastPrice'] * 100),
                                    "notional_value": last_vol * row['lastPrice'] * 100,
                                    "moneyness": moneyness, 
                                    "is_mega_whale": (last_vol * row['lastPrice'] * 100) > MEGA_WHALE_THRESHOLD,
                                    "delta": 0,
                                    "iv": row['impliedVolatility']
                                })
                    except Exception as e:
                        # print(f"  Error checking expiry {expiry} for {symbol}: {e}")
                        continue

            except Exception as e:
                # print(f"  Skipping {symbol}: {e}")
                continue
            
            # Rate Limit Protection
            time.sleep(0.5)

                    

        
        # Sort by Time (Most Recent First)
        found_whales.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Update Cache
        if found_whales:
            CACHE["barchart"]["data"] = found_whales
            CACHE["barchart"]["timestamp"] = time.time()
            print(f"🐳 Found {len(found_whales)} unusual trades.", flush=True)
        else:
            print("🐳 No unusual activity found this scan.", flush=True)
            
    except Exception as e:
        print(f"Whale Scan Failed: {e}")

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
    current_time = time.time()
    
    # 1. Check Cache (3 minutes = 180s)
    if current_time - CACHE["news"]["timestamp"] < 180 and CACHE["news"]["data"]:
        return jsonify(CACHE["news"]["data"])

    try:
        # Simplified News Logic
        import calendar
        
        RSS_URLS = [
            "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114", # CNBC Top News
            "https://techcrunch.com/feed/", # TechCrunch
            "https://www.investing.com/rss/news.rss" # Investing.com
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        all_news = []
        print("📰 Fetching fresh news...", flush=True)
        
        for url in RSS_URLS:
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
        CACHE["news"]["data"] = all_news
        CACHE["news"]["timestamp"] = current_time
        
        return jsonify(all_news)
    except Exception as e:
        print(f"News Error: {e}")
        return jsonify(CACHE["news"]["data"] if CACHE["news"]["data"] else [])

@app.route('/api/ping')
def api_ping():
    return jsonify({"status": "ok", "timestamp": time.time()})

@app.route('/api/heatmap')
def api_heatmap():
    global CACHE
    current_time = time.time()
    
    # Cache for 1 minute (60s)
    if "heatmap" in CACHE and current_time - CACHE["heatmap"]["timestamp"] < 60:
        return jsonify(CACHE["heatmap"]["data"])
        
    # Tickers mapped to their "Size" category and "Sector" for filtering
    # This ensures we get the right data for the right boxes
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
                # If .info fails or is missing keys, fall back to fast_info
                try:
                    info = t.info
                    state = info.get('marketState', 'REGULAR')
                    
                    price = info.get('regularMarketPrice')
                    prev_close = info.get('regularMarketPreviousClose')
                    
                    # Handle Pre/Post Market
                    if state in ['PRE', 'PREPRE'] and info.get('preMarketPrice'):
                        price = info['preMarketPrice']
                    elif state in ['POST', 'POSTPOST'] and info.get('postMarketPrice'):
                        price = info['postMarketPrice']
                        
                    # Fallback to fast_info if info is incomplete
                    if not price or not prev_close:
                        price = t.fast_info.last_price
                        prev_close = t.fast_info.previous_close
                        
                except:
                    # Fallback if .info fails completely
                    price = t.fast_info.last_price
                    prev_close = t.fast_info.previous_close

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
                print(f"Error fetching {symbol}: {e}")
                continue
        
        # Update Cache
        if "heatmap" not in CACHE: CACHE["heatmap"] = {}
        CACHE["heatmap"]["data"] = heatmap_data
        CACHE["heatmap"]["timestamp"] = current_time
        
        return jsonify(heatmap_data)
    except Exception as e:
        print(f"Heatmap API Error: {e}")
        return jsonify({"error": str(e)})

@app.route('/api/gamma')
def api_gamma():
    global CACHE
    symbol = request.args.get('symbol', 'SPY').upper()
    
    # Cache key for Gamma
    cache_key = f"gamma_{symbol}"
    current_time = time.time()
    
    # Check Cache (1 minute)
    if cache_key in CACHE and current_time - CACHE[cache_key]["timestamp"] < 60:
        return jsonify(CACHE[cache_key]["data"])
        
    try:
        ticker = yf.Ticker(symbol)
        
        # Get Current Price
        try:
            current_price = ticker.fast_info.last_price
        except:
            current_price = ticker.info.get('regularMarketPrice', 0)
            
        if not current_price:
            return jsonify({"error": "Price not found"})
            
        # Get Nearest Expiration
        expirations = ticker.options
        if not expirations:
            return jsonify({"error": "No options found"})
            
        # Use the first expiration (0DTE/Weekly)
        expiry = expirations[0]
        
        # Fetch Chain
        opts = ticker.option_chain(expiry)
        calls = opts.calls
        puts = opts.puts
        
        # Aggregate Volume and Open Interest by Strike
        # We want a dictionary: { strike: { call_vol: 0, put_vol: 0, call_oi: 0, put_oi: 0 } }
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
        for strike, vols in gamma_data.items():
            if lower_bound <= strike <= upper_bound:
                final_data.append({
                    "strike": strike,
                    "call_vol": vols["call_vol"],
                    "put_vol": vols["put_vol"],
                    "call_oi": vols["call_oi"],
                    "put_oi": vols["put_oi"]
                })
                
        final_data.sort(key=lambda x: x['strike'])
        
        result = {
            "symbol": symbol,
            "current_price": current_price,
            "expiration": expiry,
            "strikes": final_data
        }
        
        # Update Cache
        CACHE[cache_key] = {"data": result, "timestamp": current_time}
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Gamma API Error: {e}")
        return jsonify({"error": str(e)})

def start_background_worker():
    def worker():
        print("🔧 Background Worker Started", flush=True)
        while True:
            try:
                refresh_whales_logic()
            except Exception as e:
                print(f"Worker Error: {e}", flush=True)
            
            # Sleep for CACHE_DURATION
            time.sleep(CACHE_DURATION)

    t = threading.Thread(target=worker, daemon=True)
    t.start()

# Start the background worker immediately on import (for Gunicorn)
start_background_worker()

if __name__ == "__main__":
    
    port = int(os.environ.get("PORT", 8001))
    print(f"🚀 PigmentOS Flask Server running on port {port}", flush=True)
    app.run(host='0.0.0.0', port=port, threaded=True)
