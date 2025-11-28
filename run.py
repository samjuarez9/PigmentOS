import json
import time
import random
import threading
import requests
import yfinance as yf
import pandas as pd
import statistics
from http.server import SimpleHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import urllib3
from datetime import datetime, date
import pytz
from concurrent.futures import ThreadPoolExecutor
import urllib3
import ssl

# Fix for SSL Certificate Verify Failed
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Watchlist for "Whale" Scan - Tech, AI, and FinTwit Focus
WATCHLIST = [
    # Mag 7
    "NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META", "GOOGL",
    # Semiconductors/AI
    "AMD", "AVGO", "ARM", "SMCI", "MU", "INTC",
    # FinTwit Favorites
    "PLTR", "SOFI", "RKLB",
    # Indexes
    "SPY", "QQQ", "IWM"
]

# Mega Whale threshold
MEGA_WHALE_THRESHOLD = 9_000_000  # $9M

def filter_for_whales(chain_df, current_stock_price, min_premium=2000000):
    # print(f"DEBUG: Filtering {len(chain_df)} rows...", flush=True)
    """
    Filters for 'Unusual Activity':
    1. FRESHNESS: Volume > Open Interest (New positioning).
    2. CONVICTION: Notional Value > $100k (Big money).
    3. AGGRESSION: OTM (Out of the Money) bets.
    """
    if chain_df.empty:
        return chain_df

    # === TODAY ONLY FILTER (NY Time) ===
    # Only show trades from the current trading day
    ny_tz = pytz.timezone('America/New_York')
    today_ny = datetime.now(ny_tz).date()
    
    def is_today(ts):
        try:
            # Convert to pydatetime if it's a pandas Timestamp
            if hasattr(ts, 'to_pydatetime'):
                dt = ts.to_pydatetime()
            else:
                dt = ts
            
            # Localize if naive (assume UTC as yfinance is usually UTC)
            if dt.tzinfo is None:
                dt = pytz.utc.localize(dt)
            
            # Convert to NY Time
            dt_ny = dt.astimezone(ny_tz)
            
            # Check if same day
            return dt_ny.date() == today_ny
        except Exception as e:
            print(f"Date Error: {e}", flush=True)
            return False

    # Apply Date Filter
    chain_df = chain_df[chain_df['lastTradeDate'].apply(is_today)].copy()

    if chain_df.empty:
        return chain_df

    # 1. Calculate Premium (The "Wallet" Check)
    chain_df['notional_value'] = chain_df['volume'] * chain_df['lastPrice'] * 100
    
    # 2. Calculate Vol/OI Ratio (The "Freshness" Check)
    # Handle 0 OI to avoid division errors
    chain_df['vol_oi_ratio'] = chain_df['volume'] / (chain_df['openInterest'].replace(0, 1))
    
    # --- THE WHALE FILTER ---
    # We only want rows that pass ALL strict criteria
    whales = chain_df[
        (chain_df['volume'] > chain_df['openInterest']) &      # Must be a NEW position
        (chain_df['notional_value'] >= min_premium) &          # Must be BIG money
        (chain_df['volume'] > 50)                              # Min liquidity filter
    ].copy()
    
    if whales.empty:
        return whales
        
    # 3. Classify Aggressiveness (OTM vs ITM)
    whales['moneyness'] = 'ITM'
    # Call is OTM if Strike > Price
    whales.loc[(whales['contractSymbol'].str.contains('C')) & (whales['strike'] > current_stock_price), 'moneyness'] = 'OTM'
    # Put is OTM if Strike < Price
    whales.loc[(whales['contractSymbol'].str.contains('P')) & (whales['strike'] < current_stock_price), 'moneyness'] = 'OTM'
    
    return whales.sort_values(by='lastTradeDate', ascending=False)

