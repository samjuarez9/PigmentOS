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

if __name__ == "__main__":
    verify_whales()
