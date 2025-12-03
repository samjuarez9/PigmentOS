import run
import time

print("Checking CACHE keys...")
print(run.CACHE.keys())

if "whales" not in run.CACHE:
    print("❌ CACHE missing 'whales' key!")
else:
    print("✅ CACHE has 'whales' key.")

if "barchart" in run.CACHE:
    print("❌ CACHE still has 'barchart' key!")
else:
    print("✅ CACHE does not have 'barchart' key.")

print("\nRunning refresh_single_whale('SPY')...")
try:
    run.refresh_single_whale('SPY')
    print("✅ refresh_single_whale('SPY') completed without error.")
except Exception as e:
    print(f"❌ refresh_single_whale('SPY') FAILED: {e}")
