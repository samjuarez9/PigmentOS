#!/usr/bin/env python3
"""
Test script to verify Polygon WebSocket is receiving raw options trades for TSLA.
No filters applied - just print whatever comes through.
"""
import os
from dotenv import load_dotenv
load_dotenv()

from polygon import WebSocketClient
from polygon.websocket import Feed, Market

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

trade_count = 0

def handle_msg(msgs):
    global trade_count
    for msg in msgs:
        trade_count += 1
        # Print first 20 trades with all their attributes
        if trade_count <= 20:
            print(f"\n{'='*60}")
            print(f"Trade #{trade_count}")
            print(f"Type: {type(msg).__name__}")
            
            # Print all attributes
            for attr in dir(msg):
                if not attr.startswith('_'):
                    try:
                        val = getattr(msg, attr)
                        if not callable(val):
                            print(f"  {attr}: {val}")
                    except:
                        pass
        
        elif trade_count % 50 == 0:
            print(f"[{trade_count} trades received so far...]")

if __name__ == "__main__":
    print(f"🔑 API Key: {POLYGON_API_KEY[:10]}..." if POLYGON_API_KEY else "❌ No API key!")
    print("🚀 Connecting to Polygon delayed options feed...")
    print("📡 Subscribing to T.O:TSLA* (all TSLA options trades)")
    print("⏳ Waiting for trades (15-min delayed)...\n")
    
    client = WebSocketClient(
        api_key=POLYGON_API_KEY,
        feed=Feed.Delayed,
        market=Market.Options,
        subscriptions=["T.O:TSLA*"],
        verbose=True
    )
    
    try:
        client.run(handle_msg)
    except KeyboardInterrupt:
        print(f"\n\n📊 Total trades received: {trade_count}")
