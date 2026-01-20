import os
import stripe
from dotenv import load_dotenv

load_dotenv()

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")

if not STRIPE_SECRET_KEY:
    print("Error: STRIPE_SECRET_KEY not found in environment.")
    exit(1)

stripe.api_key = STRIPE_SECRET_KEY

try:
    # Create the price
    price = stripe.Price.create(
        unit_amount=3000,  # $30.00
        currency="usd",
        recurring={"interval": "month"},
        product_data={"name": "PigmentOS Pro"},
    )
    print(f"SUCCESS: Created Price ID: {price.id}")
except Exception as e:
    print(f"Error creating price: {e}")
