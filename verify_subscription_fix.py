import unittest
from datetime import datetime, timedelta
import time
import pytz

# Mock objects to simulate Firestore and User Data
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

# --- LOGIC TO TEST (Copy of intended logic for run.py) ---
def check_subscription_logic(user_data, trial_days=5):
    """
    Refactored logic that will go into run.py
    """
    if not user_data:
         return {
            'status': 'none',
            'has_access': False,
            'reason': 'no_account'
        }

    sub_status = user_data.get('subscriptionStatus', 'none')
    
    # 1. STRICT TRIAL CHECK
    if sub_status == 'trialing':
        trial_start = user_data.get('trialStartDate')
        
        # SECURITY FIX: If no trial start date, DENY access (assume expired/invalid)
        if not trial_start:
            return {
                'status': 'expired',
                'has_access': False,
                'reason': 'trial_date_missing'
            }

        # Parse Date
        start_ts = 0
        if hasattr(trial_start, 'timestamp'):
            start_ts = trial_start.timestamp()
        else:
            try:
                # Try parsing ISO string
                dt = datetime.fromisoformat(str(trial_start).replace('Z', '+00:00'))
                start_ts = dt.timestamp()
            except:
                # Invalid date format -> Deny Access
                return {
                    'status': 'expired',
                    'has_access': False,
                    'reason': 'trial_date_invalid'
                }
        
        # Calculate days elapsed
        now_ts = time.time()
        days_elapsed = (now_ts - start_ts) / (86400)
        
        if days_elapsed > (trial_days + 0.5):
            return {
                'status': 'expired',
                'has_access': False,
                'reason': 'trial_expired_strict'
            }
        
        # Valid Trial
        return {
            'status': 'trialing',
            'has_access': True,
            'is_premium': False,
            'days_left': max(0, trial_days - days_elapsed)
        }

    # 2. ACTIVE SUBSCRIPTION
    if sub_status == 'active':
        return {
            'status': 'active',
            'has_access': True,
            'is_premium': True
        }

    # 3. EXPLICIT DENY FOR OTHER STATUSES
    return {
        'status': sub_status,
        'has_access': False,
        'reason': f"subscription_{sub_status}"
    }

# --- TEST SUITE ---
class TestSubscriptionLogic(unittest.TestCase):
    
    def setUp(self):
        self.now = datetime.now(pytz.UTC)
    
    def test_active_user(self):
        user = {'subscriptionStatus': 'active'}
        result = check_subscription_logic(user)
        self.assertTrue(result['has_access'])
        self.assertEqual(result['status'], 'active')

    def test_valid_trial(self):
        # Trial started 1 day ago
        start = self.now - timedelta(days=1)
        user = {'subscriptionStatus': 'trialing', 'trialStartDate': start}
        result = check_subscription_logic(user)
        self.assertTrue(result['has_access'])
        self.assertEqual(result['status'], 'trialing')

    def test_expired_trial(self):
        # Trial started 10 days ago
        start = self.now - timedelta(days=10)
        user = {'subscriptionStatus': 'trialing', 'trialStartDate': start}
        result = check_subscription_logic(user)
        self.assertFalse(result['has_access'])
        self.assertEqual(result['reason'], 'trial_expired_strict')

    def test_missing_trial_date(self):
        # SECURITY FIX TEST
        user = {'subscriptionStatus': 'trialing'} # No date
        result = check_subscription_logic(user)
        self.assertFalse(result['has_access'])
        self.assertEqual(result['reason'], 'trial_date_missing')

    def test_past_due(self):
        user = {'subscriptionStatus': 'past_due'}
        result = check_subscription_logic(user)
        self.assertFalse(result['has_access'])
        self.assertEqual(result['reason'], 'subscription_past_due')

    def test_incomplete(self):
        user = {'subscriptionStatus': 'incomplete'}
        result = check_subscription_logic(user)
        self.assertFalse(result['has_access'])

    def test_canceled(self):
        user = {'subscriptionStatus': 'canceled'}
        result = check_subscription_logic(user)
        self.assertFalse(result['has_access'])

if __name__ == '__main__':
    unittest.main()
