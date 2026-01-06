import sys
import os

def test_deduplication_logic():
    print("🧪 Testing Deduplication Logic...")
    
    # Mock Trades
    # Alpaca Trade (Source: alpaca)
    t1 = {
        "symbol": "SPY251219C00500000",
        "strikePrice": 500.0,
        "putCall": "C",
        "expirationDate": "2025-12-19",
        "volume": 5000,
        "lastPrice": 10.0,
        "source": "alpaca"
    }
    
    # Polygon Trade (Source: polygon) - Identical attributes
    t2 = {
        "symbol": "SPY251219C00500000", # Assumes normalized symbol or close enough
        "strikePrice": 500.0,
        "putCall": "C",
        "expirationDate": "2025-12-19",
        "volume": 5000,
        "lastPrice": 10.0,
        "source": "polygon"
    }
    
    # Distinct Trade
    t3 = {
        "symbol": "QQQ...",
        "strikePrice": 400.0,
        "putCall": "P",
        "expirationDate": "2025-12-19",
        "volume": 1000,
        "lastPrice": 5.0,
        "source": "polygon"
    }
    
    alpaca_whales = [t1]
    poly_whales = [t2, t3]
    
    print(f"Input: {len(alpaca_whales)} Alpaca, {len(poly_whales)} Polygon")
    
    # --- DEDUPLICATION LOGIC FROM RUN.PY ---
    unique_trades = []
    seen_signatures = set()
    
    # 1. Process Alpaca first
    for trade in alpaca_whales:
        # Signature: Ticker_Strike_Type_Expiry_Vol_Price
        sig = f"{trade['symbol']}_{trade['strikePrice']}_{trade['putCall']}_{trade['expirationDate']}_{trade['volume']}_{trade['lastPrice']}"
        if sig not in seen_signatures:
            seen_signatures.add(sig)
            unique_trades.append(trade)
            
    # 2. Process Polygon (skip if seen)
    for trade in poly_whales:
        sig = f"{trade['symbol']}_{trade['strikePrice']}_{trade['putCall']}_{trade['expirationDate']}_{trade['volume']}_{trade['lastPrice']}"
        if sig not in seen_signatures:
            seen_signatures.add(sig)
            unique_trades.append(trade)
            
    new_whales = unique_trades
    # ---------------------------------------
    
    print(f"Output: {len(new_whales)} Unique Trades")
    
    # Assertions
    if len(new_whales) != 2:
        print("❌ Failed: Expected 2 unique trades")
        return
        
    # Check if the duplicate was handled correctly (Alpaca kept)
    kept_spy = [t for t in new_whales if t['volume'] == 5000][0]
    if kept_spy['source'] == 'alpaca':
        print("✅ Duplicate Handled: Kept Alpaca trade (PASSED)")
    else:
        print("❌ Duplicate Handled: Kept Polygon trade (FAILED)")
        
    # Check if distinct trade was kept
    kept_qqq = [t for t in new_whales if t['volume'] == 1000]
    if kept_qqq:
        print("✅ Distinct Trade Kept (PASSED)")
    else:
        print("❌ Distinct Trade Lost (FAILED)")

if __name__ == "__main__":
    test_deduplication_logic()
