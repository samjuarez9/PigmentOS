import requests
import json
import time

BASE_URL = "http://localhost:8001"

def test_start_trial():
    print("\n--- Testing /api/start-trial (Dev Bypass) ---")
    # Use a unique email to avoid "Customer already exists" if possible, or just test idempotency
    email = f"test_user_{int(time.time())}@example.com"
    
    payload = {"email": email}
    # No Authorization header -> Triggers Dev Bypass if firestore_db is None
    # OR we can send a dummy header if the bypass requires it.
    # Looking at run.py: 
    # if not firestore_db: bypass
    # else: check header
    # Since we are running locally and likely firestore_db IS None (unless creds are set), 
    # we can just send the body.
    
    try:
        response = requests.post(f"{BASE_URL}/api/start-trial", json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            return email
        else:
            print("Failed to start trial.")
            return None
    except Exception as e:
        print(f"Request Error: {e}")
        return None

def test_subscription_status(email):
    print(f"\n--- Testing /api/subscription-status for {email} ---")
    # Again, relying on Dev Bypass
    payload = {"email": email}
    
    try:
        response = requests.post(f"{BASE_URL}/api/subscription-status", json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        data = response.json()
        if data.get('has_access') is True:
            print("✅ Access Granted")
        else:
            print("❌ Access Denied")
            
    except Exception as e:
        print(f"Request Error: {e}")

if __name__ == "__main__":
    # Wait a bit for server to fully start if we just ran start.sh
    time.sleep(2)
    
    user_email = test_start_trial()
    if user_email:
        test_subscription_status(user_email)
