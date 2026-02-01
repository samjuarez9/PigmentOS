import os
from dotenv import load_dotenv

load_dotenv()


# Stripe Configuration for PigmentOS
# Supports 'sandbox' (Test) and 'live' (Production) modes

# Determine environment: 'sandbox' or 'live'
# Default to 'sandbox' for safety
STRIPE_ENV = os.environ.get("STRIPE_ENV", "sandbox")

# Configuration Dictionary
STRIPE_CONFIG = {
    "sandbox": {
        "secret_key": os.environ.get("STRIPE_SECRET_KEY_TEST", ""),
        "publishable_key": os.environ.get("STRIPE_PUBLISHABLE_KEY_TEST", ""),
        "price_id": "price_1StaOMGh2zQhHuerRC3JWTl4", # Created 2026-01-25: $15/month
        "webhook_secret": os.environ.get("STRIPE_WEBHOOK_SECRET_TEST", "")
    },
    "live": {
        "secret_key": os.environ.get("STRIPE_SECRET_KEY", ""),
        "publishable_key": "pk_live_51ScWFSGh2zQhHuerwyHWNhJC1WSoHenIky5sYcd8rPmntuLsnmypY6ob6Pj4J9oRXnQ9EhxPmyNGczqKMJFs4MUA00HBHGHhmm",
        "price_id": "price_1SqHVEGh2zQhHuervW1gZa30",  # $30/month
        "webhook_secret": os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    }
}

# Get current config based on environment
CURRENT_CONFIG = STRIPE_CONFIG.get(STRIPE_ENV, STRIPE_CONFIG["sandbox"])

# Export variables for easy import
STRIPE_SECRET_KEY = CURRENT_CONFIG["secret_key"]
STRIPE_PUBLISHABLE_KEY = CURRENT_CONFIG["publishable_key"]
STRIPE_PRICE_ID = CURRENT_CONFIG["price_id"]
STRIPE_WEBHOOK_SECRET = CURRENT_CONFIG["webhook_secret"]

# Common Configuration
FIREBASE_CREDENTIALS_B64 = os.environ.get("FIREBASE_CREDENTIALS_B64", "")

# URLs
SUCCESS_URL = "https://pigmentos.onrender.com/dashboard?session_id={CHECKOUT_SESSION_ID}"
CANCEL_URL = "https://pigmentos.onrender.com/upgrade"
