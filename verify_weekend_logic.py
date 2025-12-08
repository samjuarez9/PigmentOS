import pytz
from datetime import datetime, timedelta

tz_eastern = pytz.timezone('US/Eastern')
today_date = datetime.now(tz_eastern).date()

print(f"Today (Eastern): {today_date}")
print(f"Weekday: {today_date.weekday()} (0=Mon, 6=Sun)")

# Simulate a trade from Friday
friday = today_date - timedelta(days=(today_date.weekday() - 4) if today_date.weekday() >= 5 else 1)
# If today is Sat (5), delta is 1. Friday is today-1.
# If today is Sun (6), delta is 2. Friday is today-2.

if today_date.weekday() == 5: # Sat
    last_friday = today_date - timedelta(days=1)
elif today_date.weekday() == 6: # Sun
    last_friday = today_date - timedelta(days=2)
else:
    last_friday = today_date # Just for testing

print(f"Last Friday: {last_friday}")

def is_today(trade_date_str):
    # Simulate the check in run.py
    # trade_date_str is just a date object for this test
    return trade_date_str == today_date

print(f"Is Friday trade 'today'? {is_today(last_friday)}")
