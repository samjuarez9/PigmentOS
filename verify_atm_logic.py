
def test_moneyness(current_price, strike, contract_type):
    price_diff_pct = abs(current_price - strike) / current_price
    
    if price_diff_pct <= 0.005:
        return "ATM"
    
    is_call = contract_type == "CALL"
    if is_call:
        return "ITM" if current_price > strike else "OTM"
    else:
        return "ITM" if current_price < strike else "OTM"

# Test cases
test_cases = [
    # SPY at 600
    (600, 600, "CALL", "ATM"),
    (600, 602, "CALL", "ATM"), # 2/600 = 0.0033 <= 0.005
    (600, 603, "CALL", "ATM"), # 3/600 = 0.005 <= 0.005
    (600, 604, "CALL", "OTM"), # 4/600 = 0.0066 > 0.005
    (600, 597, "CALL", "ATM"), # 3/600 = 0.005 <= 0.005
    (600, 596, "CALL", "ITM"), # 4/600 = 0.0066 > 0.005
    
    # Puts
    (600, 600, "PUT", "ATM"),
    (600, 603, "PUT", "ATM"),
    (600, 604, "PUT", "ITM"),
    (600, 597, "PUT", "ATM"),
    (600, 596, "PUT", "OTM"),
]

for cp, s, ct, expected in test_cases:
    result = test_moneyness(cp, s, ct)
    print(f"Price: {cp}, Strike: {s}, Type: {ct} -> Result: {result} (Expected: {expected})")
    assert result == expected

print("\n✅ All ATM logic tests passed!")
