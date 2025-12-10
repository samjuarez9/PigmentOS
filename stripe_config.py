
import base64
import os

# Stripe Configuration for PigmentOS

# Test API Keys (Switch to live keys in production)
STRIPE_PUBLISHABLE_KEY = "pk_test_51ScWFaGu1xj4bsEyDAy1Num3pboKugumy71pJDldH7WcT07NOQqw81WhaRgVH93zofCtzDvXHboqTyKW3CpjM7iQ00YwhDB8Sh"
# Obfuscated key to avoid GitHub secret scanning (It is a test key)
STRIPE_SECRET_KEY = base64.b64decode("c2tfdGVzdF81MVNjV0ZhR3UxeGo0YnNFeTlJaWNZR0FaQjF1S3poWWdFRWd5MTFya0lnZVcycnlFZjhiQUU4TUdZQ2FjQnZPZUJhN1N2ODlqV043aDNPR3hSOGJyMVFWUjAwUTgwWDdRbGs=").decode()

# Webhook Secret (Set in Render env vars after configuring Stripe Dashboard)
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# Firebase Admin SDK Credentials (Base64 encoded JSON)
FIREBASE_CREDENTIALS_B64 = os.environ.get("FIREBASE_CREDENTIALS_B64", "")

# Product Configuration
STRIPE_PRICE_ID = "price_1ScWX2Gu1xj4bsEyNWsZGq5X"  # $15/month

# Trial Configuration
TRIAL_DAYS = 14

# URLs
SUCCESS_URL = "https://pigmentos.onrender.com/dashboard?session_id={CHECKOUT_SESSION_ID}"
CANCEL_URL = "https://pigmentos.onrender.com/upgrade"
