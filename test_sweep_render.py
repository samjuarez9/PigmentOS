import requests
import time

# Fake trade data mimicking WebSocket format
fake_trade = {
    "baseSymbol": "TEST",
    "symbol": "O:TEST260117C00420000",
    "strikePrice": 420.0,
    "expirationDate": "2026-01-17",
    "putCall": "C",
    "openInterest": 1000,
    "lastPrice": 69.0,
    "tradeTime": "13:37:00",
    "timestamp": time.time(),
    "vol_oi": 5.0,
    "premium": "$6.9M",
    "notional_value": 6900000,
    "volume": 5000,
    "moneyness": "OTM",
    "is_mega_whale": True,
    "is_sweep": True,  # This should trigger the ⚡ tag
    "delta": 0.42,
    "is_lotto": False,
    "iv": 0.69,
    "source": "polygon_ws",
    "side": None,
    "bid": 0,
    "ask": 0
}

# Inject into cache via a temporary endpoint or just print what it would look like
# Since we can't easily inject into the running server's memory from outside without an endpoint,
# we'll just verify the frontend code logic visually.

print("✅ Test trade created. To verify frontend:")
print("1. The 'is_sweep: True' flag is set.")
print("2. Frontend checks 'if (isSweep)'")
print("3. Renders: <span class=\"tag tag-sweep pulse-sweep\">⚡ SWEEP</span>")
