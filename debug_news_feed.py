
import sys
import os
import time
import logging

# Add current directory to path
sys.path.append(os.getcwd())

# Mock Flask app context if needed, but refresh_news_logic seems independent mostly
# However, it uses `CACHE` which is global in run.py
# We need to import run.py but avoid running the app.run()

# We can import the function directly if we are careful
from run import refresh_news_logic, CACHE

print("Starting News Feed Debug...")
try:
    refresh_news_logic()
    print("\n--- News Feed Result ---")
    print(f"News Count: {len(CACHE['news']['data'])}")
    if CACHE['news']['last_error']:
        print(f"Last Error: {CACHE['news']['last_error']}")
    
    for item in CACHE['news']['data'][:3]:
        print(f"- [{item['publisher']}] {item['title']}")
        
except Exception as e:
    print(f"Execution Failed: {e}")
