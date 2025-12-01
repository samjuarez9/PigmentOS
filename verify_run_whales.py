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
        print(f"✅ Top Trade Time: {data[0].get('tradeTime')}")
        print(f"✅ Top Trade Moneyness: {data[0].get('moneyness')}")
        print("✅ Sample Trade:")
        print(data[0])
        
        # Check sorting
        times = [d.get('timestamp', 0) for d in data[:5]]
        print(f"Top 5 Timestamps: {times}")
        is_sorted = all(times[i] >= times[i+1] for i in range(len(times)-1))
        print(f"Is Sorted by Time? {is_sorted}")
    else:
        print("❌ No trades found in cache!")

    # Simulate a second run to check history logic
    print("\n🧪 Running second scan to check history logic...")
    refresh_whales_logic()
    data2 = CACHE.get("barchart", {}).get("data", [])
    print(f"📊 Second scan contains {len(data2)} trades")
    
    # Ideally, if volumes haven't changed much, the output should be stable
    # We can't easily mock yfinance here without more complex patching,
    # but we can verify the code runs without error and history is populated.
    from run import WHALE_HISTORY
    print(f"📜 History contains {len(WHALE_HISTORY)} tracked contracts")


if __name__ == "__main__":
    verify_whales()
