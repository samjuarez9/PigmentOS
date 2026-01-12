"""
Trader Fear Index (TFI) - Composite Score Calculator

50/50 weighted composite of:
1. CNN Anchor (50%): CNN Fear & Greed Index, cached at 9:30 AM EST as daily anchor
2. VIX Pulse (50%): Intraday VIX on linear scale (12→100, 17→50, 22→0)

Output: JSON with final_score, rating, cnn_anchor, vix_score, vix_value, mode
"""

import json
import sys
from datetime import datetime, time as dt_time
import pytz
import yfinance as yf
import fear_and_greed

# === GLOBAL CACHE ===
# CNN Anchor: Fetched once at 9:30 AM EST, cached for the trading day
_cnn_anchor_cache = {
    "value": None,
    "date": None  # Date string (YYYY-MM-DD) when anchor was set
}


def get_current_et_time():
    """Get current time in Eastern Time."""
    et = pytz.timezone("America/New_York")
    return datetime.now(et)


def should_refresh_cnn_anchor():
    """
    Determine if we need to fetch a new CNN anchor.
    Refresh if:
    1. No cached value exists
    2. It's a new trading day (after 9:30 AM ET)
    """
    if _cnn_anchor_cache["value"] is None:
        return True
    
    now_et = get_current_et_time()
    today_str = now_et.strftime("%Y-%m-%d")
    
    # If cache is from a different day, refresh
    if _cnn_anchor_cache["date"] != today_str:
        return True
    
    return False


def get_cnn_anchor():
    """
    Fetch CNN Fear & Greed Index as daily anchor.
    Cached at 9:30 AM EST, reused for the entire trading day.
    """
    import concurrent.futures
    global _cnn_anchor_cache
    
    if should_refresh_cnn_anchor():
        def fetch_cnn():
            result = fear_and_greed.get()
            return result.value
        
        try:
            # Timeout after 2 seconds to prevent hangs
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(fetch_cnn)
                cnn_value = future.result(timeout=2)
            
            now_et = get_current_et_time()
            _cnn_anchor_cache = {
                "value": cnn_value,
                "date": now_et.strftime("%Y-%m-%d")
            }
            
            return cnn_value
        except concurrent.futures.TimeoutError:
            # If timeout and we have a cached value, use it
            if _cnn_anchor_cache["value"] is not None:
                return _cnn_anchor_cache["value"]
            return 50.0
        except Exception as e:
            # If fetch fails and we have a cached value, use it
            if _cnn_anchor_cache["value"] is not None:
                return _cnn_anchor_cache["value"]
            # Otherwise return neutral
            return 50.0
    
    return _cnn_anchor_cache["value"]


def get_vix_pulse():
    """
    Fetch intraday VIX and convert to score.
    Linear scale:
    - VIX 12 = 100 (Extreme Greed)
    - VIX 17 = 50 (Neutral)
    - VIX 22+ = 0 (Extreme Fear)
    
    Formula: vix_score = max(0, min(100, 100 - ((vix_val - 12) * 10)))
    """
    import concurrent.futures
    
    def fetch_vix():
        vix = yf.Ticker("^VIX")
        try:
            return vix.fast_info['last_price']
        except:
            return vix.history(period="1d")['Close'].iloc[-1]
    
    try:
        # Timeout after 2 seconds to prevent hangs
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(fetch_vix)
            vix_val = future.result(timeout=2)
        
        # Apply linear scale
        vix_score = 100 - ((vix_val - 12) * 10)
        vix_score = max(0, min(100, vix_score))
        
        return vix_val, vix_score
    except concurrent.futures.TimeoutError:
        # Return neutral if timeout
        return 17.0, 50.0
    except Exception as e:
        # Fallback to neutral if VIX fetch fails
        return 17.0, 50.0


def get_rating(score):
    """Convert numeric score to text rating."""
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


def get_composite_score():
    """
    Calculate the composite TFI score.
    
    Returns JSON:
    {
        "score": 62,
        "rating": "Greed",
        "cnn_anchor": 74,
        "vix_score": 50,
        "vix_value": 17.0,
        "mode": "COMPOSITE"
    }
    """
    response = {
        "score": 50,
        "rating": "Neutral",
        "cnn_anchor": 50,
        "vix_score": 50,
        "vix_value": 17.0,
        "mode": "COMPOSITE"
    }
    
    try:
        # 1. Get CNN Anchor (50%)
        cnn_anchor = get_cnn_anchor()
        
        # 2. Get VIX Pulse (50%)
        vix_value, vix_score = get_vix_pulse()
        
        # 3. Calculate Composite
        final_score = (cnn_anchor * 0.5) + (vix_score * 0.5)
        
        response["score"] = round(final_score)
        response["rating"] = get_rating(final_score)
        response["cnn_anchor"] = round(cnn_anchor, 1)
        response["vix_score"] = round(vix_score, 1)
        response["vix_value"] = round(vix_value, 2)
        
    except Exception as e:
        response["mode"] = "FALLBACK"
        response["error"] = str(e)
        response["score"] = 50
        response["rating"] = "Neutral"
    
    return response


if __name__ == "__main__":
    result = get_composite_score()
    print(json.dumps(result, indent=2))
