import sys
import os

# Mock environment variables if needed
os.environ['PORT'] = '8001'

try:
    print("Importing app from run.py...")
    # This will start the background worker, but that's okay for a quick test
    from run import app
    
    print("Creating test client...")
    with app.test_client() as client:
        print("Requesting /app.js...")
        response = client.get('/app.js')
        
        print(f"Status Code: {response.status_code}")
        print(f"Content-Length: {response.content_length}")
        print(f"Data Length: {len(response.data)}")
        
        if response.status_code == 200 and len(response.data) > 0:
            print("✅ SUCCESS: app.js is served correctly.")
        else:
            print("❌ FAILURE: app.js could not be served.")
            
except Exception as e:
    print(f"❌ CRITICAL ERROR: {e}")
