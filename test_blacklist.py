def test_blacklist():
    print("🔎 Testing Polymarket Blacklist Logic...\n")
    
    # 1. Define Blacklist (copied from run.py)
    BLACKLIST = ['nfl', 'nba', 'super bowl', 'sport', 'football', 'basketball', 'soccer', 'tennis', 'golf', 'searched', 'election', 'solana', 'microstrategy', 'mstr', 'zootopia', 'wicked', 'movie', 'film', 'box office', 'cinema', 'counterstrike']
    
    # 2. Define Test Cases
    test_cases = [
        "Will Bitcoin hit $100k?",
        "Who will win the Super Bowl?",
        "Counterstrike Major Winner",
        "CS2 Counterstrike Tournament",
        "Fed Interest Rate Decision",
        "Solana Price Prediction"
    ]
    
    # 3. Run Filter
    print(f"{'TITLE':<40} | {'STATUS':<10}")
    print("-" * 55)
    
    for title in test_cases:
        title_lower = title.lower()
        is_blocked = any(bad in title_lower for bad in BLACKLIST)
        status = "❌ BLOCKED" if is_blocked else "✅ ALLOWED"
        print(f"{title:<40} | {status}")

if __name__ == "__main__":
    test_blacklist()
