from datetime import datetime
import pytz

def check_expiration(symbol_expiry_str):
    tz_eastern = pytz.timezone('US/Eastern')
    now_et = datetime.now(tz_eastern)
    
    print(f"Current Time (ET): {now_et}")
    print(f"Current Date (ET): {now_et.date()}")
    
    try:
        exp_date = datetime.strptime(symbol_expiry_str, "%Y-%m-%d").date()
        dte = (exp_date - now_et.date()).days
        is_valid_dte = 0 <= dte <= 30
        
        print(f"Expiry: {exp_date}")
        print(f"DTE: {dte}")
        print(f"Is Valid (0<=dte<=30): {is_valid_dte}")
        return is_valid_dte
    except Exception as e:
        print(f"Error: {e}")
        return False

# Test with Jan 2nd 2026 (Expired on Friday)
print("--- Testing Expired Symbol (Jan 2, 2026) ---")
check_expiration("2026-01-02")

# Test with Jan 9th 2026 (Valid)
print("\n--- Testing Valid Symbol (Jan 9, 2026) ---")
check_expiration("2026-01-09")
