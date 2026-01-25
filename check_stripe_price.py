import stripe
from stripe_config import STRIPE_SECRET_KEY, STRIPE_PRICE_ID, STRIPE_ENV

if not STRIPE_SECRET_KEY:
    print("Error: STRIPE_SECRET_KEY not found.")
    exit(1)

stripe.api_key = STRIPE_SECRET_KEY

print(f"Checking Price ID: {STRIPE_PRICE_ID} (Env: {STRIPE_ENV})")

try:
    price = stripe.Price.retrieve(STRIPE_PRICE_ID)
    amount = price.unit_amount / 100
    currency = price.currency.upper()
    product_id = price.product
    
    print(f"✅ Price Found: {amount} {currency}")
    print(f"Product ID: {product_id}")
    
    if amount == 15.0:
        print("✅ CONFIRMED: Price is exactly $15.00")
    else:
        print(f"⚠️ WARNING: Price is NOT $15.00. It is {amount} {currency}")

except Exception as e:
    print(f"❌ Error retrieving price: {e}")
