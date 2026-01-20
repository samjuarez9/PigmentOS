import os
import stripe

# Manually parse .env to avoid dependency issues
env_vars = {}
try:
    with open(".env", "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip().strip('"').strip("'")
except Exception as e:
    print(f"Error reading .env: {e}")

STRIPE_SECRET_KEY = env_vars.get("STRIPE_SECRET_KEY")

if not STRIPE_SECRET_KEY:
    print("Error: STRIPE_SECRET_KEY not found in .env file.")
    exit(1)

stripe.api_key = STRIPE_SECRET_KEY

try:
    print(f"Attempting to create price with key ending in ...{STRIPE_SECRET_KEY[-4:]}")
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
