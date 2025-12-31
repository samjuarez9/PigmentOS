from run import fetch_options_chain_polygon, get_finnhub_price
import json

def debug_upside(symbol):
    print(f"\n--- Debugging Upside for {symbol} ---")
    
    price = get_finnhub_price(symbol)
    print(f"Price: {price}")
    
    # Fetch data as run.py does (with default 20% range)
    # We need to manually replicate the range logic to see what's being requested
    strike_low = int(price * 0.80)
    strike_high = int(price * 1.20)
    print(f"Requested Range: {strike_low} - {strike_high}")
    
    data = fetch_options_chain_polygon(symbol)
    
    if data and data.get("results"):
        results = data["results"]
        print(f"Returned Count: {len(results)}")
        
        # Extract strikes
        strikes = sorted([r.get("details", {}).get("strike_price") for r in results])
        min_strike = strikes[0]
        max_strike = strikes[-1]
        
        print(f"Returned Range: {min_strike} - {max_strike}")
        
        if max_strike < price:
            print("❌ CRITICAL: Max strike is BELOW current price! Upside is truncated.")
        elif max_strike < price * 1.02:
             print("⚠️ WARNING: Max strike is barely above price (<2%). Upside limited.")
        else:
            print("✅ Upside looks okay.")
            
        # Check density
        print(f"Strike Density: {(max_strike - min_strike) / len(strikes):.2f} pts/strike")
        
    else:
        print("❌ Fetch failed.")

if __name__ == "__main__":
    debug_upside("SPY")
    debug_upside("QQQ")
