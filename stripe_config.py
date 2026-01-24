
import base64
import os

# Stripe Configuration for PigmentOS

# Live API Keys (Production)
STRIPE_PUBLISHABLE_KEY = "pk_live_51ScWFSGh2zQhHuerwyHWNhJC1WSoHenIky5sYcd8rPmntuLsnmypY6ob6Pj4J9oRXnQ9EhxPmyNGczqKMJFs4MUA00HBHGHhmm"
# Secret key from environment variable (set in Render)
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")

# Webhook Secret (Set in Render env vars after configuring Stripe Dashboard)
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# Firebase Admin SDK Credentials (Base64 encoded JSON)
FIREBASE_CREDENTIALS_B64 = os.environ.get("FIREBASE_CREDENTIALS_B64", "")

# Product Configuration
STRIPE_PRICE_ID = "price_1SqHVEGh2zQhHuervW1gZa30"  # $30/month (LIVE)

# Trial Configuration
TRIAL_DAYS = 0

# URLs
SUCCESS_URL = "https://pigmentos.onrender.com/dashboard?session_id={CHECKOUT_SESSION_ID}"
CANCEL_URL = "https://pigmentos.onrender.com/upgrade"
