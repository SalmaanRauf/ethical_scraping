import asyncio
from typing import List, Dict, Any
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging
from services.profile_loader import ProfileLoader
from config.config import AppConfig
from agents.scraper_agent import ScraperAgent
from extractors.http_utils import safe_async_get
from services.error_handler import log_error

# Set up developer logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class NewsExtractor:
    """
    Extracts news using a hybrid "API-first, scraper-enhancement" approach.
    It fetches data from GNews API and RSS feeds, then uses a scraper to get
    the full article content, ensuring maximum context and reliability.
    This version preserves the original, detailed fetching logic while integrating
    with the modern AppContext for configuration and services.
    """
    def __init__(self, scraper_agent: ScraperAgent, profile_loader: ProfileLoader):
        self.gnews_api_key = AppConfig.GNEWS_API_KEY
        self.scraper_agent = scraper_agent
        self.profile_loader = profile_loader
        # Use lazy loading instead of loading profiles in constructor
        self._company_profiles = None
        self._regulatory_feeds = None
        self.system_timezone = ZoneInfo("America/Los_Angeles") # Consistent timezone
        logger.info("🔍 NewsExtractor initialized")

    @property
    def company_profiles(self):
        """Lazy load company profiles when first accessed."""
        if self._company_profiles is None:
            self._company_profiles = self.profile_loader.load_profiles()
        return self._company_profiles

    @property
    def regulatory_feeds(self):
        """Lazy load regulatory feeds when first accessed."""
        if self._regulatory_feeds is None:
            self._regulatory_feeds = self.profile_loader.load_regulatory_feeds()
        return self._regulatory_feeds

    async def get_all_news(self, hours_back: int = None) -> List[Dict[str, Any]]:
        """Fetches news from all configured sources for all companies."""
        if hours_back is None:
            hours_back = AppConfig.NEWS_HOURS_BACK
        
        logger.info("📰 Starting news extraction for all companies (hours_back: %d)", hours_back)
        
        tasks = []
        for company_name in self.company_profiles.keys():
            tasks.append(self.get_news_for_company(company_name, hours_back))
        
        for feed_name, feed_url in self.regulatory_feeds.items():
            tasks.append(self._get_rss_articles(feed_url, feed_name, hours_back))

        all_articles = []
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, list):
                all_articles.extend(res)
            elif isinstance(res, Exception):
                log_error(res, "Failed to fetch news for a company or feed")

        logger.info("✅ News extraction complete: %d total articles found", len(all_articles))
        return all_articles

    async def get_news_for_company(self, company_name: str, hours_back: int = 168) -> List[Dict[str, Any]]:
        """
        Fetches and enhances news for a single company from GNews and its RSS feeds.
        """
        logger.info("🔍 Extracting news for company: %s", company_name)
        
        profile = self.company_profiles.get(company_name, {})
        if not profile:
            logger.warning("⚠️  No profile found for company: %s", company_name)
            return []

        tasks = [self._get_gnews_articles(company_name, hours_back)]
        
        # Add company-specific RSS feeds from old implementation
        company_rss_feeds = self._get_company_rss_feeds(company_name)
        logger.info("📡 Found %d RSS feeds for %s", len(company_rss_feeds), company_name)
        for rss_url in company_rss_feeds:
            tasks.append(self._get_rss_articles(rss_url, company_name, hours_back))
        
        # Add profile RSS feeds if any
        for rss_url in profile.get("rss_feeds", []):
            tasks.append(self._get_rss_articles(rss_url, company_name, hours_back))

        initial_articles = []
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, list):
                initial_articles.extend(res)
            elif isinstance(res, Exception):
                log_error(res, f"Failed to fetch a news source for {company_name}")

        logger.info("📊 Found %d initial articles for %s", len(initial_articles), company_name)

        enhancement_tasks = [self._gracefully_enhance_article(article) for article in initial_articles]
        enhanced_articles = await asyncio.gather(*enhancement_tasks)
        
        final_articles = [article for article in enhanced_articles if article]
        logger.info("✅ Enhanced %d articles for %s (success rate: %.1f%%)", 
                   len(final_articles), company_name, 
                   (len(final_articles) / len(initial_articles) * 100) if initial_articles else 0)
        
        return final_articles

    async def _get_gnews_articles(self, company_name: str, hours_back: int) -> List[Dict[str, Any]]:
        """API-FIRST: Fetches article summaries from the GNews API."""
        if not self.gnews_api_key:
            logger.warning("⚠️  No GNews API key configured")
            return []
        
        profile = self.company_profiles.get(company_name, {})
        query = profile.get("gnews_query", f'"{company_name}"') # Use custom query from profile

        logger.info("🔍 GNews API query for %s: %s", company_name, query)

        # GNews API does not support 'hours_back' directly, so we filter after fetching
        url = f"https://gnews.io/api/v4/search?q={query}&lang=en&country=us&max=15&apikey={self.gnews_api_key}"  # Increased from 10 to 15
        response = await safe_async_get(url)
        if not response:
            logger.error("❌ GNews API request failed for %s", company_name)
            return []
        
        try:
            data = response.json()
            articles = [self._format_gnews_article(article) for article in data.get("articles", [])]
            recent_articles = [a for a in articles if self._is_recent_article(a.get("published_date"), hours_back)]
            
            logger.info("📰 GNews API returned %d articles for %s (%d within %d hours)", 
                       len(articles), company_name, len(recent_articles), hours_back)
            return recent_articles
        except Exception as e:
            log_error(e, f"Error parsing GNews response for {company_name}")
            return []

    async def _get_rss_articles(self, url: str, source_name: str, hours_back: int) -> List[Dict[str, Any]]:
        """API-FIRST: Fetches article summaries from a given RSS feed URL."""
        logger.info("📡 Fetching RSS feed: %s for %s", url, source_name)
        
        response = await safe_async_get(url)
        if not response:
            logger.error("❌ RSS feed request failed: %s", url)
            return []
        
        try:
            feed = feedparser.parse(response.text)
            articles = []
            for entry in feed.entries:
                article = self._format_rss_entry(entry, source_name)
                if self._is_recent_article(article.get("published_date"), hours_back):
                    articles.append(article)
            
            logger.info("📰 RSS feed returned %d articles for %s (%d within %d hours)", 
                       len(feed.entries), source_name, len(articles), hours_back)
            return articles
        except Exception as e:
            log_error(e, f"Error parsing RSS feed {url}")
            return []

    async def _gracefully_enhance_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """
        SCRAPER-ENHANCEMENT: Attempts to scrape the full text of an article.
        If scraping fails, it falls back to the original extracted text or summary.
        """
        url = article.get('link')
        if not url:
            logger.warning("⚠️  No URL found for article: %s", article.get('title', 'Unknown'))
            return article

        try:
            logger.debug("🔍 Scraping article: %s", url)
            html_content = await self.scraper_agent.fetch_content(url)
            
            if html_content:
                # Use BeautifulSoup to extract clean text
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # Get text and clean it up
                full_text = soup.get_text()
                lines = (line.strip() for line in full_text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                full_text = ' '.join(chunk for chunk in chunks if chunk)
                
                if len(full_text) > 100:  # Only use scraped content if substantial
                    article['content'] = full_text
                    logger.info("✅ Successfully scraped article: %s (%d chars)", 
                               article.get('title', 'Unknown'), len(full_text))
                else:
                    logger.warning("⚠️  Scraped content too short for: %s (%d chars)", 
                                  article.get('title', 'Unknown'), len(full_text))
            else:
                logger.warning("⚠️  Failed to scrape content for: %s", article.get('title', 'Unknown'))
                
        except Exception as e:
            logger.error("❌ Error scraping article %s: %s", url, str(e))
        
        return article

    def _format_gnews_article(self, article: Dict) -> Dict:
        return {
            "source": "GNews",
            "title": article.get("title"),
            "link": article.get("url"),
            "published_date": article.get("publishedAt"),
            "content": article.get("content", ""),
        }

    def _format_rss_entry(self, entry: Dict, source_name: str) -> Dict:
        # Use feedparser's parsed_parsed for robust date handling
        published_date = None
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            published_date = datetime(*entry.published_parsed[:6], tzinfo=ZoneInfo("UTC")).astimezone(self.system_timezone).isoformat()
        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            published_date = datetime(*entry.updated_parsed[:6], tzinfo=ZoneInfo("UTC")).astimezone(self.system_timezone).isoformat()

        return {
            "source": f"RSS ({source_name})",
            "title": entry.get("title"),
            "link": entry.get("link"),
            "published_date": published_date,
            "content": entry.get("summary", ""),
        }

    def _is_recent_article(self, published_date_str: str, hours_back: int) -> bool:
        if not published_date_str:
            return False
        try:
            # Handle various ISO formats and ensure timezone awareness
            published_date = datetime.fromisoformat(published_date_str.replace('Z', '+00:00'))
            if published_date.tzinfo is None:
                published_date = published_date.replace(tzinfo=ZoneInfo("UTC"))
            
            now = datetime.now(self.system_timezone)
            cutoff = now - timedelta(hours=hours_back)
            return published_date >= cutoff
        except Exception as e:
            log_error(e, f"Error parsing date {published_date_str} for recency check.")
            return False

    def _get_company_rss_feeds(self, company_name: str) -> List[str]:
        """Get company-specific RSS feeds from the old implementation."""
        rss_feeds = {
            "Capital One": "https://api.rss2json.com/v1/api.json?rss_url=https%3A%2F%2Fwww.bing.com%2Fnews%2Fsearch%3Fq%3D%2522Capital%2520One%2520Financial%2520Corporation%2522%2520COF%26format%3DRSS",
            "Freddie Mac": "https://api.rss2json.com/v1/api.json?rss_url=https%3A%2F%2Fwww.bing.com%2Fnews%2Fsearch%3Fq%3DFreddie%2520Mac%2520-%2520Federal%2520Home%2520Loan%2520Mortgage%2520Corporation%2520%2522FMCC%2522%26format%3DRSS",
            "Freddie Mac (SECOND FEED)": "https://api.rss2json.com/v1/api.json?rss_url=https%3A%2F%2Fwww.bing.com%2Fnews%2Fsearch%3Fq%3D%2522Freddie%2520Mac%2520-%2520Federal%2520Home%2520Loan%2520Mortgage%2520Corporation%2522%2520FMCC%26format%3DRSS",
            "Fannie Mae": "https://api.rss2json.com/v1/api.json?rss_url=https%3A%2F%2Fwww.bing.com%2Fnews%2Fsearch%3Fq%3D%2522Federal%2520National%2520Mortgage%2520Association%2522%2520FNMA%26format%3DRSS",
        }
        
        # Return feeds for the specific company
        feeds = []
        if company_name in rss_feeds:
            feeds.append(rss_feeds[company_name])
        
        # Add regulatory feeds for all companies
        regulatory_feeds = [
            "https://www.occ.gov/rss/occ_bulletins.xml",
            "https://www.federalreserve.gov/feeds/press_enforcement.xml"
        ]
        feeds.extend(regulatory_feeds)
        
        return feeds