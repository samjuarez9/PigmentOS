import os
import sys
import time
from dotenv import load_dotenv

# Add current directory to path
sys.path.append(os.getcwd())

# Load environment variables
load_dotenv()

try:
    from run import get_finnhub_price, get_cached_price, FINNHUB_API_KEY
    print("Successfully imported functions")
except ImportError as e:
    print(f"Failed to import: {e}")
    sys.exit(1)

if not FINNHUB_API_KEY:
    print("⚠️ FINNHUB_API_KEY not set!")

symbol = "SPY"
print(f"Fetching prices for {symbol}...")

# Fetch from Finnhub (Gamma Wall source)
start = time.time()
finnhub_price = get_finnhub_price(symbol)
finnhub_time = time.time() - start
print(f"Finnhub Price: {finnhub_price} (took {finnhub_time:.2f}s)")

# Fetch from YFinance (General source)
start = time.time()
yfinance_price = get_cached_price(symbol)
yfinance_time = time.time() - start
print(f"YFinance Price: {yfinance_price} (took {yfinance_time:.2f}s)")

if finnhub_price and yfinance_price:
    diff = abs(finnhub_price - yfinance_price)
    print(f"Difference: {diff:.2f}")
    if diff > 1.0:
        print("⚠️ Significant discrepancy found!")
    else:
        print("✅ Prices are consistent.")
else:
    print("❌ Could not compare prices.")
