import asyncio
from typing import List, Dict, Any
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from services.profile_loader import ProfileLoader
from config.config import AppConfig
from agents.scraper_agent import ScraperAgent
from extractors.http_utils import safe_async_get
from services.error_handler import log_error

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
        self.company_profiles = self.profile_loader.load_profiles()
        self.regulatory_feeds = self.profile_loader.load_regulatory_feeds()
        self.system_timezone = ZoneInfo("America/Los_Angeles") # Consistent timezone

    async def get_all_news(self, hours_back: int = None) -> List[Dict[str, Any]]:
        """Fetches news from all configured sources for all companies."""
        if hours_back is None:
            hours_back = AppConfig.NEWS_HOURS_BACK
        """Fetches news from all configured sources for all companies."""
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

        return all_articles

    async def get_news_for_company(self, company_name: str, hours_back: int = 168) -> List[Dict[str, Any]]:
        """
        Fetches and enhances news for a single company from GNews and its RSS feeds.
        """
        profile = self.company_profiles.get(company_name, {})
        if not profile:
            return []

        tasks = [self._get_gnews_articles(company_name, hours_back)]
        for rss_url in profile.get("rss_feeds", []):
            tasks.append(self._get_rss_articles(rss_url, company_name, hours_back))

        initial_articles = []
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, list):
                initial_articles.extend(res)
            elif isinstance(res, Exception):
                log_error(res, f"Failed to fetch a news source for {company_name}")

        enhancement_tasks = [self._gracefully_enhance_article(article) for article in initial_articles]
        enhanced_articles = await asyncio.gather(*enhancement_tasks)
        
        return [article for article in enhanced_articles if article]

    async def _get_gnews_articles(self, company_name: str, hours_back: int) -> List[Dict[str, Any]]:
        """API-FIRST: Fetches article summaries from the GNews API."""
        if not self.gnews_api_key:
            return []
        
        profile = self.company_profiles.get(company_name, {})
        query = profile.get("gnews_query", f'"{company_name}"') # Use custom query from profile

        # GNews API does not support 'hours_back' directly, so we filter after fetching
        url = f"https://gnews.io/api/v4/search?q={query}&lang=en&country=us&max=10&apikey={self.gnews_api_key}"
        response = await safe_async_get(url)
        if not response:
            return []
        
        try:
            data = response.json()
            articles = [self._format_gnews_article(article) for article in data.get("articles", [])]
            return [a for a in articles if self._is_recent_article(a.get("published_date"), hours_back)]
        except Exception as e:
            log_error(e, f"Error parsing GNews response for {company_name}")
            return []

    async def _get_rss_articles(self, url: str, source_name: str, hours_back: int) -> List[Dict[str, Any]]:
        """API-FIRST: Fetches article summaries from a given RSS feed URL."""
        response = await safe_async_get(url)
        if not response:
            return []
        
        try:
            feed = feedparser.parse(response.text)
            articles = [self._format_rss_entry(entry, source_name) for entry in feed.entries]
            return [a for a in articles if self._is_recent_article(a.get("published_date"), hours_back)]
        except Exception as e:
            log_error(e, f"Error parsing RSS feed {url}")
            return []

    async def _gracefully_enhance_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """
        SCRAPER-ENHANCEMENT: Attempts to scrape the full content of an article from its URL.
        If scraping fails, it falls back to the original summary content.
        """
        url = article.get('link')
        if not url:
            return article

        try:
            html_content = await self.scraper_agent.fetch_content(url)
            if html_content:
                soup = BeautifulSoup(html_content, 'html.parser')
                main_content = soup.find('main') or soup.find('article') or soup.body
                if main_content:
                    article['content'] = main_content.get_text(separator='\n', strip=True)
        except Exception as e:
            log_error(e, f"Graceful enhancement failed for {url}. Falling back to summary.")
        
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