def fetch_ticker_options(ticker):
    try:
        stock = yf.Ticker(ticker)
        exps = stock.options
        if not exps:
            return []
        
        # Get nearest expiry
        expiry = exps[0]
        chain = stock.option_chain(expiry)
        
        # Get Current Price (Fast)
        try:
            current_price = stock.fast_info['last_price']
        except:
            current_price = stock.history(period="1d")['Close'].iloc[-1]

        # Prepare DataFrames
        calls = chain.calls.copy()
        calls['putCall'] = 'C'
        # Extract Greeks if available
        if 'delta' not in calls.columns:
            calls['delta'] = 0.0
        if 'impliedVolatility' not in calls.columns:
            calls['impliedVolatility'] = 0.0
        
        puts = chain.puts.copy()
        puts['putCall'] = 'P'
        # Extract Greeks if available
        if 'delta' not in puts.columns:
            puts['delta'] = 0.0
        if 'impliedVolatility' not in puts.columns:
            puts['impliedVolatility'] = 0.0
        
        # Combine
        full_chain = pd.concat([calls, puts])
        
        # Apply Antigravity Whale Filter
        whales = filter_for_whales(full_chain, current_price)
        
        if whales.empty:
            return []

        trades = []
        current_time = int(time.time())
        
        # Iterate Top 5 for Ticker Tape
        for i, (index, row) in enumerate(whales.iterrows()):
            # Format Premium
            premium = row['notional_value']
            if premium >= 1_000_000:
                prem_str = f"${premium/1_000_000:.1f}M"
            else:
                prem_str = f"${premium/1_000:.0f}k"

            # Format Type + Strike (Emoji + Compact)
            call_or_put = 'c' if row['putCall'] == 'C' else 'p'
            type_emoji = "🟢" if row['putCall'] == 'C' else "🔴"
            strike_str = f"{type_emoji} {int(row['strike'])}{call_or_put}"
            
            # Format Expiry (MM/DD)
            expiry_parts = expiry.split('-')  # ['2025', '11', '28']
            expiry_short = f"{expiry_parts[1]}/{expiry_parts[2]}"
            
            # Format Time (Current time for now - will be sorted by time later)
            from datetime import datetime
            trade_time = datetime.now().strftime("%H:%M")
            
            # Check if Mega Whale
            is_mega = premium >= MEGA_WHALE_THRESHOLD
            
            # Ticker Tape Output (Top 5 Only)
            if i < 5:
                if is_mega:
                    # Mega Whale Format
                    mega_prem = f"{prem_str} 💎"
                    print(f"🚨 {trade_time} | {ticker} | {mega_prem} | {strike_str} | ⚡ SUPER WHALE 🚨", flush=True)
                else:
                    # Normal Format
                    vol_oi_str = f"⚡ Vol>OI"
                    print(f"{trade_time} | {ticker} | {prem_str} | {strike_str} | {vol_oi_str}", flush=True)

            trades.append({
                "baseSymbol": ticker,
                "symbol": row['contractSymbol'],
                "strikePrice": float(row['strike']),
                "expirationDate": expiry,
                "putCall": row['putCall'],
                "volume": int(row['volume']),
                "openInterest": int(row['openInterest']),
                "lastPrice": float(row['lastPrice']),
                "tradeTime": int(row['lastTradeDate'].timestamp()), # Use ACTUAL trade time
                # New Metrics
                "vol_oi": round(row['vol_oi_ratio'], 1),
                "premium": prem_str,
                "notional_value": row['notional_value'],
                "moneyness": row['moneyness'],
                "is_mega_whale": is_mega,
                # Greeks
                "delta": round(float(row.get('delta', 0)), 3),
                "iv": round(float(row.get('impliedVolatility', 0)) * 100, 1)  # Convert to percentage
            })
            
        return trades

    except Exception as e:
        # print(f"Error fetching {ticker}: {e}", flush=True)
        return []

# Cache structure
CACHE_DURATION = 60  # 1 minute (was 300)
MACRO_CACHE_DURATION = 1800  # 30 mins for VIX

# Global State for Volatility Tracking
POLY_STATE = {}  # Maps Market ID -> Last Probability (float)

CACHE = {
    "barchart": {"data": [], "timestamp": 0},
    "vix": {"data": {"value": 0, "rating": "Neutral"}, "timestamp": 0},
    "cnn_fear_greed": {"data": {"value": 50, "rating": "Neutral"}, "timestamp": 0},
    "cnn_fear_greed": {"data": {"value": 50, "rating": "Neutral"}, "timestamp": 0},
    "polymarket": {"data": [], "timestamp": 0},
    "movers": {"data": [], "timestamp": 0}
}


# Polymarket Filtering Logic
POLYMARKET_CATEGORY_WHITELIST = ["Business", "Economics", "Politics", "Tech", "Finance", "Global Events"]

