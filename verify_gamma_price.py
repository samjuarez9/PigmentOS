import os
import sys
import time
from dotenv import load_dotenv

# Add current directory to path so we can import run.py
sys.path.append(os.getcwd())

# Load environment variables
load_dotenv()

# Mock Flask and other dependencies if needed, or just import the function
# Since run.py has a lot of global state and imports, it might be safer to just extract the function or try to import it.
# run.py starts a background worker on import, which might be annoying.
# But we can check if we can import just the function.

try:
    from run import get_cached_price, PRICE_CACHE
    print("Successfully imported get_cached_price")
except ImportError as e:
    print(f"Failed to import: {e}")
    sys.exit(1)

# Test with a known ticker
symbol = "SPY"
print(f"Fetching price for {symbol}...")

price = get_cached_price(symbol)

if price:
    print(f"✅ Success! Price for {symbol}: {price}")
    print(f"Cache entry: {PRICE_CACHE.get(symbol)}")
else:
    print(f"❌ Failed to fetch price for {symbol}")

# Test with a ticker that might be pre-market active or have specific behavior if possible
# But SPY is good enough.

