import re

CATEGORY_KEYWORDS = {
    "GEOPOL": [
        "war", "invasion", "strike", "china", "russia", "israel", "iran", 
        "taiwan", "ukraine", "gaza", "military", "ceasefire", "regime", 
        "syria", "korea", "venezuela", "heutih"
    ],
    "MACRO": [
        "fed", "rate", "inflation", "cpi", "recession", "powell", "gold", 
        "treasury", "trump", "cabinet", "nominate", "tariff"
    ],
    "TECH": [
        "nvidia", "apple", "microsoft", "google", "tesla", "openai", "gemini", 
        "grok", "deepseek", "claude", "spacex", "starship", "robotaxi"
    ],
    "CULTURE": [
        "spotify", "youtube", "mrbeast", "swift", "beyonce", "grammy"
    ]
}

BLACKLIST_WORDS = [
    # Structural (Enforce Yes/No UI)
    "who will", "which company", "what will", "price on", "how many", 
    "highest", "lowest", "above/below",
    
    # Sports/Entertainment Noise
    "nfl", "nba", "super bowl", "sport", "football", "basketball", 
    "soccer", "tennis", "golf", "box office", "cinema", "rotten tomatoes",
    
    # Crypto/Asset Noise
    "solana", "memecoin", "pepe", "doge", 
    
    # General
    "searched", "daily", "weekly"
]

def test_filter(title):
    title_lower = title.lower()
    
    # 1. Blacklist Check
    if any(bad in title_lower for bad in BLACKLIST_WORDS):
        return False, "Blacklisted"
    
    # 2. Filter out markets with specific times of day
    time_pattern = r'\b\d{1,2}(:\d{2})?\s*(AM|PM|am|pm)\s*(ET|EST|PST|CST)?\b'
    if re.search(time_pattern, title):
        return False, "Time-of-day"
    
    # 3. Determine Category
    category = "OTHER"
    for cat, keys in CATEGORY_KEYWORDS.items():
        if any(re.search(r'\b' + re.escape(k) + r'\b', title_lower) for k in keys):
            category = cat
            break
    
    if category == "OTHER":
        return False, "No matching category"
    
    return True, category

test_cases = [
    ("Will there be a ceasefire in Gaza by 2025?", True, "GEOPOL"),
    ("Will the Fed cut rates in March?", True, "MACRO"),
    ("Will Nvidia hit $200?", True, "TECH"),
    ("Will MrBeast reach 400M subscribers?", True, "CULTURE"),
    ("Who will win the Super Bowl?", False, "Blacklisted"),
    ("What will be the price of Solana in 2025?", False, "Blacklisted"),
    ("Highest temperature in December?", False, "Blacklisted"),
    ("Will Apple release a new iPhone?", True, "TECH"),
    ("NFL Sunday Night Football: Eagles vs Cowboys", False, "Blacklisted"),
    ("Will there be a strike in Israel?", True, "GEOPOL"),
    ("Will Trump nominate a new cabinet member?", True, "MACRO"),
    ("Will SpaceX launch Starship in February?", True, "TECH"),
    ("Will Spotify increase prices?", True, "CULTURE"),
    ("How many people will watch the Grammys?", False, "Blacklisted"),
    ("Will there be a war between China and Taiwan?", True, "GEOPOL"),
    ("Will the CPI be above 3%?", True, "MACRO"),
    ("Will OpenAI release GPT-5?", True, "TECH"),
    ("Will Beyonce win a Grammy?", True, "CULTURE"),
    ("Will Doge hit $1?", False, "Blacklisted"),
    ("Daily volume of Bitcoin?", False, "Blacklisted"),
]

print(f"{'Title':<60} | {'Expected':<10} | {'Result':<10} | {'Status'}")
print("-" * 100)
for title, expected_pass, expected_cat in test_cases:
    passed, reason = test_filter(title)
    status = "✅" if passed == expected_pass else "❌"
    print(f"{title[:60]:<60} | {str(expected_pass):<10} | {str(passed):<10} | {status} ({reason})")
