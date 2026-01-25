
import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
import base64
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Initialize Firebase
FIREBASE_CREDENTIALS_B64 = os.environ.get("FIREBASE_CREDENTIALS_B64")

if not FIREBASE_CREDENTIALS_B64:
    # Try to load from stripe_config if not in env directly (though run.py loads from env)
    try:
        import stripe_config
        FIREBASE_CREDENTIALS_B64 = stripe_config.FIREBASE_CREDENTIALS_B64
    except ImportError:
        pass

if not FIREBASE_CREDENTIALS_B64:
    print("❌ Error: FIREBASE_CREDENTIALS_B64 not found.")
    exit(1)

try:
    creds_json = base64.b64decode(FIREBASE_CREDENTIALS_B64).decode('utf-8')
    creds_dict = json.loads(creds_json)
    cred = credentials.Certificate(creds_dict)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Firebase initialized.")
except Exception as e:
    print(f"❌ Firebase initialization failed: {e}")
    exit(1)

def grant_access(email, days=10):
    print(f"🔍 Searching for user: {email}")
    users_ref = db.collection('users')
    query = users_ref.where('email', '==', email).limit(1)
    docs = query.stream()
    
    user_doc = None
    for doc in docs:
        user_doc = doc
        break
    
    if not user_doc:
        print(f"❌ User not found: {email}")
        return

    print(f"✅ Found user: {user_doc.id}")
    
    # Calculate trialStartDate
    # Logic: days_remaining = TRIAL_DAYS - elapsed_days
    # elapsed_days = (now - start)
    # We want days_remaining = 10
    # 10 = 3 - (now - start)
    # (now - start) = 3 - 10 = -7
    # start = now + 7 days
    
    # Wait, let's double check TRIAL_DAYS. It is 3 in stripe_config.py.
    # So start = now + 7 days.
    
    # However, if I want exactly 10 days from NOW, I should set start such that:
    # TRIAL_DAYS - (now - start) = 10
    # 3 - (now - start) = 10
    # now - start = -7
    # start = now + 7
    
    # Let's verify:
    # If start = now + 7
    # elapsed = now - (now + 7) = -7
    # remaining = 3 - (-7) = 10. Correct.
    
    # But wait, if TRIAL_DAYS changes, this breaks.
    # Assuming TRIAL_DAYS = 3.
    
    # To be safe, let's read TRIAL_DAYS from config if possible, or assume 3.
    TRIAL_DAYS = 3
    try:
        import stripe_config
        TRIAL_DAYS = stripe_config.TRIAL_DAYS
    except:
        pass
        
    target_remaining = days
    # target = TRIAL_DAYS - elapsed
    # elapsed = TRIAL_DAYS - target
    # now - start = TRIAL_DAYS - target
    # start = now - (TRIAL_DAYS - target)
    # start = now - TRIAL_DAYS + target
    
    future_start_date = datetime.now() - timedelta(days=TRIAL_DAYS) + timedelta(days=target_remaining)
    
    print(f"Calculated future start date: {future_start_date}")
    
    try:
        user_doc.reference.update({
            'trialStartDate': future_start_date,
            'subscriptionStatus': 'trialing',
            'subscriptionUpdatedAt': firestore.SERVER_TIMESTAMP
        })
        print(f"✅ Successfully granted {days} days access to {email}")
        print(f"   Set trialStartDate to: {future_start_date}")
        print(f"   Set subscriptionStatus to: trialing")
        
    except Exception as e:
        print(f"❌ Failed to update user: {e}")

if __name__ == "__main__":
    grant_access("saulr165@gmail.com", days=10)