POLYMARKET_KEYWORD_WHITELIST = [
    # Macro Data
    "Fed", "Rate", "Powell", "Inflation", "CPI", "PCE", "GDP", "Recession", "Unemployment", "Jobs", "Yield",
    # Market & Assets
    "S&P", "Nasdaq", "Stock", "IPO", "Market", "Oil", "Gold", "Energy", "Dollar",
    # Geopolitics & Policy
    "China", "Taiwan", "Tariff", "Tax", "Senate", "Congress", "Election", "War", "Sanction", "Military",
    
    # Mag 7 - Tickers, Companies & CEOs
    "NVIDIA", "NVDA", "Jensen Huang", "Huang",
    "Tesla", "TSLA", "Elon Musk", "Musk",
    "Apple", "AAPL", "Tim Cook",
    "Microsoft", "MSFT", "Satya Nadella", "Nadella",
    "Amazon", "AMZN", "Andy Jassy", "Jassy",
    "Meta", "META", "Facebook", "Mark Zuckerberg", "Zuckerberg",
    "Google", "Alphabet", "GOOGL", "Sundar Pichai", "Pichai",
    
    # AI & Semiconductors - Tickers, Companies & CEOs
    "AMD", "Lisa Su",
    "PLTR", "Palantir", "Alex Karp", "Karp",
    "AVGO", "Broadcom", "Hock Tan",
    "QCOM", "Qualcomm", "Cristiano Amon",
    "INTC", "Intel", "Pat Gelsinger", "Gelsinger",
    "MU", "Micron", "Sanjay Mehrotra",
    "ARM", "Arm Holdings", "Rene Haas",
    "ASML", "Peter Wennink",
    "TSM", "TSMC", "Taiwan Semiconductor", "C.C. Wei",
    "SMCI", "Super Micro", "Charles Liang",
    "MRVL", "Marvell", "Matt Murphy",
    
    # Crypto & Fintech
    "COIN", "Coinbase", "Brian Armstrong", "Armstrong",
    "SQ", "Block", "Jack Dorsey", "Dorsey",
    "SHOP", "Shopify", "Tobi Lutke",
    
    # Growth Tech
    "UBER", "Dara Khosrowshahi",
    "ABNB", "Airbnb", "Brian Chesky", "Chesky",
    "SNOW", "Snowflake", "Sridhar Ramaswamy",
    
    # Defense & Aerospace
    "LMT", "Lockheed Martin", "Jim Taiclet",
    "RTX", "Raytheon", "Greg Hayes",
    "BA", "Boeing", "Dave Calhoun",
    "NOC", "Northrop Grumman", "Kathy Warden",
    
    # Finance
    "JPM", "JPMorgan", "Jamie Dimon", "Dimon",
    "GS", "Goldman Sachs", "David Solomon", "Solomon",
    "BAC", "Bank of America", "Brian Moynihan", "Moynihan",
    "BRK", "Berkshire Hathaway", "Warren Buffett", "Buffett",
    
    # Index/ETF
    "SPY", "QQQ", "IWM", "VIX"
]

POLYMARKET_KEYWORD_BLACKLIST = [
    "Super Bowl", "NFL", "NBA", "MLB", "Soccer", "Football", "Premier League", 
    "Song", "Grammy", "Oscar", "Music", "Box Office", "Celebrity", "Dating", "Game", "Poker"
]

class MyHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        # Route 6: Whales SSE stream (Check FIRST to avoid prefix collision with /api/whales)
        if self.path.startswith('/api/whales/stream'):
            self.handle_whales_stream()
        # Route 1: Barchart Whales
        elif self.path.startswith('/api/whales'):
            self.handle_barchart()
        # Route 2: Polymarket Odds
        elif self.path.startswith('/api/polymarket'):
            self.handle_polymarket()
        # Route 3: CNN Fear & Greed
        elif self.path.startswith('/api/cnn-fear-greed'):
            self.handle_cnn_fear_greed()

        # Route 4: FRED VIX
        elif self.path.startswith('/api/vix'):
            self.handle_vix()

        elif self.path == '/api/movers':
            self.handle_movers()
        elif self.path == '/api/news':
            self.handle_news()
        else:
            # Serve static files
            try:
                super().do_GET()
            except Exception as e:
                print(f"Static File Error: {e}", flush=True)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'X-Requested-With, Content-Type')
        self.end_headers()

    def handle_barchart(self):
        """Serve /api/whales with optional pagination and stale flag."""
        try:
            global CACHE
            current_time = time.time()
            # Parse query params
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            limit = int(qs.get('limit', ['25'])[0])
            offset = int(qs.get('offset', ['0'])[0])
            # Determine freshness
            stale = False
            if current_time - CACHE["barchart"]["timestamp"] < CACHE_DURATION:
                data = CACHE["barchart"]["data"]
            else:
                # Attempt fresh fetch; if fails keep old data and mark stale
                try:
                    self.refresh_whales()
                    data = CACHE["barchart"]["data"]
                except Exception as e:
                    print(f"⚠️ Whales refresh failed: {e}")
                    data = CACHE["barchart"]["data"]
                    stale = True
            # Slice for pagination
            sliced = data[offset:offset+limit]
            response = {"data": sliced, "stale": stale, "timestamp": int(CACHE["barchart"]["timestamp"])}
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))
        except Exception as e:
            print(f"CRITICAL ERROR in handle_barchart: {e}", flush=True)
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        return

    def refresh_whales(self):
        """Fetches fresh options data from yfinance and updates the cache."""
        global CACHE
        
        # Watchlist tickers for whale monitoring
        WATCHLIST = ['NVDA', 'TSLA', 'AAPL', 'MSFT', 'META', 'GOOGL', 'AMZN', 'QQQ', 'SPY']
        
        all_whales = []
        
        for ticker in WATCHLIST:
            try:
                print(f"🐳 Scanning {ticker} for whales...", flush=True)
                whales = fetch_ticker_options(ticker)
                all_whales.extend(whales)
            except Exception as e:
                print(f"🐳 Error scanning {ticker}: {e}", flush=True)
                continue
        
        # Sort by TIME (Newest First)
        all_whales.sort(key=lambda x: x.get('tradeTime', 0), reverse=True)
        
        # Keep top 50
        all_whales = all_whales[:50]
        
        # Update cache
        CACHE["barchart"]["data"] = all_whales
        CACHE["barchart"]["timestamp"] = time.time()
        
        print(f"🐳 Refreshed {len(all_whales)} whale trades.", flush=True)

    def handle_polymarket(self):
        global CACHE, POLY_STATE
        current_time = time.time()

        if current_time - CACHE["polymarket"]["timestamp"] < CACHE_DURATION:
            data = CACHE["polymarket"]["data"]
        else:
            try:
                # TRENDING MARKETS - Fetch by 24h volume (breaking news)
                # Fetch more to ensure we get enough after filtering
                url = "https://gamma-api.polymarket.com/events?closed=false&limit=100&order=volume24hr&ascending=false"
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                    'Accept': 'application/json',
                }
                
                resp = requests.get(url, headers=headers, verify=False, timeout=5)
                if resp.status_code != 200:
                    raise Exception(f"API returned {resp.status_code}")
                
                events = resp.json()
                if not events or not isinstance(events, list):
                    raise Exception("Invalid response format")
                
                # Category keywords for filtering
                TECH_KEYWORDS = ['apple', 'nvidia', 'microsoft', 'google', 'meta', 'tesla', 'amazon', 'ai', 'tech', 'software', 'chip', 'semiconductor', 'openai', 'anthropic', 'spacex', 'starship', 'rocket']
                FINANCE_KEYWORDS = ['fed', 'interest rate', 'recession', 'inflation', 'stock', 'market', 's&p', 'dow', 'nasdaq', 'dollar', 'gdp', 'unemployment', 'treasury', 'bond', 'economy', 'economic', 'wall street', 'bank', 'financial']
                
                # Crypto blacklist - exclude all crypto markets
                CRYPTO_BLACKLIST = ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'blockchain', 'coin', 'token', 'solana', 'cardano', 'ripple', 'xrp', 'dogecoin', 'shiba', 'polygon', 'matic', 'avalanche', 'avax']
                
                clean_markets = []
                
                for event in events:
                    try:
                        title = event.get('title', '')
                        if not title:
                            continue
                        
                        title_lower = title.lower()
                        
                        # CRYPTO BLACKLIST CHECK - Skip if crypto-related
                        if any(crypto_term in title_lower for crypto_term in CRYPTO_BLACKLIST):
                            continue
                        
                        # CATEGORY FILTER: Only Tech and Finance (no politics, no crypto)
                        is_tech = any(keyword in title_lower for keyword in TECH_KEYWORDS)
                        is_finance = any(keyword in title_lower for keyword in FINANCE_KEYWORDS)
                        
                        if not (is_tech or is_finance):
                            continue
                        
                        markets = event.get('markets', [])
                        if not markets:
                            continue
                        
                        # For multi-outcome markets (like Fed decision), aggregate all sub-markets
                        if len(markets) > 2:
                            # This is likely a multi-outcome market
                            all_outcomes = []
                            for sub_market in markets:
                                question = sub_market.get('question', '')
                                prices_str = sub_market.get('outcomePrices')
                                outcomes_str = sub_market.get('outcomes')
                                
                                try:
                                    if isinstance(prices_str, str):
                                        prices = json.loads(prices_str)
                                    else:
                                        prices = prices_str
                                    
                                    if isinstance(outcomes_str, str):
                                        outcomes = json.loads(outcomes_str)
                                    else:
                                        outcomes = outcomes_str
                                    
                                    # Extract the outcome label from the question
                                    # e.g., "Fed decreases interest rates by 25 bps?" -> "25 bps cut"
                                    if '25 bps' in question or '25+ bps' in question:
                                        label = "25 bps cut"
                                    elif '50 bps' in question or '50+ bps' in question:
                                        label = "50+ bps cut"
                                    elif 'No change' in question or 'no change' in question:
                                        label = "No change"
                                    elif 'increase' in question.lower():
                                        label = "Rate increase"
                                    else:
                                        # Use the Yes probability for this bracket
                                        label = question.split('?')[0].replace('Fed ', '').strip()
                                    
                                    # Get the "Yes" probability (assuming index 0 is Yes)
                                    yes_prob = float(prices[0]) if prices and len(prices) > 0 else 0
                                    all_outcomes.append({
                                        "label": label,
                                        "prob": yes_prob
                                    })
                                except:
                                    continue
                            
                            # Sort and get top 2
                            all_outcomes.sort(key=lambda x: x['prob'], reverse=True)
                            if len(all_outcomes) < 2:
                                continue
                            
                            top_1 = all_outcomes[0]
                            top_2 = all_outcomes[1]
                            market = markets[0] # Assign market for ID tracking
                        else:
                            # Regular binary market
                            market = markets[0]
                            
                            # Parse outcomes
                            outcomes = market.get('outcomes')
                            if isinstance(outcomes, str):
                                try:
                                    outcomes = json.loads(outcomes)
                                except:
                                    continue
                            
                            if not outcomes or not isinstance(outcomes, list):
                                continue
                            
                            # Parse prices
                            prices_str = market.get('outcomePrices')
                            try:
                                if isinstance(prices_str, str):
                                    prices = json.loads(prices_str)
                                elif isinstance(prices_str, list):
                                    prices = prices_str
                                else:
                                    continue
                            except:
                                continue
                            
                            # Build outcome data
                            outcome_data = []
                            for i, price_str in enumerate(prices):
                                try:
                                    prob = float(price_str)
                                    outcome_data.append({
                                        "label": str(outcomes[i]),
                                        "prob": prob
                                    })
                                except:
                                    continue
                            
                            # Sort by probability
                            outcome_data.sort(key=lambda x: x['prob'], reverse=True)
                            
                            if len(outcome_data) < 2:
                                continue
                            
                            top_1 = outcome_data[0]
                            top_2 = outcome_data[1]
                        
                        # Track delta
                        market_id = market.get('id', '')
                        last_prob = POLY_STATE.get(market_id, top_1['prob'])
                        delta = top_1['prob'] - last_prob
                        POLY_STATE[market_id] = top_1['prob']
                        
                        volume = float(event.get('volume', 0))
                        volume24hr = float(event.get('volume24hr', 0))
                        slug = event.get('slug', '')
                        
                        clean_markets.append({
                            "event": title,
                            "outcome_1_label": top_1['label'],
                            "outcome_1_prob": int(top_1['prob'] * 100),
                            "outcome_2_label": top_2['label'],
                            "outcome_2_prob": int(top_2['prob'] * 100),
                            "volume": volume,
                            "volume24hr": volume24hr,
                            "slug": slug,
                            "delta": delta
                        })
                    except Exception as e:
                        print(f"Failed to process market {event.get('title', 'unknown')}: {e}")
                        continue
                
                # Already sorted by volume24hr from API, take top 15
                data = clean_markets[:15]
                
                CACHE["polymarket"]["data"] = data
                CACHE["polymarket"]["timestamp"] = current_time
                CACHE["polymarket"]["is_mock"] = False
            except Exception as e:
                print(f"Polymarket Error: {e}", flush=True)
                # Fallback to mock data
                data = [
                    {"event": "Will Trump win 2024 election?", "outcome_1_label": "Yes", "outcome_1_prob": 52, "outcome_2_label": "No", "outcome_2_prob": 48, "slug": "trump-2024", "delta": 0},
                    {"event": "Will Bitcoin hit $100k in 2024?", "outcome_1_label": "Yes", "outcome_1_prob": 68, "outcome_2_label": "No", "outcome_2_prob": 32, "slug": "btc-100k", "delta": 0.06},
                    {"event": "Fed rate cut in December 2024?", "outcome_1_label": "25bps", "outcome_1_prob": 75, "outcome_2_label": "No Cut", "outcome_2_prob": 25, "slug": "fed-cut-dec", "delta": -0.02},
                    {"event": "S&P 500 above 6000 by end of 2024?", "outcome_1_label": "Yes", "outcome_1_prob": 45, "outcome_2_label": "No", "outcome_2_prob": 55, "slug": "sp500-6k", "delta": 0.01},
                    {"event": "NVDA market cap exceeds $4T in 2025?", "outcome_1_label": "Yes", "outcome_1_prob": 38, "outcome_2_label": "No", "outcome_2_prob": 62, "slug": "nvda-4t", "delta": 0},
                ]
                CACHE["polymarket"]["is_mock"] = True

        # Return response with is_mock flag
        response_data = {
            "data": data,
            "is_mock": CACHE["polymarket"].get("is_mock", False)
        }

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(response_data).encode('utf-8'))

    def handle_whales_stream(self):
        """Server‑Sent Events stream for whales data.
        Sends the full payload (including stale flag) every CACHE_DURATION seconds.
        """
        print("🐳 SSE Client Connected", flush=True)
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        try:
            # Send initial ping to confirm connection
            self.wfile.write(b": ping\n\n")
            self.wfile.flush()
            
            # Immediate refresh if cache is old/empty
            current_time = time.time()
            cache_age = current_time - CACHE["barchart"]["timestamp"]
            if cache_age >= CACHE_DURATION or len(CACHE["barchart"]["data"]) == 0:
                print(f"🐳 SSE Initial Refresh (cache age: {int(cache_age)}s, items: {len(CACHE['barchart']['data'])})", flush=True)
                self.refresh_whales()
            else:
                print(f"🐳 Using cached data ({len(CACHE['barchart']['data'])} items, {int(cache_age)}s old)", flush=True)
            
            # Send initial data immediately
            data = CACHE["barchart"]["data"]
            response = {"data": data, "stale": False, "timestamp": int(CACHE["barchart"]["timestamp"])}
            payload = f"data: {json.dumps(response)}\n\n"
            self.wfile.write(payload.encode('utf-8'))
            self.wfile.flush()
            print(f"🐳 Sent initial data: {len(data)} trades", flush=True)
            
            # Continue streaming updates
            while True:
                time.sleep(CACHE_DURATION)
                
                # Refresh cache
                current_time = time.time()
                print("🐳 SSE Triggering Periodic Refresh...", flush=True)
                self.refresh_whales()
                
                data = CACHE["barchart"]["data"]
                response = {"data": data, "stale": False, "timestamp": int(CACHE["barchart"]["timestamp"])}
                payload = f"data: {json.dumps(response)}\n\n"
                try:
                    self.wfile.write(payload.encode('utf-8'))
                    self.wfile.flush()
                    print(f"🐳 Sent periodic update: {len(data)} trades", flush=True)
                except BrokenPipeError:
                    print("🐳 SSE Client Disconnected", flush=True)
                    break
                
        except Exception as e:
            print(f"🐳 SSE connection closed: {e}", flush=True)

    def handle_vix(self):
        global CACHE
        current_time = time.time()
        # USER API KEY
        FRED_KEY = "9832f887b004951ec7d53cb78f1063a0"

        if current_time - CACHE["vix"]["timestamp"] < MACRO_CACHE_DURATION:
            print("Serving VIX from Cache")
            data = CACHE["vix"]["data"]
        else:
            print("Fetching fresh VIX data...")
            try:
                url = f"https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&api_key={FRED_KEY}&file_type=json&sort_order=desc&limit=1"
                resp = requests.get(url, timeout=5)
                data = resp.json()
                CACHE["vix"]["data"] = data
                CACHE["vix"]["timestamp"] = current_time
            except Exception as e:
                print(f"VIX Error: {e}")
                data = {"error": str(e)}

        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))
        except Exception as e:
            print(f"Error sending VIX response: {e}")

    def handle_cnn_fear_greed(self):
        """
        Fetch VIX and convert to Fear & Greed Score (0-100).
        Source: Yahoo Finance (via subprocess script)
        Formula: Linear mapping of VIX 10-40 to Score 100-0.
        """
        global CACHE
        current_time = time.time()
        
        # Check cache (5 mins = 300 seconds)
        if "cnn_fear_greed" in CACHE:
            if current_time - CACHE["cnn_fear_greed"]["timestamp"] < 300:
                print("Serving cached VIX-based Fear & Greed", flush=True)
                data = CACHE["cnn_fear_greed"]["data"]
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode('utf-8'))
                return
        
        try:
            # Fetch VIX using external script to bypass SSL issues in server process
            print("Fetching fresh VIX (Subprocess) for Fear & Greed...", flush=True)
            
            import subprocess
            result = subprocess.check_output(["python3", "fetch_vix.py"], cwd="/Users/newuser/PigmentOS")
            vix_val = float(result.decode().strip())
            
            # === NORMALIZE VIX TO 0-100 SCORE ===
            # VIX 10 = Extreme Greed (Score 100)
            # VIX 40 = Extreme Fear (Score 0)
            # Formula: Score = 100 - ((VIX - 10) / (30) * 100)
            
            score = 100 - ((vix_val - 10) / 30 * 100)
            
            # Clamp to 0-100
            score = max(0, min(100, score))
            
            # Determine Rating (Adjusted thresholds for more realistic ratings)
            if score >= 80: rating = "Extreme Greed"  # VIX < 13.3
            elif score >= 60: rating = "Greed"         # VIX 13.3-22
            elif score >= 40: rating = "Neutral"       # VIX 22-28
            elif score >= 20: rating = "Fear"          # VIX 28-34
            else: rating = "Extreme Fear"              # VIX > 34
            
            # Construct response
            response_data = {
                "value": round(score),
                "rating": rating,
                "vix_reference": round(vix_val, 2)
            }
            
            # Cache the result
            CACHE["cnn_fear_greed"] = {
                "data": response_data,
                "timestamp": current_time
            }
            
            print(f"VIX-based Fear & Greed: VIX {vix_val:.2f} -> Score {round(score)} ({rating})", flush=True)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode())
            
        except Exception as e:
            print(f"Error fetching VIX-based Fear & Greed: {e}", flush=True)
            # Return fallback (Neutral)
            data = {"value": 50, "rating": "Neutral"}
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())



    def handle_movers(self):
        """Fetches 1-day performance for curated tickers and returns top gainers/losers."""
        global CACHE
        current_time = time.time()
        
        # Curated list for "Top Movers" (High interest stocks)
        MOVERS_TICKERS = [
            "NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META", "GOOGL", # Mag 7
            "AMD", "AVGO", "ARM", "SMCI", "MU", "INTC", "QCOM",      # Semis
            "PLTR", "SOFI", "RKLB", "COIN", "MSTR", "HOOD",          # FinTwit / Crypto
            "SPY", "QQQ", "IWM", "DIA",                              # Indexes
            "NFLX", "DIS", "WMT", "TGT", "COST", "JPM", "GS",        # Blue Chips
            "GME", "AMC",                                            # Memes
            # HOUSEHOLD NAMES - Retail & Consumer
            "HD", "LOW", "TJX", "SBUX", "MCD", "YUM", "CMG", "DKNG",
            "PG", "KO", "PEP", "NKE", "LULU", "ULTA", "EL",
            # Tech & Software
            "ORCL", "CRM", "ADBE", "NOW", "SHOP", "SQ", "UBER", "LYFT", "ABNB", "DASH",
            # Media & Gaming
            "SPOT", "RBLX", "EA", "TTWO",
            # Finance & Payments
            "V", "MA", "AXP", "PYPL", "C", "BAC", "WFC", "MS",
            # Healthcare
            "JNJ", "UNH", "CVS", "PFE", "ABBV", "LLY", "MRK",
            # Auto
            "F", "GM", "RIVN", "LCID",
            # Energy
            "XOM", "CVX", "SLB",
            # Industrial
            "BA", "CAT", "DE", "UPS", "FDX",
            # Telecom
            "T", "VZ", "TMUS"
        ]
        
        # Cache for 1 minute (60 seconds) - LIVE FEEL
        if current_time - CACHE["movers"]["timestamp"] < 60 and CACHE["movers"]["data"]:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(CACHE["movers"]["data"]).encode('utf-8'))
            return

        try:
            # Fetch data for all tickers at once (efficient)
            print(f"Fetching movers data for {len(MOVERS_TICKERS)} tickers...")
            
            movers = []
            tickers_obj = yf.Tickers(" ".join(MOVERS_TICKERS))
            
            for symbol in MOVERS_TICKERS:
                try:
                    ticker = tickers_obj.tickers[symbol]
                    # fast_info is much faster than .info
                    last_price = ticker.fast_info.last_price
                    prev_close = ticker.fast_info.previous_close
                    
                    if last_price and prev_close:
                        change_pct = ((last_price - prev_close) / prev_close) * 100
                        movers.append({
                            "symbol": symbol,
                            "change": round(change_pct, 2),
                            "price": round(last_price, 2),
                            "type": "gain" if change_pct >= 0 else "loss"
                        })
                except Exception as e:
                    print(f"Error fetching {symbol}: {e}")
                    continue
            
            # Separate Gainers and Losers
            gainers = [m for m in movers if m['change'] >= 0]
            losers = [m for m in movers if m['change'] < 0]
            
            # Sort Gainers (Highest Positive First)
            gainers.sort(key=lambda x: x['change'], reverse=True)
            
            # Sort Losers (Lowest Negative First - Most negative)
            losers.sort(key=lambda x: x['change'], reverse=False) # -5% is "smaller" than -1%, so sort ascending
            
            # Take Top 5 of each
            top_gainers = gainers[:5]
            top_losers = losers[:5] # These are the biggest losers
            
            # Combine
            final_list = top_gainers + top_losers
            
            # Update cache
            CACHE["movers"]["data"] = final_list
            CACHE["movers"]["timestamp"] = current_time
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(final_list).encode('utf-8'))
            
        except Exception as e:
            print(f"Error in handle_movers: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

    def handle_news(self):
        """Fetch news from Investing.com & CNBC RSS, prioritizing Breaking News."""
        try:
            import feedparser
            import time
            import calendar # For correct UTC timestamp parsing
            from datetime import datetime
        except ImportError as e:
            print(f"Import Error in handle_news: {e}", flush=True)
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Missing dependencies"}).encode('utf-8'))
            return
        
        # Configuration
        STANDARD_RSS = [
            "https://www.investing.com/rss/stock_market_news.rss",
            "https://finance.yahoo.com/news/rssindex"
        ]
        URGENT_RSS = [
            "https://www.investing.com/rss/news.rss",
            "https://www.cnbc.com/id/100003114/device/rss/rss.html"
        ]
        
        TECH_RSS = [
            "https://techcrunch.com/feed/",
            "https://www.theverge.com/rss/index.xml"
        ]

        POLITICS_RSS = [
            "https://www.cnbc.com/id/10000113/device/rss/rss.html"
        ]
        
        # WATCHLIST is now global (defined at top of file)
        
        all_news = []
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            import requests

            # 1. Fetch Urgent News
            for url in URGENT_RSS:
                try:
                    print(f"DEBUG: Fetching Urgent RSS: {url}", flush=True)
                    response = requests.get(url, headers=headers, timeout=5)
                    print(f"DEBUG: Status Code: {response.status_code}", flush=True)
                    if response.status_code != 200: continue
                    feed = feedparser.parse(response.content)
                    print(f"DEBUG: Entries found: {len(feed.entries)}", flush=True)
                except Exception as e:
                    print(f"DEBUG: Error fetching {url}: {e}", flush=True)
                    continue
                
                if not feed.entries: continue
                
                for entry in feed.entries[:10]: # Limit urgent items per feed
                    title = entry.get('title', '')
                    # REMOVED: Prepend Breaking tag (User requested compact view)
                    # if not title.startswith("🚨"):
                    #    title = f"🚨 BREAKING: {title}"
                    
                    # Parse Timestamp (Correctly handle UTC)
                    pub_timestamp = int(time.time())
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        # feedparser returns UTC struct_time. calendar.timegm converts UTC struct_time to timestamp.
                        pub_timestamp = int(calendar.timegm(entry.published_parsed))
                        
                    all_news.append({
                        "title": title,
                        "publisher": "Breaking News",
                        "link": entry.get('link', ''),
                        "time": pub_timestamp,
                        "ticker": "ALERT",
                        "priority": "urgent"
                    })

            # 2. Fetch Standard News
            for url in STANDARD_RSS:
                try:
                    print(f"DEBUG: Fetching Standard RSS: {url}", flush=True)
                    response = requests.get(url, headers=headers, timeout=5)
                    print(f"DEBUG: Status Code: {response.status_code}", flush=True)
                    if response.status_code != 200: continue
                    feed = feedparser.parse(response.content)
                    print(f"DEBUG: Entries found: {len(feed.entries)}", flush=True)
                except Exception as e:
                    print(f"DEBUG: Error fetching {url}: {e}", flush=True)
                    continue
                
                if not feed.entries: continue
                
                for entry in feed.entries[:10]:
                    title = entry.get('title', '')
                    # Filter out non-market news if needed
                    
                    pub_timestamp = int(time.time())
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_timestamp = int(calendar.timegm(entry.published_parsed))
                    
                    all_news.append({
                        "title": title,
                        "publisher": "Market Wire",
                        "link": entry.get('link', ''),
                        "time": pub_timestamp,
                        "ticker": "NEWS",
                        "priority": "standard"
                    })

            # 3. Fetch Tech News
            for url in TECH_RSS:
                try:
                    print(f"DEBUG: Fetching Tech RSS: {url}", flush=True)
                    response = requests.get(url, headers=headers, timeout=5)
                    if response.status_code != 200: continue
                    feed = feedparser.parse(response.content)
                except Exception as e:
                    continue
                
                if not feed.entries: continue
                
                for entry in feed.entries[:5]: # Limit tech items
                    title = entry.get('title', '')
                    pub_timestamp = int(time.time())
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_timestamp = int(calendar.timegm(entry.published_parsed))
                    
                    all_news.append({
                        "title": title,
                        "publisher": "Tech Wire",
                        "link": entry.get('link', ''),
                        "time": pub_timestamp,
                        "ticker": "TECH",
                        "priority": "standard"
                    })

            # 4. Fetch Politics News
            for url in POLITICS_RSS:
                try:
                    print(f"DEBUG: Fetching Politics RSS: {url}", flush=True)
                    response = requests.get(url, headers=headers, timeout=5)
                    if response.status_code != 200: continue
                    feed = feedparser.parse(response.content)
                except Exception as e:
                    continue
                
                if not feed.entries: continue
                
                for entry in feed.entries[:5]:
                    title = entry.get('title', '')
                    pub_timestamp = int(time.time())
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_timestamp = int(calendar.timegm(entry.published_parsed))
                    
                    all_news.append({
                        "title": title,
                        "publisher": "Politics",
                        "link": entry.get('link', ''),
                        "time": pub_timestamp,
                        "ticker": "GOV",
                        "priority": "standard"
                    })
            
            # Deduplicate by Title
            seen_titles = set()
            unique_news = []
            for item in all_news:
                if item['title'] not in seen_titles:
                    seen_titles.add(item['title'])
                    
                    # Sentiment Analysis
                    title_lower = item['title'].lower()
                    sentiment = "NEUTRAL"
                    if any(x in title_lower for x in ['soars', 'jumps', 'beats', 'rally', 'upgrade']):
                        sentiment = "BULLISH"
                    elif any(x in title_lower for x in ['drops', 'misses', 'plunges', 'caution', 'downgrade']):
                        sentiment = "BEARISH"
                    
                    item['sentiment'] = sentiment
                    unique_news.append(item)
            
            # Sort by Time (Newest First)
            unique_news.sort(key=lambda x: x['time'], reverse=True)
            
            # Fallback if empty
            if not unique_news:
                # Mock Data
                unique_news = [
                    {"title": "Markets await Fed decision on interest rates", "publisher": "Market Wire", "time": int(time.time()), "ticker": "FED", "priority": "urgent", "sentiment": "NEUTRAL"},
                    {"title": "NVIDIA announces new AI chip architecture", "publisher": "Tech Wire", "time": int(time.time()) - 300, "ticker": "NVDA", "priority": "standard", "sentiment": "BULLISH"},
                    {"title": "Oil prices stabilize amid geopolitical tensions", "publisher": "Market Wire", "time": int(time.time()) - 600, "ticker": "OIL", "priority": "standard", "sentiment": "NEUTRAL"}
                ]

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(unique_news).encode('utf-8'))
            
        except Exception as e:
            print(f"CRITICAL ERROR in handle_news: {e}", flush=True)
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            

if __name__ == "__main__":
    print("Starting CYBER-GRID Server on port 8001...", flush=True)
    # Use ThreadingHTTPServer to handle multiple connections (SSE blocks one thread)
    from http.server import ThreadingHTTPServer
    ThreadingHTTPServer(("", 8001), MyHandler).serve_forever()
