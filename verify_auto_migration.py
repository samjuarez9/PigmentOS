import requests
import time

BASE_URL = "http://localhost:8001"

def test_auto_migration():
    print("\n--- Testing Auto-Migration ---")
    # Use a unique email that definitely doesn't exist in Stripe Test Mode
    email = f"migration_test_{int(time.time())}@example.com"
    
    print(f"Testing with new email: {email}")
    
    # We call subscription-status directly. 
    # Since this user has no Stripe record, the server should:
    # 1. Check Stripe -> Find nothing.
    # 2. Auto-create Customer & Subscription.
    # 3. Return 'trialing'.
    
    payload = {"email": email}
    
    try:
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/api/subscription-status", json=payload)
        duration = time.time() - start_time
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        print(f"Time taken: {duration:.2f}s")
        
        data = response.json()
        if data.get('status') == 'trialing' and data.get('has_access') is True:
            print("✅ Auto-Migration Successful")
        else:
            print("❌ Auto-Migration Failed")
            
    except Exception as e:
        print(f"Request Error: {e}")

if __name__ == "__main__":
    test_auto_migration()
