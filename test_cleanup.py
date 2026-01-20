import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
import base64
from dotenv import load_dotenv

load_dotenv()

from stripe_config import FIREBASE_CREDENTIALS_B64

# Initialize Firebase
if not FIREBASE_CREDENTIALS_B64:
    print("❌ FIREBASE_CREDENTIALS_B64 not found")
    exit(1)

try:
    creds_json = base64.b64decode(FIREBASE_CREDENTIALS_B64).decode('utf-8')
    creds_dict = json.loads(creds_json)
    cred = credentials.Certificate(creds_dict)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Firebase initialized")
except Exception as e:
    print(f"❌ Firebase init failed: {e}")
    exit(1)

# Inject DB into whales_service manually since we aren't running the full app
import whales_service
whales_service.FIRESTORE_DB = db

# Run Cleanup
print("🧪 Testing Cleanup Function...")
whales_service.clear_all_snapshots()
