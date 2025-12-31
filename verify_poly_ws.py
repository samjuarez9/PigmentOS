import os
import websocket
import json
import time
import threading
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('POLYGON_API_KEY')
WS_URL = "wss://socket.polygon.io/options"

def on_message(ws, message):
    print(f"Received: {message}")
    # If we get a success message for subscription, we know we have access
    data = json.loads(message)
    for item in data:
        if item.get('ev') == 'status':
            print(f"Status: {item.get('message')}")
            if item.get('status') == 'auth_success':
                print("✅ Authentication Successful!")
                # Try subscribing to Trades (T) and Quotes (Q) for a test ticker
                sub_msg = {"action": "subscribe", "params": "T.O:SPY251219C00650000,Q.O:SPY251219C00650000"}
                ws.send(json.dumps(sub_msg))
                print(f"Sent subscription: {sub_msg}")
            if item.get('status') == 'success':
                print(f"✅ Subscription Successful: {item.get('message')}")
                ws.close() # We're good, close it

def on_error(ws, error):
    print(f"Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("### Closed ###")

def on_open(ws):
    print("Opened connection")
    auth_msg = {"action": "auth", "params": API_KEY}
    ws.send(json.dumps(auth_msg))
    print("Sent auth...")

if __name__ == "__main__":
    # Enable trace to see full communication
    # websocket.enableTrace(True)
    ws = websocket.WebSocketApp(WS_URL,
                              on_open=on_open,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close)

    # Run for max 5 seconds
    wst = threading.Thread(target=ws.run_forever, kwargs={"sslopt": {"cert_reqs": 0}})
    wst.daemon = True
    wst.start()
    
    time.sleep(5)
    ws.close()
