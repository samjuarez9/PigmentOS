import json
import time
import random
import threading
import requests
import yfinance as yf
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

# Watchlist for "Whale" Scan
WATCHLIST = [
    "NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META", "GOOGL",
    "AMD", "AVGO", "ARM", "SMCI", "MU", "INTC",
    "PLTR", "SOFI", "RKLB",
    "SPY", "QQQ", "IWM"
]

MEGA_WHALE_THRESHOLD = 9_000_000  # $9M

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

def filter_for_whales(chain_df, current_stock_price, min_premium=2000000):
    if chain_df.empty: return chain_df
    
    ny_tz = pytz.timezone('America/New_York')
    today_ny = datetime.now(ny_tz).date()
    
    def is_today(ts):
        try:
            if hasattr(ts, 'to_pydatetime'): dt = ts.to_pydatetime()
            else: dt = ts
            if dt.tzinfo is None: dt = pytz.utc.localize(dt)
            return dt.astimezone(ny_tz).date() == today_ny
        except: return False

    chain_df = chain_df[chain_df['lastTradeDate'].apply(is_today)].copy()
    if chain_df.empty: return chain_df

    chain_df['notional_value'] = chain_df['volume'] * chain_df['lastPrice'] * 100
    chain_df['vol_oi_ratio'] = chain_df['volume'] / (chain_df['openInterest'].replace(0, 1))
    
    whales = chain_df[
        (chain_df['volume'] > chain_df['openInterest']) &
        (chain_df['notional_value'] >= min_premium) &
        (chain_df['volume'] > 50)
    ].copy()
    
    if whales.empty: return whales
        
    whales['moneyness'] = 'ITM'
    whales.loc[(whales['contractSymbol'].str.contains('C')) & (whales['strike'] > current_stock_price), 'moneyness'] = 'OTM'
    whales.loc[(whales['contractSymbol'].str.contains('P')) & (whales['strike'] < current_stock_price), 'moneyness'] = 'OTM'
    
    return whales.sort_values(by='lastTradeDate', ascending=False)

def fetch_ticker_options(ticker):
    try:
        stock = yf.Ticker(ticker)
        exps = stock.options
        if not exps: return []
        
        expiry = exps[0]
        chain = stock.option_chain(expiry)
        
        try: current_price = stock.fast_info['last_price']
        except: current_price = stock.history(period="1d")['Close'].iloc[-1]

        calls = chain.calls.copy()
        calls['putCall'] = 'C'
        if 'delta' not in calls.columns: calls['delta'] = 0.0
        if 'impliedVolatility' not in calls.columns: calls['impliedVolatility'] = 0.0
        
        puts = chain.puts.copy()
        puts['putCall'] = 'P'
        if 'delta' not in puts.columns: puts['delta'] = 0.0
        if 'impliedVolatility' not in puts.columns: puts['impliedVolatility'] = 0.0
        
        full_chain = pd.concat([calls, puts])
        whales = filter_for_whales(full_chain, current_price)
        
        if whales.empty: return []

        trades = []
        for i, (index, row) in enumerate(whales.iterrows()):
            premium = row['notional_value']
            is_mega = premium >= MEGA_WHALE_THRESHOLD
            
            # Formatting for console logs (optional)
            if premium >= 1_000_000: prem_str = f"${premium/1_000_000:.1f}M"
            else: prem_str = f"${premium/1_000:.0f}k"

            trades.append({
                "baseSymbol": ticker,
                "symbol": row['contractSymbol'],
                "strikePrice": float(row['strike']),
                "expirationDate": expiry,
                "putCall": row['putCall'],
                "volume": int(row['volume']),
                "openInterest": int(row['openInterest']),
                "lastPrice": float(row['lastPrice']),
                "tradeTime": int(row['lastTradeDate'].timestamp()),
                "vol_oi": round(row['vol_oi_ratio'], 1),
                "premium": prem_str,
                "notional_value": row['notional_value'],
                "moneyness": row['moneyness'],
                "is_mega_whale": is_mega,
                "delta": round(float(row.get('delta', 0)), 3),
                "iv": round(float(row.get('impliedVolatility', 0)) * 100, 1)
            })
        return trades
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return []

