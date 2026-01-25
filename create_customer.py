import stripe
from stripe_config import STRIPE_SECRET_KEY, STRIPE_ENV

if not STRIPE_SECRET_KEY:
    print("Error: STRIPE_SECRET_KEY not found.")
    exit(1)

stripe.api_key = STRIPE_SECRET_KEY

print(f"⚠️  Running in {STRIPE_ENV.upper()} mode")

try:
    customer = stripe.Customer.create(
        email="jane.smith@email.com",
        name="Jane Smith",
        description="My First Stripe Customer"
    )
    print(f"✅ Success! Created Customer: {customer.name} ({customer.email})")
    print(f"🆔 Customer ID: {customer.id}")
except Exception as e:
    print(f"❌ Error creating customer: {e}")
