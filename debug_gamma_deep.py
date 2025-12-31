from run import fetch_options_chain_polygon, parse_polygon_to_gamma_format, get_finnhub_price
import json

def deep_debug_ticker(symbol):
    print(f"\n========================================")
    print(f"   DEEP DEBUG: {symbol}")
    print(f"========================================")
    
    price = get_finnhub_price(symbol)
    print(f"Price: {price}")
    
    print("Fetching Polygon Data...")
    data = fetch_options_chain_polygon(symbol)
    
    if not data:
        print("❌ Fetch failed.")
        return

    results = data.get("results", [])
    print(f"Raw Results Count: {len(results)}")
    
    # 1. Analyze Raw Data for Calls
    raw_calls = [r for r in results if r.get("details", {}).get("contract_type") == "call"]
    raw_puts = [r for r in results if r.get("details", {}).get("contract_type") == "put"]
    
    print(f"Raw Calls: {len(raw_calls)}")
    print(f"Raw Puts: {len(raw_puts)}")
    
    raw_call_vol = sum(r.get("day", {}).get("volume", 0) or 0 for r in raw_calls)
    raw_put_vol = sum(r.get("day", {}).get("volume", 0) or 0 for r in raw_puts)
    
    print(f"Raw Call Volume: {raw_call_vol}")
    print(f"Raw Put Volume:  {raw_put_vol}")
    
    if raw_call_vol == 0:
        print("⚠️ CRITICAL: Polygon returned 0 volume for ALL calls.")
        if raw_calls:
            print("Sample Raw Call:", json.dumps(raw_calls[0], indent=2))
            
    # 2. Analyze Parsed Data
    print("\nParsing Data...")
    gamma_data, _ = parse_polygon_to_gamma_format(data, current_price=price)
    
    parsed_call_vol = sum(d['call_vol'] for d in gamma_data.values())
    parsed_put_vol = sum(d['put_vol'] for d in gamma_data.values())
    
    print(f"Parsed Call Vol: {parsed_call_vol}")
    print(f"Parsed Put Vol:  {parsed_put_vol}")
    
    # 3. Top Strikes & Outliers
    print("\nTop 5 Strikes by Call Volume:")
    sorted_by_call = sorted(gamma_data.items(), key=lambda x: x[1]['call_vol'], reverse=True)[:5]
    for strike, d in sorted_by_call:
        print(f"  Strike {strike}: Call Vol={d['call_vol']}, Put Vol={d['put_vol']}, Call OI={d['call_oi']}")
        
    print("\nTop 5 Strikes by Put Volume:")
    sorted_by_put = sorted(gamma_data.items(), key=lambda x: x[1]['put_vol'], reverse=True)[:5]
    for strike, d in sorted_by_put:
        print(f"  Strike {strike}: Put Vol={d['put_vol']}, Call Vol={d['call_vol']}, Put OI={d['put_oi']}")
        
    max_call = max(d['call_vol'] for d in gamma_data.values()) if gamma_data else 0
    max_put = max(d['put_vol'] for d in gamma_data.values()) if gamma_data else 0
    global_max = max(max_call, max_put)
    
    print(f"\nMAX Call: {max_call}")
    print(f"MAX Put:  {max_put}")
    print(f"Global Max (Scaling Base): {global_max}")
    
    if max_call < global_max * 0.1:
        print("⚠️ Call bars will be tiny (<10% width) due to Put dominance.")
    if max_put < global_max * 0.1:
        print("⚠️ Put bars will be tiny (<10% width) due to Call dominance.")

if __name__ == "__main__":
    deep_debug_ticker("SPY")
    deep_debug_ticker("QQQ")
