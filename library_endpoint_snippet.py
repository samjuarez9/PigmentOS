
@app.route('/api/library/options')
def api_library_options():
    """
    Fetch full option chain for a specific ticker (0-30 DTE) from Polygon.
    Used for the "Upcoming Options Library" visualization.
    """
    symbol = request.args.get('symbol')
    if not symbol:
        return jsonify({"error": "Symbol required"}), 400
        
    if not POLYGON_API_KEY:
        return jsonify({"error": "Polygon API key missing"}), 500

    # Cache Key (Symbol + Date + Hour to keep it relatively fresh but cached)
    # 5-minute cache seems appropriate for "Library" view
    current_time = time.time()
    cache_key = f"library_{symbol}"
    
    # Check Cache (Simple in-memory for now, could use file if needed)
    # We'll reuse the main CACHE dict but add a new section if needed or just use a separate dict
    # Let's use a separate global for library cache to avoid cluttering the main one
    global LIBRARY_CACHE
    if 'LIBRARY_CACHE' not in globals():
        LIBRARY_CACHE = {}
        
    if cache_key in LIBRARY_CACHE:
        cached = LIBRARY_CACHE[cache_key]
        if current_time - cached['timestamp'] < 300: # 5 mins
            return jsonify(cached['data'])

    try:
        # Fetch Logic (Similar to estimation script)
        # 1. Get Contracts (Reference) - actually, for visualization we might want the Snapshot directly
        # to get Volume/OI/Greeks immediately.
        # The estimation script showed Snapshot is efficient enough (~4 calls for 1000 contracts).
        
        tz_eastern = pytz.timezone('US/Eastern')
        now_et = datetime.now(tz_eastern)
        end_date = now_et + timedelta(days=30)
        
        url = f"https://api.polygon.io/v3/snapshot/options/{symbol}"
        params = {
            "apiKey": POLYGON_API_KEY,
            "limit": 250,
            "expiration_date.gte": now_et.strftime("%Y-%m-%d"),
            "expiration_date.lte": end_date.strftime("%Y-%m-%d"),
            "order": "asc",
            "sort": "expiration_date"
        }
        
        all_results = []
        
        while True:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code != 200:
                print(f"Library Fetch Error: {resp.status_code}")
                break
                
            data = resp.json()
            results = data.get("results", [])
            all_results.extend(results)
            
            # Pagination
            # Polygon v3 Snapshot usually doesn't paginate via next_url in the same way as Reference?
            # Wait, Snapshot endpoint DOES NOT support pagination in the same way as Reference.
            # It returns everything matching the query up to the limit?
            # Actually, the docs say "Pagination: The response will include a next_url..."
            # Let's assume it does.
            
            if data.get("next_url"):
                url = data["next_url"] + f"&apiKey={POLYGON_API_KEY}"
                params = {} # params are in next_url
            else:
                break
                
        # Process Data for Frontend
        # Group by Expiration -> Strike
        processed = {}
        
        for contract in all_results:
            details = contract.get("details", {})
            day = contract.get("day", {})
            greeks = contract.get("greeks", {})
            
            expiry = details.get("expiration_date")
            strike = details.get("strike_price")
            type_ = details.get("contract_type") # call/put
            
            if not expiry or not strike: continue
            
            if expiry not in processed:
                processed[expiry] = []
                
            processed[expiry].append({
                "s": strike,
                "t": type_,
                "v": day.get("volume", 0) or 0,
                "oi": contract.get("open_interest", 0) or 0,
                "p": day.get("close", 0) or 0,
                "iv": contract.get("implied_volatility", 0) or 0,
                "d": greeks.get("delta", 0) or 0
            })
            
        response_data = {
            "symbol": symbol,
            "count": len(all_results),
            "data": processed,
            "timestamp": current_time
        }
        
        # Update Cache
        LIBRARY_CACHE[cache_key] = {
            "data": response_data,
            "timestamp": current_time
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Library API Error: {e}")
        return jsonify({"error": str(e)}), 500
