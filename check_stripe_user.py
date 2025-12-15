import stripe
import stripe_config

stripe.api_key = stripe_config.STRIPE_SECRET_KEY

def check_user(email):
    print(f"Checking Stripe (Test Mode) for: {email}")
    try:
        customers = stripe.Customer.list(email=email, limit=1)
        if not customers.data:
            print("❌ User NOT found in Stripe Test Mode.")
            return

        customer = customers.data[0]
        print(f"✅ Found Customer: {customer.id}")
        
        subscriptions = stripe.Subscription.list(customer=customer.id, status='all')
        if not subscriptions.data:
            print("❌ No subscriptions found.")
        else:
            for sub in subscriptions.data:
                print(f"   - Sub ID: {sub.id}")
                print(f"   - Status: {sub.status}")
                print(f"   - Trial End: {sub.trial_end}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_user("sam.juarez9@outlook.com")
