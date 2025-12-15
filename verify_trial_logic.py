from datetime import datetime, timedelta
import pytz

# Mock objects
class MockUserDocSnapshot:
    def __init__(self, data, exists=True):
        self._data = data
        self.exists = exists
    
    def to_dict(self):
        return self._data

class MockDocRef:
    def __init__(self, data, exists):
        self._data = data
        self._exists = exists
        
    def get(self):
        return MockUserDocSnapshot(self._data, self._exists)

class MockFirestore:
    def __init__(self, users):
        self.users = users
        
    def collection(self, name):
        return self
        
    def document(self, uid):
        return MockDocRef(self.users.get(uid), exists=uid in self.users)

# Logic from run.py (UPDATED)
def check_subscription(user_uid, firestore_db):
    TRIAL_DAYS = 14
    try:
        trial_start_date = None
        if firestore_db:
            try:
                user_doc = firestore_db.collection('users').document(user_uid).get()
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    trial_start_ts = user_data.get('trialStartDate')
                    subscription_status_db = user_data.get('subscriptionStatus', 'trialing')
                    
                    print(f"User Data: {user_data}")
                    
                    if subscription_status_db == 'active':
                        return {'status': 'active', 'has_access': True}
                    
                    if subscription_status_db in ['expired', 'past_due']:
                        return {'status': 'expired', 'has_access': False}
                    
                    if trial_start_ts:
                        trial_start_date = trial_start_ts
            except Exception as db_error:
                print(f"Firestore lookup error: {db_error}")
        
        if not trial_start_date:
            print("No trial start date -> New User")
            return {
                'status': 'trialing',
                'days_remaining': TRIAL_DAYS,
                'has_access': True
            }
        
        # Calculate Expiration (UPDATED LOGIC)
        try:
            if hasattr(trial_start_date, 'timestamp'):
                trial_start = datetime.fromtimestamp(trial_start_date.timestamp(), tz=pytz.UTC)
            elif isinstance(trial_start_date, str):
                try:
                    trial_start = datetime.fromisoformat(trial_start_date.replace('Z', '+00:00'))
                    if trial_start.tzinfo is None:
                        trial_start = trial_start.replace(tzinfo=pytz.UTC)
                except ValueError:
                    print(f"Invalid date string format: {trial_start_date}")
                    trial_start = datetime.now(pytz.UTC)
            elif isinstance(trial_start_date, datetime):
                trial_start = trial_start_date
                if trial_start.tzinfo is None:
                    trial_start = trial_start.replace(tzinfo=pytz.UTC)
            else:
                print(f"Unknown trial_start_date type: {type(trial_start_date)}")
                trial_start = datetime.now(pytz.UTC)
                
            trial_end = trial_start + timedelta(days=TRIAL_DAYS)
            now = datetime.now(pytz.UTC)
            days_remaining = (trial_end - now).days
            
            if days_remaining > 0:
                return {
                    'status': 'trialing',
                    'days_remaining': days_remaining,
                    'has_access': True
                }
                
        except Exception as date_error:
            print(f"Date calculation error: {date_error}")
            return {
                'status': 'trialing',
                'days_remaining': TRIAL_DAYS,
                'has_access': True
            }
        
        return {
            'status': 'expired',
            'has_access': False
        }
        
    except Exception as e:
        print(f"ERROR: {e}")
        # Fail OPEN
        return {
            'status': 'trialing',
            'days_remaining': 1,
            'has_access': True,
            'error': str(e)
        }

# Test Cases
print("--- TEST 1: New User (No Doc) ---")
db1 = MockFirestore({})
print(check_subscription("user1", db1))

print("\n--- TEST 2: User with Timestamp (Now) ---")
now = datetime.now(pytz.UTC)
db2 = MockFirestore({"user2": {"trialStartDate": now, "subscriptionStatus": "trialing"}})
print(check_subscription("user2", db2))

print("\n--- TEST 3: User with Timestamp (Old) ---")
old = now - timedelta(days=20)
db3 = MockFirestore({"user3": {"trialStartDate": old, "subscriptionStatus": "trialing"}})
print(check_subscription("user3", db3))

print("\n--- TEST 4: User with String Date (WAS ERROR, NOW SHOULD PASS) ---")
db4 = MockFirestore({"user4": {"trialStartDate": "2025-12-15T12:00:00Z", "subscriptionStatus": "trialing"}})
print(check_subscription("user4", db4))

print("\n--- TEST 5: User with None Date ---")
db5 = MockFirestore({"user5": {"trialStartDate": None, "subscriptionStatus": "trialing"}})
print(check_subscription("user5", db5))

print("\n--- TEST 6: User with Garbage Date (Should Fail Open) ---")
db6 = MockFirestore({"user6": {"trialStartDate": 12345, "subscriptionStatus": "trialing"}})
print(check_subscription("user6", db6))
