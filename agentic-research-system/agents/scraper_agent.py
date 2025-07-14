import asyncio
import logging
import time
from typing import Optional, Dict, Any
from collections import defaultdict
from urllib.parse import urlparse
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)

class ScraperAgent:
    """
    Uses playwright and beautifulsoup4 to scrape and clean the main content of any URL.
    Integrates with our existing architecture for enhanced data extraction.
    """

    def __init__(self):
        self.browser = None
        self.page = None
        self.rate_limit_semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
        self.last_request_times = defaultdict(float)  # Per-domain tracking
        self.min_request_interval = 1.0  # 1 second between requests
        self._rate_limit_lock = asyncio.Lock()  # Lock for rate limiting
        self._playwright = None
        
        logger.info("✅ ScraperAgent initialized successfully")

    async def _ensure_browser(self):
        """Ensure browser is initialized."""
        if not self._playwright:
            self._playwright = await async_playwright().start()
            self.browser = await self._playwright.chromium.launch(headless=True)
            self.page = await self.browser.new_page()
            logger.info("✅ Browser initialized")

    async def scrape_url(self, url: str, content_type: str = "general", timeout: int = 30) -> Optional[str]:
        """
        Scrape and extract main content from a URL with rate limiting and detailed error handling.
        
        Args:
            url: The URL to scrape
            content_type: Type of content ("news", "sec_filing", "procurement", "general")
            
        Returns:
            Extracted text content or None if failed
        """
        if not url:
            return None
            
        # Extract domain for per-domain rate limiting
        try:
            domain = urlparse(url).netloc
        except Exception:
            domain = "unknown"
            
        # Rate limiting with proper locking
        async with self.rate_limit_semaphore:
            async with self._rate_limit_lock:
                current_time = time.time()
                time_since_last = current_time - self.last_request_times[domain]
                
                if time_since_last < self.min_request_interval:
                    sleep_time = self.min_request_interval - time_since_last
                    await asyncio.sleep(sleep_time)
                
                self.last_request_times[domain] = time.time()
            
            try:
                # Ensure browser is ready
                await self._ensure_browser()
                
                # Navigate to the page
                await self.page.goto(url, timeout=timeout * 1000)
                
                # Wait for content to load
                await self.page.wait_for_load_state("networkidle", timeout=10000)
                
                # Get the page content
                content = await self.page.content()
                
                # Parse with BeautifulSoup
                soup = BeautifulSoup(content, 'html.parser')
                
                # Extract content based on type
                extracted_content = self._extract_content_by_type(soup, content_type)
                
                if extracted_content:
                    logger.info(f"✅ Successfully scraped {len(extracted_content)} chars from {url}")
                    return extracted_content
                else:
                    logger.warning(f"⚠️  No content extracted from {url}")
                    return None
                    
            except Exception as e:
                logger.error(f"❌ Error scraping {url}: {str(e)}")
                logger.error(f"📋 Exception type: {type(e).__name__}")
                # Log full traceback for debugging
                import traceback
                logger.error(f"📋 Full traceback: {traceback.format_exc()}")
                return None

    def _extract_content_by_type(self, soup: BeautifulSoup, content_type: str) -> str:
        """Extract content based on the type of page."""
        
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'noscript']):
            element.decompose()
        
        # Remove elements with common ad/analytics classes
        for element in soup.find_all(class_=re.compile(r'(ad|ads|advertisement|analytics|tracking|social|share|comment|sidebar|popup|modal|overlay)', re.I)):
            element.decompose()
        
        if content_type == "news":
            return self._extract_news_content(soup)
        elif content_type == "sec_filing":
            return self._extract_sec_content(soup)
        elif content_type == "procurement":
            return self._extract_procurement_content(soup)
        else:
            return self._extract_general_content(soup)

    def _extract_news_content(self, soup: BeautifulSoup) -> str:
        """Extract news article content."""
        content_parts = []
        
        # Try to find title
        title = soup.find('h1') or soup.find('title')
        if title:
            content_parts.append(f"# {title.get_text().strip()}")
        
        # Try to find article body
        article = soup.find('article') or soup.find(class_=re.compile(r'(article|post|entry|content)', re.I))
        if article:
            # Extract paragraphs
            paragraphs = article.find_all(['p', 'h2', 'h3', 'h4'])
            for p in paragraphs:
                text = p.get_text().strip()
                if text and len(text) > 20:  # Filter out short snippets
                    if p.name.startswith('h'):
                        content_parts.append(f"\n## {text}")
                    else:
                        content_parts.append(text)
        
        return '\n\n'.join(content_parts)

    def _extract_sec_content(self, soup: BeautifulSoup) -> str:
        """Extract SEC filing content."""
        content_parts = []
        
        # Try to find filing title
        title = soup.find('h1') or soup.find('title')
        if title:
            content_parts.append(f"# {title.get_text().strip()}")
        
        # Look for filing content
        filing_content = soup.find(class_=re.compile(r'(filing|document|content|text)', re.I))
        if filing_content:
            paragraphs = filing_content.find_all(['p', 'h2', 'h3', 'h4', 'div'])
            for p in paragraphs:
                text = p.get_text().strip()
                if text and len(text) > 20:
                    if p.name.startswith('h'):
                        content_parts.append(f"\n## {text}")
                    else:
                        content_parts.append(text)
        
        return '\n\n'.join(content_parts)

    def _extract_procurement_content(self, soup: BeautifulSoup) -> str:
        """Extract procurement notice content."""
        content_parts = []
        
        # Try to find notice title
        title = soup.find('h1') or soup.find('title')
        if title:
            content_parts.append(f"# {title.get_text().strip()}")
        
        # Look for procurement details
        procurement_content = soup.find(class_=re.compile(r'(procurement|notice|solicitation|contract)', re.I))
        if procurement_content:
            paragraphs = procurement_content.find_all(['p', 'h2', 'h3', 'h4', 'div'])
            for p in paragraphs:
                text = p.get_text().strip()
                if text and len(text) > 20:
                    if p.name.startswith('h'):
                        content_parts.append(f"\n## {text}")
                    else:
                        content_parts.append(text)
        
        return '\n\n'.join(content_parts)

    def _extract_general_content(self, soup: BeautifulSoup) -> str:
        """Extract general page content."""
        content_parts = []
        
        # Try to find main title
        title = soup.find('h1') or soup.find('title')
        if title:
            content_parts.append(f"# {title.get_text().strip()}")
        
        # Find main content area
        main_content = soup.find('main') or soup.find(class_=re.compile(r'(main|content|body|text)', re.I))
        if main_content:
            paragraphs = main_content.find_all(['p', 'h2', 'h3', 'h4'])
            for p in paragraphs:
                text = p.get_text().strip()
                if text and len(text) > 20:
                    if p.name.startswith('h'):
                        content_parts.append(f"\n## {text}")
                    else:
                        content_parts.append(text)
        
        return '\n\n'.join(content_parts)

    async def scrape_multiple_urls(self, urls: list, content_type: str = "general") -> Dict[str, str]:
        """
        Scrape multiple URLs concurrently.
        
        Args:
            urls: List of URLs to scrape
            content_type: Type of content for all URLs
            
        Returns:
            Dictionary mapping URLs to their extracted content
        """
        if not urls:
            return {}
            
        async def scrape_single(url):
            content = await self.scrape_url(url, content_type)
            return url, content
            
        # Scrape all URLs concurrently
        tasks = [scrape_single(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out failed scrapes
        successful_results = {}
        for url, content in results:
            if isinstance(content, Exception):
                logger.error(f"❌ Exception scraping {url}: {content}")
            elif content:
                successful_results[url] = content
                
        logger.info(f"✅ Successfully scraped {len(successful_results)}/{len(urls)} URLs")
        return successful_results

    def is_available(self) -> bool:
        """Check if the scraper is properly initialized and available."""
        return self._playwright is not None

    async def close(self):
        """Clean up browser resources."""
        if self.page:
            try:
                await self.page.close()
            except Exception as e:
                logger.error(f"❌ Error closing page: {e}")
        
        if self.browser:
            try:
                await self.browser.close()
            except Exception as e:
                logger.error(f"❌ Error closing browser: {e}")
        
        if self._playwright:
            try:
                await self._playwright.stop()
                logger.info("✅ ScraperAgent browser resources cleaned up")
            except Exception as e:
                logger.error(f"❌ Error closing ScraperAgent: {e}") 