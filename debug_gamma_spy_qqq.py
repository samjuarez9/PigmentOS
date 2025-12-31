from run import fetch_options_chain_polygon, parse_polygon_to_gamma_format, get_finnhub_price
import json
import os

# Ensure API keys are set (they should be in the environment, but just in case)
# You might need to source .env or similar if running locally, but here I assume the environment is set up like run.py expects.

def debug_ticker(symbol):
    print(f"\n--- Debugging {symbol} ---")
    
    # 1. Check Price
    print(f"Fetching price for {symbol}...")
    price = get_finnhub_price(symbol)
    print(f"Price: {price}")
    
    # 2. Fetch Options Chain
    print(f"Fetching options chain for {symbol}...")
    data = fetch_options_chain_polygon(symbol)
    
    if data:
        print("Fetch successful!")
        print(f"Results count: {len(data.get('results', []))}")
        print(f"Expiry used: {data.get('_expiry_date')}")
        print(f"Is Next Trading Day: {data.get('_is_next_trading_day')}")
        
        # 3. Parse Data
        print("Parsing data...")
        gamma_data, underlying = parse_polygon_to_gamma_format(data, current_price=price)
        print(f"Parsed Underlying Price: {underlying}")
        print(f"Strikes found: {len(gamma_data)}")
        
        # Show a sample strike
        if gamma_data:
            first_strike = list(gamma_data.keys())[0]
            print(f"Sample Strike {first_strike}: {gamma_data[first_strike]}")
            
            # Check for empty data
            total_vol = sum(d['call_vol'] + d['put_vol'] for d in gamma_data.values())
            total_oi = sum(d['call_oi'] + d['put_oi'] for d in gamma_data.values())
            print(f"Total Volume: {total_vol}")
            print(f"Total OI: {total_oi}")
            
            if total_vol == 0 and total_oi == 0:
                print("⚠️ WARNING: Data is empty (0 Vol, 0 OI).")
    else:
        print("❌ Fetch failed (returned None).")

if __name__ == "__main__":
    debug_ticker("SPY")
    debug_ticker("QQQ")
