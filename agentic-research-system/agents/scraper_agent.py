import asyncio
import logging
import time
from typing import Optional, Dict, Any
from collections import defaultdict
from urllib.parse import urlparse
from crawl4ai import AsyncWebCrawler
from crawl4ai.config import BrowserConfig, CrawlerRunConfig

logger = logging.getLogger(__name__)

class ScraperAgent:
    """
    Uses crawl4ai to scrape and clean the main content of any URL.
    Integrates with our existing architecture for enhanced data extraction.
    """

    def __init__(self):
        self.crawler = None
        self.rate_limit_semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
        self.last_request_times = defaultdict(float)  # Per-domain tracking
        self.min_request_interval = 1.0  # 1 second between requests
        self._rate_limit_lock = asyncio.Lock()  # Lock for rate limiting
        
        try:
            self.crawler = AsyncWebCrawler(
                browser_config=BrowserConfig(
                    provider="playwright",
                    headless=True
                )
            )
            logger.info("✅ ScraperAgent initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize ScraperAgent: {e}")
            self.crawler = None

    async def scrape_url(self, url: str, content_type: str = "general", timeout: int = 30) -> Optional[str]:
        """
        Scrape and extract main content from a URL with rate limiting and detailed error handling.
        
        Args:
            url: The URL to scrape
            content_type: Type of content ("news", "sec_filing", "procurement", "general")
            
        Returns:
            Extracted text content or None if failed
        """
        if not url or not self.crawler:
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
                # Customize extraction prompt based on content type
                extraction_prompts = {
                    "news": (
                        "Extract the main article content including title, date, author, and body text. "
                        "Format as clean Markdown. Omit navigation, ads, comments, and unrelated sections. "
                        "Focus on the primary news content and any financial details mentioned."
                    ),
                    "sec_filing": (
                        "Extract the main filing content including company information, financial data, "
                        "risk factors, and key disclosures. Format as clean Markdown. "
                        "Focus on material information and financial statements."
                    ),
                    "procurement": (
                        "Extract the main procurement notice content including project description, "
                        "requirements, deadlines, and budget information. Format as clean Markdown. "
                        "Focus on the scope of work and technical requirements."
                    ),
                    "general": (
                        "Extract the main content including title, date, and body text. "
                        "Format as clean Markdown. Omit navigation, ads, and unrelated sections."
                    )
                }
                
                prompt = extraction_prompts.get(content_type, extraction_prompts["general"])
                
                run_cfg = CrawlerRunConfig(
                    url=url,
                    extraction_strategy="llm-extractor",
                    llm_extraction_prompt=prompt,
                    timeout=timeout
                )
                
                result = await self.crawler.arun(config=run_cfg)
                extracted_content = result.markdown or ""
                
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
        return self.crawler is not None

    async def close(self):
        """Clean up browser resources."""
        if self.crawler:
            try:
                await self.crawler.close()
                logger.info("✅ ScraperAgent browser resources cleaned up")
            except Exception as e:
                logger.error(f"❌ Error closing ScraperAgent: {e}") 