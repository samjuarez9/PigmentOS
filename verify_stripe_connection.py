import stripe
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get the key
stripe_key = os.getenv("STRIPE_SECRET_KEY")

if not stripe_key:
    print("❌ Error: STRIPE_SECRET_KEY not found in .env")
    exit(1)

print(f"🔑 Found Stripe Key: {stripe_key[:8]}...{stripe_key[-4:]}")

stripe.api_key = stripe_key

try:
    # Try to fetch account balance (standard check for valid secret key)
    # Note: This works for both test and live keys usually, but live keys might have permissions.
    # Alternatively, list products which is a safe read operation.
    print("📡 Attempting to connect to Stripe API...")
    products = stripe.Product.list(limit=1)
    print("✅ Connection Successful!")
    print(f"📦 Found {len(products.data)} products.")
    if products.data:
        print(f"   - First Product: {products.data[0].name} ({products.data[0].id})")
    
    # Also check if we can retrieve the specific price ID used in config
    from stripe_config import STRIPE_PRICE_ID
    print(f"\n🔍 Checking Configured Price ID: {STRIPE_PRICE_ID}")
    try:
        price = stripe.Price.retrieve(STRIPE_PRICE_ID)
        print(f"✅ Price ID is valid: {price.unit_amount/100} {price.currency.upper()}")
    except Exception as e:
        print(f"⚠️ Warning: Configured Price ID not found or accessible: {e}")

except stripe.error.AuthenticationError:
    print("❌ Authentication Failed: The API key is invalid.")
except Exception as e:
    print(f"❌ Error: {e}")
