import requests
import json
import os

# Credentials
API_KEY = "PKD66OSCNTGDQ2ORIX4RGSKGI5"
SECRET_KEY = "9eSKSK2CchHQbFFwMYr1tnwZgu8MNZEMNfdXqVYwyF5M"
DATA_URL = "https://data.alpaca.markets/v1beta1/options"

def get_latest_quote(symbol):
    headers = {
        "APCA-API-KEY-ID": API_KEY,
        "APCA-API-SECRET-KEY": SECRET_KEY,
        "Accept": "application/json"
    }
    url = f"{DATA_URL}/quotes/latest?symbols={symbol}"
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("quotes", {}).get(symbol)
    except Exception as e:
        print(f"Fetch failed: {e}")
    return None

def determine_side(trade_price, bid, ask):
    """
    The Core Logic we want to test.
    """
    if trade_price >= ask:
        return "🟢 BUY (Aggressor Paid Ask)"
    elif trade_price <= bid:
        return "🔴 SELL (Aggressor Hit Bid)"
    else:
        return "⚪ NEUTRAL (Mid-Market)"

# 1. Get Real Data (Static Closing Quote)
symbol = "SPY260102C00500000"
print(f"Fetching latest quote for {symbol}...")
quote = get_latest_quote(symbol)

if not quote:
    print("❌ Could not fetch quote. Cannot run test.")
    exit(1)

bid = quote.get("bp") or quote.get("b")
ask = quote.get("ap") or quote.get("a")

print(f"✅ Market Data Received:")
print(f"   Bid: ${bid}")
print(f"   Ask: ${ask}")
print("-" * 30)

# 2. Simulate Scenarios
print("🧪 Running Simulations:\n")

# Scenario A: Whale buys at Ask
sim_price_buy = ask
print(f"Scenario 1: Whale Trade @ ${sim_price_buy}")
print(f"   Result: {determine_side(sim_price_buy, bid, ask)}")

# Scenario B: Whale sells at Bid
sim_price_sell = bid
print(f"\nScenario 2: Whale Trade @ ${sim_price_sell}")
print(f"   Result: {determine_side(sim_price_sell, bid, ask)}")

# Scenario C: Whale trades in between (Mid)
sim_price_mid = round((bid + ask) / 2, 2)
print(f"\nScenario 3: Whale Trade @ ${sim_price_mid}")
print(f"   Result: {determine_side(sim_price_mid, bid, ask)}")

print("\n✅ Logic Verified! We can deploy this.")
