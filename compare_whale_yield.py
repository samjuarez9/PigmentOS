import sys
import os

# Add project root to path
sys.path.append(os.path.abspath("/Users/newuser/PigmentOS"))

# Import run (triggers gevent patching)
try:
    import run
except ImportError:
    # If run.py fails to import due to missing env vars or other issues, we might need to mock them
    print("⚠️ Warning: run.py import issues, attempting to proceed...")
    import run

def compare_whale_yield(ticker="AMD"):
    print(f"🧪 Comparing Whale Yield for {ticker}: Polygon vs Alpaca")
    
    # Override Watchlist to focus on target
    run.WHALE_WATCHLIST = [ticker]
    
    # Clear History to ensure we capture everything
    run.WHALE_HISTORY = {}
    
    print("\n1. Scanning Polygon...")
    try:
        poly_whales = run.scan_whales_polygon()
        print(f"✅ Polygon found {len(poly_whales)} qualifying whale trades")
        for w in poly_whales:
            print(f"   - {w['premium']} {w['putCall']} {w['strikePrice']} (Vol: {w['volume']})")
    except Exception as e:
        print(f"❌ Polygon Scan Failed: {e}")
        poly_whales = []

    print("\n2. Scanning Alpaca...")
    try:
        alpaca_whales = run.scan_whales_alpaca()
        print(f"✅ Alpaca found {len(alpaca_whales)} qualifying whale trades")
        for w in alpaca_whales:
            print(f"   - {w['premium']} {w['putCall']} {w['strikePrice']} (Vol: {w['volume']})")
    except Exception as e:
        print(f"❌ Alpaca Scan Failed: {e}")
        alpaca_whales = []

    # --- COMPARISON ---
    print("\n--- 📊 YIELD COMPARISON ---")
    print(f"Ticker: {ticker}")
    print(f"{'SOURCE':<15} | {'TRADES FOUND':<15}")
    print("-" * 35)
    print(f"{'Polygon':<15} | {len(poly_whales):<15}")
    print(f"{'Alpaca':<15} | {len(alpaca_whales):<15}")
    print("-" * 35)
    
    if len(poly_whales) > len(alpaca_whales):
        print("🏆 Polygon captured more whale activity.")
    elif len(alpaca_whales) > len(poly_whales):
        print("🏆 Alpaca captured more whale activity.")
    else:
        print("🤝 Both APIs captured the same amount of activity.")

if __name__ == "__main__":
    target = "AMD"
    if len(sys.argv) > 1:
        target = sys.argv[1]
    compare_whale_yield(target)
