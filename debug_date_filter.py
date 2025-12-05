import pytz
from datetime import datetime

def debug_filter():
    # 1. Setup Timezone
    tz_eastern = pytz.timezone('US/Eastern')
    
    # 2. Get "Now"
    now = datetime.now(tz_eastern)
    today_date = now.date()
    
    print(f"Current System Time (Eastern): {now}")
    print(f"Target 'Today' Date: {today_date}")
    
    # 3. Test the Stale Timestamp from the Curl Output
    # Timestamp: 1764880323.0 (from the JSON response)
    stale_ts = 1764880323.0
    
    # 4. Convert to Date
    trade_dt = datetime.fromtimestamp(stale_ts, tz_eastern)
    trade_date = trade_dt.date()
    
    print(f"\nStale Timestamp: {stale_ts}")
    print(f"Converted Trade Time (Eastern): {trade_dt}")
    print(f"Converted Trade Date: {trade_date}")
    
    # 5. The Comparison
    is_match = (trade_date == today_date)
    
    print(f"\nMatch Result: {is_match}")
    
    if is_match:
        print("❌ ERROR: The filter thinks this stale trade is from today!")
    else:
        print("✅ SUCCESS: The filter correctly rejects this trade.")

if __name__ == "__main__":
    debug_filter()
