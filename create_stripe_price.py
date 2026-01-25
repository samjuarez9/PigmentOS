import stripe
from stripe_config import STRIPE_SECRET_KEY

if not STRIPE_SECRET_KEY:
    print("Error: STRIPE_SECRET_KEY not found.")
    exit(1)

stripe.api_key = STRIPE_SECRET_KEY

try:
    print("Creating $15.00 Monthly Price...")
    price = stripe.Price.create(
        unit_amount=1500,  # $15.00
        currency="usd",
        recurring={"interval": "month"},
        product_data={"name": "PigmentOS Pro"}
    )
    print(f"✅ Success! Created Price: {price.id}")
    print(f"Amount: {price.unit_amount/100} {price.currency.upper()}")
    
except Exception as e:
    print(f"❌ Error creating price: {e}")
