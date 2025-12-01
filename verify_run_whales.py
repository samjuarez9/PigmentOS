import time
from run import refresh_whales_logic, CACHE

def verify_whales():
    print("🧪 Verifying Yahoo Finance Whale Scanner...", flush=True)
    
    # Run the logic
    start_time = time.time()
    refresh_whales_logic()
    end_time = time.time()
    
    print(f"⏱️ Scan took {end_time - start_time:.2f} seconds")
    
    # Check Cache
    data = CACHE.get("barchart", {}).get("data", [])
    print(f"📊 Cache contains {len(data)} trades")
    
    if data:
        print("✅ Sample Trade:")
        print(data[0])
    else:
        print("❌ No trades found in cache!")

if __name__ == "__main__":
    verify_whales()
