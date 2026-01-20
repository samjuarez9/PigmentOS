import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8001/api"

def verify_firestore_persistence():
    print("\n--- Verifying Firestore Persistence ---")
    
    # 1. Check if History Endpoint works (should return empty or existing)
    try:
        print("1. Fetching History...")
        resp = requests.get(f"{BASE_URL}/whales-history")
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            print(f"✅ History Endpoint Reachable. Items: {len(data)}")
        else:
            print(f"❌ History Endpoint Failed: {resp.status_code}")
            return
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return

    # 2. Check if Main Feed merges data
    try:
        print("2. Fetching Main Feed (Lotto Mode)...")
        resp = requests.get(f"{BASE_URL}/whales?lotto=true&limit=10")
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            print(f"✅ Main Feed Reachable. Items: {len(data)}")
            if data:
                print(f"Sample Item: {data[0].get('ticker')} | Source: {data[0].get('source', 'Unknown')}")
        else:
            print(f"❌ Main Feed Failed: {resp.status_code}")
    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    verify_firestore_persistence()
