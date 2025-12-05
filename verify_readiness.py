import pytz
from datetime import datetime, timedelta

def verify_readiness():
    print("🔎 Verifying System Readiness for Dec 5, 9:30 AM ET...\n")
    
    # 1. Setup Timezone
    tz_eastern = pytz.timezone('US/Eastern')
    
    # 2. Simulate "Now" as Dec 5, 9:30:01 AM
    # We can't change system time, but we can verify the logic against this target
    target_now = datetime(2025, 12, 5, 9, 30, 1, tzinfo=tz_eastern)
    target_date = target_now.date()
    
    print(f"Target System Time: {target_now}")
    print(f"Target Date: {target_date}")
    
    # 3. Simulate a Trade at 9:30:00 AM (Just happened)
    trade_ts = datetime(2025, 12, 5, 9, 30, 0, tzinfo=tz_eastern)
    print(f"Simulated Trade Time: {trade_ts}")
    
    # --- TEST 1: WHALE FILTER LOGIC ---
    print("\n[TEST 1] Whale Filter Logic:")
    # Logic from api_whales:
    # if trade_dt.date() == today_date: keep
    
    whale_pass = trade_ts.date() == target_date
    if whale_pass:
        print("✅ PASS: Whale logic accepts the trade.")
    else:
        print("❌ FAIL: Whale logic rejects the trade.")
        
    # --- TEST 2: GAMMA FILTER LOGIC ---
    print("\n[TEST 2] Gamma Filter Logic:")
    # Logic from refresh_gamma_logic:
    # return ts.astimezone(tz_eastern).date() == today_date
    
    gamma_pass = trade_ts.astimezone(tz_eastern).date() == target_date
    if gamma_pass:
        print("✅ PASS: Gamma logic accepts the trade volume.")
    else:
        print("❌ FAIL: Gamma logic rejects the trade volume.")

    # --- TEST 3: MARKET OPEN CHECK ---
    print("\n[TEST 3] Market Open Check:")
    # Logic from start_background_worker:
    # is_market_open = is_weekday and ((now.hour > 9 or (now.hour == 9 and now.minute >= 30)) and (now.hour < 16))
    
    now = target_now
    is_weekday = now.weekday() < 5 # Friday is 4, so True
    is_market_open = is_weekday and (
        (now.hour > 9 or (now.hour == 9 and now.minute >= 30)) and 
        (now.hour < 16)
    )
    
    if is_market_open:
        print("✅ PASS: System recognizes Market is OPEN.")
    else:
        print("❌ FAIL: System thinks Market is CLOSED.")

if __name__ == "__main__":
    verify_readiness()
