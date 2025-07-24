import requests
import random
import time
from urllib.parse import urlparse
from urllib import robotparser
import logging

# ------------------------------------------------------------------------------
# This file was created to standardize the web request ethics. Per the requirements,
# I've incorporated a 1-5s random delay, user agents, etc...
#
# This module is meant to help you make web requests the right way: by rotating
# user agents, being nice to servers (polite delays), and respecting robots.txt.
# It also includes logging so you have visibility into what's happening—
# especially if something goes wrong or you're running this at scale.
# ------------------------------------------------------------------------------

# A comprehensive list of user agents (modern, old, mobile, and bot).
USER_AGENTS = [
    # Modern desktop browsers
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:114.0) Gecko/20100101 Firefox/114.0",
    # Older desktop browsers
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/601.1.56 (KHTML, like Gecko) Version/9.0 Safari/601.1.56",
    # Mobile browsers
    "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 10; Pixel 3a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.81 Mobile Safari/537.36",
    "Mozilla/5.0 (iPad; CPU OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0 Mobile/15E148 Safari/604.1",
    # Bots & non-browser (use sparingly if ever)
    # Add more as needed for even greater coverage
]

_robots_cache = {}

def can_fetch(url, user_agent=None):
    """
    Checks if we're allowed to fetch the given URL based on that site's robots.txt.
    Allows crawling if robots.txt is missing or malformed, but logs a warning or error.

    Args:
        url (str): The URL to access.
        user_agent (str, optional): The user agent for the check. Defaults to the first in USER_AGENTS.

    Returns:
        bool: True if allowed, or robots.txt is unreachable or malformed; False if not allowed by robots.txt.
    """
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    # Only grab and parse robots.txt for a site once (to cache it).
    if base_url not in _robots_cache:
        rp = robotparser.RobotFileParser()
        rp.set_url(f"{base_url}/robots.txt")
        try:
            rp.read()
            # If robots.txt is empty or can't be parsed (malformed), treat as missing and allow.
            if rp.default_entry is None and not rp.entries:
                logging.error(f"Malformed or empty robots.txt at {base_url}: proceeding with crawl.")
                _robots_cache[base_url] = None
            else:
                _robots_cache[base_url] = rp
        except Exception as ex:
            logging.warning(f"Couldn't read robots.txt from {base_url}: {ex} (proceeding with crawl)")
            _robots_cache[base_url] = None

    rp = _robots_cache[base_url]
    if rp is None:
        # robots.txt missing or malformed: allow crawling
        return True
    # robots.txt loaded and rules parsed
    return rp.can_fetch(user_agent or USER_AGENTS[0], url)


def ethical_get(url, max_retries=3, backoff_factor=2, skip_robots=False, **kwargs):
    """
    Makes a polite HTTP GET request:
    - Rotates user agents by default (unless you set your own in headers).
    - Checks robots.txt before making the request (unless skip_robots=True).
    - Waits a random 1–5 seconds so we don't hammer the server.
    - Handles 403 and 429 responses with exponential backoff and retries.
    - Logs any issues or blocks.

    Args:
        url (str): The URL to fetch.
        max_retries (int): Number of times to retry on 403/429.
        backoff_factor (int): Factor to multiply delay between retries.
        skip_robots (bool): If True, skips robots.txt check (useful for API calls).
        **kwargs: Additional arguments for requests.get (e.g., timeout, headers).

    Returns:
        requests.Response if successful (<400); None if blocked, failed, or too many retries.

    Example:
        response = ethical_get('https://example.com')
        if response:
            print(response.content)
        else:
            print('Request was blocked or failed')

    Tip:
        To control the user agent, use: headers={'User-Agent': 'MyBot/1.0'}
    """
    user_agent = random.choice(USER_AGENTS)
    headers = kwargs.pop('headers', {})
    headers.setdefault('User-Agent', user_agent)

    # Only check robots.txt if skip_robots is False
    if not skip_robots:
        if not can_fetch(url, headers['User-Agent']):
            logging.warning(f"Request blocked by robots.txt: {url}")
            return None

    delay = random.uniform(1, 5)
    attempt = 0

    while attempt <= max_retries:
        print(f"[DEBUG] ethical_get is fetching URL: {url} | Attempt: {attempt+1}/{max_retries+1}")
        time.sleep(delay)
        try:
            response = requests.get(url, headers=headers, **kwargs)
            if response.status_code in (403, 429):
                logging.warning(
                    f"Received status code {response.status_code} for {url} "
                    f"(attempt {attempt + 1}/{max_retries + 1}). Will retry with exponential backoff."
                )
                print(f"[DEBUG] HTTP error {response.status_code} for {url} (body: {response.text[:200]})")
                delay *= backoff_factor
                attempt += 1
                continue
            elif response.status_code >= 400:
                logging.error(f"HTTP error {response.status_code} for {url}: {response.text[:100]}")
                print(f"[DEBUG] HTTP error {response.status_code} for {url}: {response.text[:200]}")
                return None
            return response
        except Exception as e:
            logging.error(f"HTTP request to {url} failed: {e}")
            print(f"[DEBUG] Exception fetching {url}: {e}")
            return None

    logging.error(f"Giving up on {url} after {max_retries + 1} attempts (got 403/429 each time).")
    print(f"[DEBUG] Giving up on URL: {url} after {max_retries + 1} attempts (got 403/429 each time).")
    return None