def refresh_whales_logic():
    global CACHE
    all_whales = []
    print("🐳 Scanning for whales...", flush=True)
    for ticker in WATCHLIST:
        try:
            whales = fetch_ticker_options(ticker)
            all_whales.extend(whales)
            time.sleep(2)
        except: continue
    
    all_whales.sort(key=lambda x: x.get('tradeTime', 0), reverse=True)
    all_whales = all_whales[:50]
    
    CACHE["barchart"]["data"] = all_whales
    CACHE["barchart"]["timestamp"] = time.time()
    print(f"🐳 Refreshed {len(all_whales)} whale trades.", flush=True)

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
    
    if current_time - CACHE["barchart"]["timestamp"] >= CACHE_DURATION:
        try:
            refresh_whales_logic()
        except Exception as e:
            print(f"Refresh failed: {e}")
            stale = True
            
    data = CACHE["barchart"]["data"]
    sliced = data[offset:offset+limit]
    
    return jsonify({
        "data": sliced,
        "stale": stale,
        "timestamp": int(CACHE["barchart"]["timestamp"])
    })

@app.route('/api/whales/stream')
def api_whales_stream():
    def generate():
        print("🐳 SSE Client Connected")
        # Initial Data
        current_time = time.time()
        if current_time - CACHE["barchart"]["timestamp"] >= CACHE_DURATION:
            refresh_whales_logic()
            
        data = CACHE["barchart"]["data"]
        yield f"data: {json.dumps({'data': data, 'stale': False, 'timestamp': int(CACHE['barchart']['timestamp'])})}\n\n"
        
        while True:
            time.sleep(CACHE_DURATION)
            refresh_whales_logic()
            data = CACHE["barchart"]["data"]
            yield f"data: {json.dumps({'data': data, 'stale': False, 'timestamp': int(CACHE['barchart']['timestamp'])})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/api/polymarket')
