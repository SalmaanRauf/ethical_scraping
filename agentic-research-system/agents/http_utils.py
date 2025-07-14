import requests
import random
import time
from urllib.parse import urlparse
from urllib import robotparser

# List of common browser user agent strings for ethical web scraping
# These help identify the client making HTTP requests to web servers
# Rotating between different user agents helps avoid being blocked by rate limiting
# 
# YES, this is common practice in web scraping for several reasons:
# 1. Prevents detection as automated traffic
# 2. Mimics real browser behavior 
# 3. Reduces likelihood of being rate-limited or blocked
# 4. Many websites expect standard browser user agents
# 5. Part of responsible/ethical scraping practices
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
    # Add more user agents as needed
]

_robots_cache = {}
_last_request_time = 0
_min_request_interval = 1.0  # 1 second between requests

def can_fetch(url, user_agent=None):
    """Check robots.txt for the given URL and user agent."""
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    if base_url not in _robots_cache:
        rp = robotparser.RobotFileParser()
        rp.set_url(f"{base_url}/robots.txt")
        try:
            rp.read()
        except Exception:
            rp = None
        _robots_cache[base_url] = rp
    rp = _robots_cache[base_url]
    if rp is None:
        return True  # If robots.txt can't be fetched, default to allow
    return rp.can_fetch(user_agent or USER_AGENTS[0], url)

def ethical_get(url, timeout=30, max_retries=3, **kwargs):
    """Make an HTTP GET request with user-agent rotation, robots.txt compliance, rate limiting, timeout, and retry logic."""
    global _last_request_time
    
    # Rate limiting
    current_time = time.time()
    time_since_last = current_time - _last_request_time
    if time_since_last < _min_request_interval:
        sleep_time = _min_request_interval - time_since_last
        time.sleep(sleep_time)
    
    user_agent = random.choice(USER_AGENTS)
    headers = kwargs.pop('headers', {})
    headers['User-Agent'] = user_agent
    
    if not can_fetch(url, user_agent):
        print(f"Blocked by robots.txt: {url}")
        return None
    
    # Retry logic with exponential backoff
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=timeout, **kwargs)
            _last_request_time = time.time()
            return response
        except requests.exceptions.Timeout:
            print(f"Timeout on attempt {attempt + 1} for {url}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
        except requests.exceptions.RequestException as e:
            print(f"Request failed on attempt {attempt + 1} for {url}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
        except Exception as e:
            print(f"Unexpected error on attempt {attempt + 1} for {url}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
    
    print(f"All {max_retries} attempts failed for {url}")
    return None 