import sys
import os
import time
from datetime import datetime
import pytz
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath("/Users/newuser/PigmentOS"))

# Mock environment variables
os.environ["ALPACA_API_KEY"] = "test_key"
os.environ["ALPACA_SECRET_KEY"] = "test_secret"
os.environ["POLYGON_API_KEY"] = "test_poly"

import run

def test_overlap():
    print("🧪 Testing Data Overlap between Polygon and Alpaca...")
    
    # Reset History
    run.WHALE_HISTORY = {}
    
    # Common Trade Details
    symbol = "SPY"
    strike = 500.0
    expiry = "2025-12-19"
    # Polygon format ticker: O:SPY251219C00500000
    # Alpaca format ticker: SPY251219C00500000
    poly_ticker = "O:SPY251219C00500000"
    alpaca_ticker = "SPY251219C00500000"
    
    volume = 5000
    price = 10.0
    premium = volume * price * 100 # $5M
    
    # Mock Polygon Response
    mock_poly_data = {
        "results": [{
            "details": {
                "ticker": poly_ticker,
                "strike_price": strike,
                "contract_type": "call",
                "expiration_date": expiry
            },
            "day": {
                "volume": volume,
                "close": price,
                "vwap": price
            },
            "greeks": {"delta": 0.5},
            "open_interest": 10000
        }],
        "_current_price": 505.0
    }
    
    # Mock Alpaca Response
    # Alpaca returns a dict of snapshots keyed by symbol
    mock_alpaca_data = {
        "snapshots": {
            alpaca_ticker: {
                "dailyBar": {"v": volume},
                "latestTrade": {
                    "p": price,
                    "t": datetime.now(pytz.utc).isoformat() # Real timestamp
                },
                "latestQuote": {"bp": 9.9, "ap": 10.1}
            }
        }
    }
    
    # Patch functions
    with patch('run.fetch_unusual_options_polygon', return_value=mock_poly_data):
        print("\n--- Scanning Polygon ---")
        poly_whales = run.scan_whales_polygon()
        print(f"Polygon found {len(poly_whales)} trades")
        if poly_whales:
            print(f"Polygon ID: {poly_whales[0].get('symbol')}_{poly_whales[0].get('volume')}_{poly_whales[0].get('lastPrice')}")

    with patch('requests.get') as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_alpaca_data
        
        # Mock get_cached_price for Alpaca
        with patch('run.get_cached_price', return_value=505.0):
            print("\n--- Scanning Alpaca ---")
            alpaca_whales = run.scan_whales_alpaca()
            print(f"Alpaca found {len(alpaca_whales)} trades")
            if alpaca_whales:
                # Reconstruct ID logic from run.py for verification
                # trade_id = f"{option_symbol}_{trade_time_str}"
                pass

    # Check for duplicates in the combined list
    combined = poly_whales + alpaca_whales
    print(f"\nTotal Combined Trades: {len(combined)}")
    
    # Check if they are effectively the same
    if len(combined) == 2:
        t1 = combined[0]
        t2 = combined[1]
        
        print("\nComparison:")
        print(f"Trade 1 Source: {t1.get('source')} | Vol: {t1['volume']} | Price: {t1['lastPrice']}")
        print(f"Trade 2 Source: {t2.get('source', 'alpaca')} | Vol: {t2['volume']} | Price: {t2['lastPrice']}")
        
        if t1['volume'] == t2['volume'] and t1['lastPrice'] == t2['lastPrice']:
            print("\n⚠️ DUPLICATE DETECTED! Same trade counted twice due to different ID logic.")
        else:
            print("\n✅ No duplicate detected (attributes differ).")
    else:
        print("\n✅ No duplicate detected (count != 2).")

if __name__ == "__main__":
    test_overlap()
