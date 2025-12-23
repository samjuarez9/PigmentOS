"""
Debug/Test script for Trader Fear Index (TFI) composite calculation.

Tests the math for the 50/50 CNN+VIX composite.
"""

import json


def calculate_vix_score(vix_val):
    """
    VIX to score conversion.
    VIX 12 = 100 (Extreme Greed)
    VIX 17 = 50 (Neutral)
    VIX 22+ = 0 (Extreme Fear)
    """
    score = 100 - ((vix_val - 12) * 10)
    return max(0, min(100, score))


def calculate_composite(cnn_anchor, vix_score):
    """Calculate 50/50 weighted composite."""
    return (cnn_anchor * 0.5) + (vix_score * 0.5)


def get_rating(score):
    """Convert score to rating."""
    if score >= 75:
        return "Extreme Greed"
    elif score >= 55:
        return "Greed"
    elif score >= 45:
        return "Neutral"
    elif score >= 25:
        return "Fear"
    else:
        return "Extreme Fear"


def run_tests():
    """Run test cases to verify the math."""
    
    print("=" * 60)
    print("TFI COMPOSITE TEST CASES")
    print("=" * 60)
    print()
    
    test_cases = [
        # (VIX, CNN, Expected Score, Expected Rating)
        (12, 50, 75, "Extreme Greed"),   # VIX at extreme greed level
        (17, 50, 50, "Neutral"),         # VIX at neutral
        (22, 50, 25, "Fear"),            # VIX at extreme fear level
        (14, 80, 80, "Extreme Greed"),   # Low VIX + high CNN
        (20, 30, 25, "Fear"),            # High VIX + low CNN
        (12, 100, 100, "Extreme Greed"), # Both at max greed
        (22, 0, 0, "Extreme Fear"),      # Both at max fear
        (15, 60, 65, "Greed"),           # Typical greed scenario
        (19, 40, 35, "Fear"),            # Typical fear scenario
    ]

    
    all_passed = True
    
    for vix, cnn, expected_score, expected_rating in test_cases:
        vix_score = calculate_vix_score(vix)
        composite = calculate_composite(cnn, vix_score)
        rating = get_rating(composite)
        
        passed = (round(composite) == expected_score and rating == expected_rating)
        status = "✅ PASS" if passed else "❌ FAIL"
        
        if not passed:
            all_passed = False
        
        print(f"{status} | VIX={vix:4}, CNN={cnn:3} → VIX_Score={vix_score:5.1f}, Composite={composite:5.1f}, Rating={rating}")
        
        if not passed:
            print(f"         Expected: Score={expected_score}, Rating={expected_rating}")
    
    print()
    print("=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 60)
    
    return all_passed


def test_live():
    """Test with live data."""
    print()
    print("=" * 60)
    print("LIVE DATA TEST")
    print("=" * 60)
    
    try:
        from fetch_composite_tfi import get_composite_score
        result = get_composite_score()
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    run_tests()
    test_live()
