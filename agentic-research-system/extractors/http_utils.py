import asyncio
import httpx
from typing import Optional, Dict
from services.error_handler import log_error

# User agents for web scraping
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0"
]

def can_fetch(url: str) -> bool:
    """
    Check if a URL can be fetched based on robots.txt and other restrictions.
    
    Args:
        url: URL to check
        
    Returns:
        True if URL can be fetched, False otherwise
    """
    # Simple implementation - can be enhanced with robots.txt parsing
    blocked_domains = ['facebook.com', 'twitter.com', 'instagram.com']
    return not any(domain in url for domain in blocked_domains)

async def safe_async_get(
    url: str, 
    headers: Optional[Dict] = None, 
    params: Optional[Dict] = None, 
    retries: int = 3, 
    backoff_factor: float = 0.5,
    **kwargs
) -> Optional[httpx.Response]:
    """
    Performs a robust, asynchronous GET request with retry logic.

    Args:
        url (str): The URL to request.
        headers (dict, optional): Request headers.
        params (dict, optional): URL parameters.
        retries (int): The maximum number of retry attempts.
        backoff_factor (float): The base factor for exponential backoff delay.
        **kwargs: Additional arguments to pass to the httpx request.

    Returns:
        Optional[httpx.Response]: The response object on success, None on failure.
    """
    async with httpx.AsyncClient() as client:
        for attempt in range(retries):
            try:
                response = await client.get(url, headers=headers, params=params, **kwargs)
                response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
                return response
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as e:
                # Only retry on timeout, network errors, or 5xx server errors
                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code < 500:
                    log_error(e, f"Client error fetching {url}. Will not retry.")
                    return None # Do not retry on 4xx client errors

                if attempt == retries - 1:
                    log_error(e, f"Final attempt failed for {url}.")
                    return None # All retries failed
                
                delay = backoff_factor * (2 ** attempt)
                log_error(e, f"Attempt {attempt + 1}/{retries} failed for {url}. Retrying in {delay:.2f}s.")
                await asyncio.sleep(delay)
    return None
