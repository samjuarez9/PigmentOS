import pytz
from datetime import datetime, timedelta

def test_logic():
    tz_eastern = pytz.timezone('US/Eastern')
    now_eastern = datetime.now(tz_eastern)
    
    print(f"Current Eastern Time: {now_eastern}")
    print(f"Current Date: {now_eastern.date()}")
    
    # Simulate a trade from Yesterday at 3:59 PM ET
    yesterday = now_eastern - timedelta(days=1)
    trade_ts = yesterday.replace(hour=15, minute=59, second=0, microsecond=0)
    
    print(f"\nSimulated Trade Time (Yesterday): {trade_ts}")
    print(f"Trade Date: {trade_ts.date()}")
    
    # The Logic from run.py
    is_today = trade_ts.date() == now_eastern.date()
    
    print(f"\nIs Trade Date == Current Date? {is_today}")
    
    if is_today:
        print("❌ FAIL: Logic thinks yesterday is today.")
    else:
        print("✅ PASS: Logic correctly identifies yesterday as NOT today.")

if __name__ == "__main__":
    test_logic()
