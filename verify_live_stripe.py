import stripe
from stripe_config import STRIPE_SECRET_KEY, STRIPE_CONFIG

# Manually load from .env since stripe_config might cache old values if imported before env update
import os
from dotenv import load_dotenv
load_dotenv(override=True)

LIVE_KEY = os.environ.get("STRIPE_SECRET_KEY")
LIVE_PRICE_ID = STRIPE_CONFIG["live"]["price_id"]

if not LIVE_KEY or not LIVE_KEY.startswith("sk_live_"):
    print(f"❌ Error: STRIPE_SECRET_KEY is not a live key: {LIVE_KEY[:8]}...")
    exit(1)

stripe.api_key = LIVE_KEY

print(f"Checking Live Price ID: {LIVE_PRICE_ID}")

try:
    price = stripe.Price.retrieve(LIVE_PRICE_ID)
    amount = price.unit_amount / 100
    currency = price.currency.upper()
    product_id = price.product
    
    print(f"✅ Price Found: {amount} {currency}")
    print(f"Product ID: {product_id}")
    
    if amount == 15.0:
        print("✅ CONFIRMED: Live Price is exactly $15.00")
    else:
        print(f"⚠️ WARNING: Price is NOT $15.00. It is {amount} {currency}")

except Exception as e:
    print(f"❌ Error retrieving price: {e}")
