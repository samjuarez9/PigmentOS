import firebase_admin
from firebase_admin import credentials, firestore
import os
from dotenv import load_dotenv
import base64
import json
from datetime import datetime
import pytz

# Load environment variables
load_dotenv()

# Initialize Firebase Admin
FIREBASE_CREDENTIALS_B64 = os.getenv("FIREBASE_CREDENTIALS_B64")

if not FIREBASE_CREDENTIALS_B64:
    print("❌ Error: FIREBASE_CREDENTIALS_B64 not found in .env")
    exit(1)

try:
    creds_json = base64.b64decode(FIREBASE_CREDENTIALS_B64).decode('utf-8')
    creds_dict = json.loads(creds_json)
    cred = credentials.Certificate(creds_dict)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Firebase Admin SDK initialized")
except Exception as e:
    print(f"❌ Firebase Init Failed: {e}")
    exit(1)

def reset_trials():
    print("\n🔄 Starting Trial Reset Migration...")
    
    users_ref = db.collection('users')
    # Get all users (might need pagination for large datasets, but fine for now)
    docs = users_ref.stream()
    
    count = 0
    updated = 0
    skipped = 0
    
    now = datetime.now(pytz.UTC)
    
    for doc in docs:
        count += 1
        user_data = doc.to_dict()
        uid = doc.id
        email = user_data.get('email', 'Unknown')
        status = user_data.get('subscriptionStatus', 'none')
        
        # Skip active (paid) subscribers
        if status == 'active':
            print(f"⏭️  Skipping ACTIVE user: {email}")
            skipped += 1
            continue
            
        # Reset everyone else (trialing, expired, none, past_due)
        try:
            users_ref.document(uid).update({
                'trialStartDate': now,
                'subscriptionStatus': 'trialing', # Force back to trialing
                'lastUpdated': now
            })
            print(f"✅ Reset trial for: {email} ({status} -> trialing)")
            updated += 1
        except Exception as e:
            print(f"❌ Failed to update {email}: {e}")

    print(f"\n📊 Migration Complete:")
    print(f"   - Total Users Scanned: {count}")
    print(f"   - Users Reset: {updated}")
    print(f"   - Users Skipped (Active): {skipped}")

if __name__ == "__main__":
    # Confirmation
    print("⚠️  WARNING: This will reset the trial start date for ALL non-active users to NOW.")
    confirm = input("Type 'RESET' to confirm: ")
    
    if confirm == "RESET":
        reset_trials()
    else:
        print("❌ Operation cancelled.")
