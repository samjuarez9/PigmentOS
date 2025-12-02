from flask import Flask, send_from_directory
import os

app = Flask(__name__, static_folder='.')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

if __name__ == "__main__":
    # Create a dummy app.js if it doesn't exist
    if not os.path.exists('app.js'):
        with open('app.js', 'w') as f:
            f.write('console.log("Hello");')
            
    print(f"File size on disk: {os.path.getsize('app.js')}")
    
    with app.test_client() as client:
        response = client.get('/app.js')
        print(f"Status: {response.status_code}")
        print(f"Content-Length: {response.content_length}")
        print(f"Data length: {len(response.data)}")
