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
    TRIAL_DAYS = 5
    try:
        user_data = {}
        if firestore_db:
            try:
                user_doc = firestore_db.collection('users').document(user_uid).get()
                if user_doc.exists:
                    user_data = user_doc.to_dict()
            except Exception as db_error:
                print(f"Firestore lookup error: {db_error}")
                return {'error': 'Database error'}
        
        if not user_data:
             return {
                'status': 'none',
                'has_access': False,
                'reason': 'no_account'
            }

        sub_status = user_data.get('subscriptionStatus', 'none')
        
        # STRICT TRIAL CHECK
        if sub_status == 'trialing':
            trial_start = user_data.get('trialStartDate')
            if trial_start:
                # Handle Firestore Timestamp or ISO string
                if hasattr(trial_start, 'timestamp'):
                    start_ts = trial_start.timestamp()
                else:
                    try:
                        # Try parsing ISO string
                        dt = datetime.fromisoformat(str(trial_start).replace('Z', '+00:00'))
                        start_ts = dt.timestamp()
                    except:
                        import time
                        start_ts = time.time() # Fallback
                
                # Calculate days elapsed
                import time
                now_ts = time.time()
                days_elapsed = (now_ts - start_ts) / (86400)
                
                if days_elapsed > (TRIAL_DAYS + 0.5):
                    return {
                        'status': 'expired',
                        'has_access': False,
                        'reason': 'trial_expired_strict'
                    }

        # Simple Access Logic
        if sub_status in ['active', 'trialing']:
            return {
                'status': sub_status,
                'has_access': True,
                'is_premium': (sub_status == 'active')
            }
        else:
            return {
                'status': sub_status,
                'has_access': False,
                'reason': f"subscription_{sub_status}"
            }
            
    except Exception as e:
        print(f"ERROR: {e}")
        return {'error': str(e)}

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
