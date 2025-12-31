from run import fetch_options_chain_polygon, parse_polygon_to_gamma_format, get_finnhub_price
import json

def debug_ticker_filters(symbol):
    print(f"\n--- Debugging Filters for {symbol} ---")
    
    price = get_finnhub_price(symbol)
    data = fetch_options_chain_polygon(symbol)
    
    if data:
        gamma_data, underlying = parse_polygon_to_gamma_format(data, current_price=price)
        print(f"Total Strikes (Pre-filter): {len(gamma_data)}")
        
        MIN_VOLUME = 100
        MIN_OI = 500
        
        passed_count = 0
        filtered_vol = 0
        filtered_oi = 0
        
        for strike, d in gamma_data.items():
            total_vol = d["call_vol"] + d["put_vol"]
            total_oi = d["call_oi"] + d["put_oi"]
            
            if total_oi < MIN_OI:
                filtered_oi += 1
                continue
                
            # Relax volume filter for Indices:
            INDEX_ETFS = ['SPY', 'QQQ', 'IWM', 'DIA']
            is_index = symbol in INDEX_ETFS
            
            if not is_index and total_vol < MIN_VOLUME:
                filtered_vol += 1
                continue
                
            passed_count += 1
            
        print(f"Strikes Passing Filters: {passed_count}")
        print(f"Filtered by OI (<{MIN_OI}): {filtered_oi}")
        print(f"Filtered by Vol (<{MIN_VOLUME}): {filtered_vol}")
        
        if passed_count < 5:
            print("⚠️ VERY FEW STRIKES PASSED! This is likely the issue.")
            
    else:
        print("❌ Fetch failed.")

if __name__ == "__main__":
    debug_ticker_filters("SPY")
    debug_ticker_filters("QQQ")