def api_polymarket():
    global CACHE, POLY_STATE
    current_time = time.time()
    
    if current_time - CACHE["polymarket"]["timestamp"] < CACHE_DURATION:
        return jsonify({"data": CACHE["polymarket"]["data"], "is_mock": CACHE["polymarket"]["is_mock"]})

    try:
        url = "https://gamma-api.polymarket.com/events?closed=false&limit=100&order=volume24hr&ascending=false"
        
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        
        # Optional: Use API Key if provided (helps with rate limits)
        api_key = os.environ.get("POLYMARKET_API_KEY")
        if api_key:
            headers['Authorization'] = f"Bearer {api_key}"
            print("🔑 Using Polymarket API Key", flush=True)
            
        resp = requests.get(url, headers=headers, verify=False, timeout=5)
        
        if resp.status_code == 200:
            events = resp.json()
            # Expanded Keywords for "Deep Intel"
            KEYWORDS = {
                "GEOPOL": ['war', 'invasion', 'strike', 'china', 'russia', 'israel', 'iran', 'taiwan', 'election', 'ukraine', 'gaza', 'border', 'military'],
                "MACRO": ['fed', 'rate', 'inflation', 'cpi', 'jobs', 'recession', 'gdp', 'fomc'],
                "CRYPTO": ['bitcoin', 'crypto', 'btc', 'eth', 'solana', 'nft'],
                "TECH": ['apple', 'nvidia', 'microsoft', 'google', 'meta', 'tesla', 'amazon', 'ai', 'tech']
            }

            BLACKLIST = ['nfl', 'nba', 'super bowl', 'box office', 'pop', 'music', 'song', 'artist', 'movie', 'film', 'grammy', 'oscar', 'sport', 'football', 'basketball', 'soccer', 'tennis', 'golf']
            
            clean_markets = []
            for event in events:
                title = event.get('title', '')
                title_lower = title.lower()

                # 1. Blacklist Check
                if any(bad in title_lower for bad in BLACKLIST): continue
                
                # 2. Determine Category (Strict Regex)
                category = "OTHER"
                for cat, keys in KEYWORDS.items():
                    # Match whole words only (e.g. "AI" matches "AI", but not "Saints")
                    if any(re.search(r'\b' + re.escape(k) + r'\b', title_lower) for k in keys):
                        category = cat
                        break
                
                # Filter: Only show relevant categories
                if category == "OTHER": continue
                
                markets = event.get('markets', [])
                if not markets: continue
                
                # Take first market
                m = markets[0]
                try:
                    outcomes = json.loads(m['outcomes']) if isinstance(m['outcomes'], str) else m['outcomes']
                    prices = json.loads(m['outcomePrices']) if isinstance(m['outcomePrices'], str) else m['outcomePrices']
                    
                    if len(outcomes) >= 2 and len(prices) >= 2:
                        # Pair outcomes with prices
                        outcome_data = []
                        for i in range(len(outcomes)):
                            try:
                                price = float(prices[i])
                                label = str(outcomes[i])
                                outcome_data.append({"label": label, "price": price})
                            except: continue
                        
                        # Sort by price (probability) descending
                        outcome_data.sort(key=lambda x: x['price'], reverse=True)
                        
                        # Take Top 2
                        if len(outcome_data) < 2: continue
                        
                        top1 = outcome_data[0]
                        top2 = outcome_data[1]
                        
                        prob1 = top1['price']
                        prob2 = top2['price']
                        
                        # Delta
                        mid = m.get('id', '')
                        last_prob = POLY_STATE.get(mid, prob1)
                        delta = prob1 - last_prob
                        POLY_STATE[mid] = prob1
                        # Volatility Threshold (5% move)
                        is_volatile = abs(delta) >= 0.05
                        
                        # Volume & Liquidity
                        vol = float(m.get('volume', 0))
                        liq = float(m.get('liquidity', 0))
                        
                        def format_money(val):
                            if val >= 1_000_000: return f"${val/1_000_000:.1f}M"
                            if val >= 1_000: return f"${val/1_000:.0f}k"
                            return f"${val:.0f}"
                        
                        category = event.get('category', 'General') # Assuming category is available in event
                        clean_markets.append({
                            "event": title,
                            "category": category,
                            "is_volatile": is_volatile,
                            "volume": format_money(vol),
                            "liquidity": format_money(liq),
                            "outcome_1_label": top1['label'],
                            "outcome_1_prob": int(prob1 * 100),
                            "outcome_2_label": top2['label'],
                            "outcome_2_prob": int(prob2 * 100),
                            "slug": event.get('slug', ''),
                            "delta": delta
                        })
                except: continue
            
            CACHE["polymarket"]["data"] = clean_markets[:15]
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
        # Direct VIX fetch for simplicity in Flask (avoid subprocess if possible, but keeping logic)
        # We can use yfinance directly here instead of subprocess for cleaner Flask app
        vix = yf.Ticker("^VIX")
        try:
            vix_val = vix.fast_info['last_price']
        except:
            vix_val = vix.history(period="1d")['Close'].iloc[-1]
            
        score = 100 - ((vix_val - 10) / 30 * 100)
        score = max(0, min(100, score))
        
        if score >= 80: rating = "Extreme Greed"
        elif score >= 60: rating = "Greed"
        elif score >= 40: rating = "Neutral"
        elif score >= 20: rating = "Fear"
        else: rating = "Extreme Fear"
        
        data = {"value": round(score), "rating": rating, "vix_reference": round(vix_val, 2)}
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
    
    # Cache for 5 minutes (300s)
    if "heatmap" in CACHE and current_time - CACHE["heatmap"]["timestamp"] < 300:
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
                last = t.fast_info.last_price
                prev = t.fast_info.previous_close
                
                if last and prev:
                    change = ((last - prev) / prev) * 100
                    heatmap_data.append({
                        "symbol": symbol,
                        "change": round(change, 2),
                        "price": round(last, 2),
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    print(f"🚀 PigmentOS Flask Server running on port {port}", flush=True)
    app.run(host='0.0.0.0', port=port, threaded=True)
