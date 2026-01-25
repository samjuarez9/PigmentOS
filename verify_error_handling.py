import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Mock environment variables
os.environ['STRIPE_SECRET_KEY'] = 'sk_test_mock'
os.environ['FIREBASE_CREDENTIALS_B64'] = '' 

# Mock gevent
sys.modules['gevent'] = MagicMock()
sys.modules['gevent.monkey'] = MagicMock()

# Create a mock stripe module that behaves like the real one for exception classes
mock_stripe = MagicMock()

# Define exception classes on the mock so they can be used in 'except' blocks
class MockStripeError(Exception): pass
class MockCardError(MockStripeError): 
    def __init__(self, message, param, code):
        self.user_message = message
class MockRateLimitError(MockStripeError): pass
class MockInvalidRequestError(MockStripeError): pass
class MockAuthenticationError(MockStripeError): pass
class MockAPIConnectionError(MockStripeError): pass

mock_stripe.error.StripeError = MockStripeError
mock_stripe.error.CardError = MockCardError
mock_stripe.error.RateLimitError = MockRateLimitError
mock_stripe.error.InvalidRequestError = MockInvalidRequestError
mock_stripe.error.AuthenticationError = MockAuthenticationError
mock_stripe.error.APIConnectionError = MockAPIConnectionError

# Patch sys.modules to inject our mock stripe
with patch.dict(sys.modules, {'stripe': mock_stripe}):
    try:
        # Prevent app.run
        with patch('flask.Flask.run'):
            from run import app
    except ImportError:
        print("Could not import run.py")
        exit(1)

class TestStripeErrorHandling(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    @patch('run.stripe.Customer.list')
    @patch('run.stripe.Customer.create')
    @patch('run.stripe.Subscription.list')
    @patch('run.stripe.Subscription.create')
    @patch('firebase_admin.auth.verify_id_token')
    def test_card_error(self, mock_verify, mock_sub_create, mock_sub_list, mock_cust_create, mock_cust_list):
        mock_verify.return_value = {'email': 'test@example.com', 'uid': 'test_uid'}
        mock_cust_list.return_value = MagicMock(data=[MagicMock(id='cus_test')])
        mock_sub_list.return_value = MagicMock(data=[])
        
        # Raise the MOCK exception class that run.py imported
        error = mock_stripe.error.CardError("Your card was declined.", "param", "code")
        mock_sub_create.side_effect = error

        response = self.app.post('/api/start-trial', 
                                 headers={'Authorization': 'Bearer test_token'})
        
        if response.status_code == 500:
             print(f"DEBUG: 500 Error: {response.json}")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Card declined", response.json['error'])
        print("✅ CardError handled correctly (400)")

    @patch('run.stripe.Customer.list')
    @patch('run.stripe.Subscription.list')
    @patch('run.stripe.Subscription.create')
    @patch('firebase_admin.auth.verify_id_token')
    def test_rate_limit_error(self, mock_verify, mock_sub_create, mock_sub_list, mock_cust_list):
        mock_verify.return_value = {'email': 'test@example.com', 'uid': 'test_uid'}
        mock_cust_list.return_value = MagicMock(data=[MagicMock(id='cus_test')])
        mock_sub_list.return_value = MagicMock(data=[])
        
        mock_sub_create.side_effect = mock_stripe.error.RateLimitError("Rate limit")

        response = self.app.post('/api/start-trial', 
                                 headers={'Authorization': 'Bearer test_token'})
        
        self.assertEqual(response.status_code, 429)
        self.assertIn("Too many requests", response.json['error'])
        print("✅ RateLimitError handled correctly (429)")

    @patch('run.stripe.Customer.list')
    @patch('run.stripe.Subscription.list')
    @patch('run.stripe.Subscription.create')
    @patch('firebase_admin.auth.verify_id_token')
    def test_auth_error(self, mock_verify, mock_sub_create, mock_sub_list, mock_cust_list):
        mock_verify.return_value = {'email': 'test@example.com', 'uid': 'test_uid'}
        mock_cust_list.return_value = MagicMock(data=[MagicMock(id='cus_test')])
        mock_sub_list.return_value = MagicMock(data=[])
        
        mock_sub_create.side_effect = mock_stripe.error.AuthenticationError("Auth failed")

        response = self.app.post('/api/start-trial', 
                                 headers={'Authorization': 'Bearer test_token'})
        
        self.assertEqual(response.status_code, 401)
        self.assertIn("configuration error", response.json['error'])
        print("✅ AuthenticationError handled correctly (401)")

if __name__ == '__main__':
    unittest.main()
