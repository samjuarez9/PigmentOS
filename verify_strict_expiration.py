from datetime import datetime, timedelta
import pytz

# Mock objects to simulate Firestore
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

# The EXACT logic from run.py (copied and adapted for standalone testing)
def check_subscription_logic(user_uid, firestore_db):
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
                    
                    # Explicit status check
                    if subscription_status_db == 'active':
                        return {'status': 'active', 'has_access': True}
                    
                    if subscription_status_db in ['expired', 'past_due']:
                        return {'status': 'expired', 'has_access': False}
                    
                    if trial_start_ts:
                        trial_start_date = trial_start_ts
            except Exception as db_error:
                print(f"Firestore lookup error: {db_error}")
        
        if not trial_start_date:
            return {
                'status': 'trialing',
                'days_remaining': TRIAL_DAYS,
                'has_access': True
            }
        
        # 3. CALCULATE TRIAL EXPIRATION
        try:
            # Handle Firestore Timestamp
            if hasattr(trial_start_date, 'timestamp'):
                trial_start = datetime.fromtimestamp(trial_start_date.timestamp(), tz=pytz.UTC)
            elif isinstance(trial_start_date, str):
                # Handle string dates (ISO format)
                try:
                    trial_start = datetime.fromisoformat(trial_start_date.replace('Z', '+00:00'))
                    if trial_start.tzinfo is None:
                        trial_start = trial_start.replace(tzinfo=pytz.UTC)
                except ValueError:
                    print(f"Invalid date string format: {trial_start_date}")
                    # Fallback to now if date is invalid (Fail Open)
                    trial_start = datetime.now(pytz.UTC)
            elif isinstance(trial_start_date, datetime):
                trial_start = trial_start_date
                if trial_start.tzinfo is None:
                    trial_start = trial_start.replace(tzinfo=pytz.UTC)
            else:
                # Fallback for unknown types
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
            # Fail OPEN
            return {
                'status': 'trialing',
                'days_remaining': TRIAL_DAYS,
                'has_access': True
            }
        
        # 4. TRIAL EXPIRED (Simulating fall-through)
        return {
            'status': 'expired',
            'has_access': False
        }
        
    except Exception as e:
        print(f"Subscription status error: {e}")
        # Fail OPEN on general error
        return {
            'status': 'trialing',
            'days_remaining': 1,
            'has_access': True,
            'error': str(e)
        }

# --- RUNNING TESTS ---
print("Running Strict Expiration Tests...\n")

now = datetime.now(pytz.UTC)

# Case 1: Brand New User (Just signed up)
# Expected: Access Granted
db1 = MockFirestore({"user1": {"trialStartDate": now, "subscriptionStatus": "trialing"}})
res1 = check_subscription_logic("user1", db1)
print(f"Test 1 (New User): {'✅ PASS' if res1['has_access'] else '❌ FAIL'} -> {res1['status']}")

# Case 2: Active Trial User (7 days in)
# Expected: Access Granted
mid_trial = now - timedelta(days=7)
db2 = MockFirestore({"user2": {"trialStartDate": mid_trial, "subscriptionStatus": "trialing"}})
res2 = check_subscription_logic("user2", db2)
print(f"Test 2 (Mid Trial): {'✅ PASS' if res2['has_access'] else '❌ FAIL'} -> {res2['status']} ({res2.get('days_remaining')} days left)")

# Case 3: EXPIRED User (15 days ago)
# Expected: ACCESS DENIED
expired_date = now - timedelta(days=15)
db3 = MockFirestore({"user3": {"trialStartDate": expired_date, "subscriptionStatus": "trialing"}})
res3 = check_subscription_logic("user3", db3)
print(f"Test 3 (Expired User): {'✅ PASS' if not res3['has_access'] else '❌ FAIL'} -> {res3['status']}")

# Case 4: Explicitly 'expired' status in DB
# Expected: ACCESS DENIED
db4 = MockFirestore({"user4": {"trialStartDate": now, "subscriptionStatus": "expired"}})
res4 = check_subscription_logic("user4", db4)
print(f"Test 4 (Explicit Status 'expired'): {'✅ PASS' if not res4['has_access'] else '❌ FAIL'} -> {res4['status']}")

# Case 5: Corrupted Date (Fail Open Safety Net)
# Expected: Access Granted (to prevent accidental lockout)
db5 = MockFirestore({"user5": {"trialStartDate": "NOT_A_DATE", "subscriptionStatus": "trialing"}})
res5 = check_subscription_logic("user5", db5)
print(f"Test 5 (Corrupted Date): {'✅ PASS' if res5['has_access'] else '❌ FAIL'} -> {res5['status']} (Fail Open Active)")
