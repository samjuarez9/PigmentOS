import stripe
from stripe_config import STRIPE_SECRET_KEY

if not STRIPE_SECRET_KEY:
    print("Error: STRIPE_SECRET_KEY not found.")
    exit(1)

stripe.api_key = STRIPE_SECRET_KEY
PRODUCT_ID = "prod_TaiPG2QjSy9lwe"

try:
    print(f"Searching for prices for Product: {PRODUCT_ID}...")
    prices = stripe.Price.list(product=PRODUCT_ID, active=True)
    
    found = False
    for p in prices.data:
        amount = p.unit_amount / 100
        currency = p.currency.upper()
        interval = p.recurring.interval if p.recurring else "one-time"
        print(f"Found Price: {p.id} | {amount} {currency} / {interval}")
        
        if amount == 15.0 and interval == 'month':
            print(f"✅ MATCH FOUND: {p.id}")
            found = True

    if not found:
        print("❌ No active $15/month price found for this product.")

except Exception as e:
    print(f"❌ Error listing prices: {e}")
