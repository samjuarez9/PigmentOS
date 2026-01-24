import requests
import json

def check_status(email):
    url = "http://localhost:8001/api/subscription-status"
    headers = {"Content-Type": "application/json"}
    # Note: Local dev bypasses token check if firestore is not init, 
    # but we want to test the logic flow.
    # If firestore IS init (which it might be if creds are there), we need a token.
    # But let's try sending just the body first, as run.py handles the bypass.
    
    data = {"email": email}
    
    try:
        print(f"Checking status for {email}...")
        response = requests.post(url, json=data, headers=headers)
        print(f"Status Code: {response.status_code}")
        try:
            print(f"Response: {json.dumps(response.json(), indent=2)}")
        except:
            print(f"Raw Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Test with a random new email
    check_status("test_new_user_123@example.com")
