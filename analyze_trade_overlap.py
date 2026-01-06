import sys
import os
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath("/Users/newuser/PigmentOS"))

# Load env for run.py
load_dotenv("/Users/newuser/PigmentOS/.env")

# Import run (triggers gevent patching)
try:
    import run
except ImportError:
    print("⚠️ Warning: run.py import issues, attempting to proceed...")
    import run

def analyze_overlap(ticker="AMD"):
    print(f"🧪 Analyzing Trade Overlap for {ticker}")
    
    # Override Watchlist
    run.WHALE_WATCHLIST = [ticker]
    run.WHALE_HISTORY = {}
    
    # 1. Fetch Both
    print("   Fetching Polygon...")
    try:
        poly_whales = run.scan_whales_polygon()
    except: poly_whales = []
    
    print("   Fetching Alpaca...")
    try:
        alpaca_whales = run.scan_whales_alpaca()
    except: alpaca_whales = []
    
    # 2. Build Signatures
    # Sig: Strike_Type_Expiry_Vol (Price can vary slightly, so maybe exclude or round it?)
    # Let's use the strict signature from run.py first: Ticker_Strike_Type_Expiry_Vol_Price
    # But for analysis, let's be a bit looser on price to see if it's just price variance.
    
    def get_sig(w, strict_price=True):
        price = w['lastPrice']
        if not strict_price:
            price = round(price, 1) # Round to 1 decimal for loose comparison
        return f"{w['strikePrice']}_{w['putCall']}_{w['expirationDate']}_{w['volume']}_{price}"

    poly_sigs = {get_sig(w): w for w in poly_whales}
    alpaca_sigs = {get_sig(w): w for w in alpaca_whales}
    
    common = set(poly_sigs.keys()) & set(alpaca_sigs.keys())
    unique_poly = set(poly_sigs.keys()) - set(alpaca_sigs.keys())
    unique_alpaca = set(alpaca_sigs.keys()) - set(poly_sigs.keys())
    
    print("\n--- 📊 OVERLAP ANALYSIS ---")
    print(f"Total Polygon: {len(poly_whales)}")
    print(f"Total Alpaca:  {len(alpaca_whales)}")
    print(f"Exact Matches: {len(common)}")
    print(f"Unique to Poly: {len(unique_poly)}")
    print(f"Unique to Alpaca: {len(unique_alpaca)}")
    
    if unique_poly:
        print("\n--- 🔍 UNIQUE TO POLYGON ---")
        for sig in unique_poly:
            w = poly_sigs[sig]
            print(f"   {w['putCall']} ${w['strikePrice']} Exp:{w['expirationDate']} Vol:{w['volume']} @ ${w['lastPrice']}")
            
    if unique_alpaca:
        print("\n--- 🔍 UNIQUE TO ALPACA ---")
        for sig in unique_alpaca:
            w = alpaca_sigs[sig]
            print(f"   {w['putCall']} ${w['strikePrice']} Exp:{w['expirationDate']} Vol:{w['volume']} @ ${w['lastPrice']}")
            
    # Check for "Near Matches" (Same Vol/Strike/Exp, different Price)
    print("\n--- 🕵️‍♂️ INVESTIGATING DIFFERENCES ---")
    for sig in unique_poly:
        parts = sig.split('_')
        # Reconstruct partial sig: Strike_Type_Expiry_Vol
        partial_sig = "_".join(parts[:-1]) 
        
        # Check if Alpaca has this partial sig
        potential_matches = [k for k in unique_alpaca if "_".join(k.split('_')[:-1]) == partial_sig]
        if potential_matches:
            print(f"⚠️ Price Mismatch found for {partial_sig}:")
            p_price = parts[-1]
            a_price = potential_matches[0].split('_')[-1]
            print(f"   Polygon Price: ${p_price} vs Alpaca Price: ${a_price}")

if __name__ == "__main__":
    target = "AMD"
    if len(sys.argv) > 1:
        target = sys.argv[1]
    analyze_overlap(target)
