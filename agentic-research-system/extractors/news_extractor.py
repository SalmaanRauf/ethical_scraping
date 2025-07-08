import os
import requests
import feedparser
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from agents.http_utils import ethical_get

class NewsExtractor:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        self.marketaux_api_key = os.getenv("MARKETAUX_API_KEY")
        
        # RSS feeds for companies that have them (final, corrected)
        self.rss_feeds = {
            "Capital One": "https://www.capitalone.com/about/newsroom/rss.xml",
            "Freddie Mac": "https://www.freddiemac.com/news/rss.xml",
            "Fannie Mae": "https://www.fanniemae.com/news/rss.xml"
        }
        
        # Companies to search via API (those without RSS feeds)
        self.api_targets = [
            "Navy Federal Credit Union", "PenFed Credit Union", "EagleBank", "Capital Bank N.A."
        ]
        
        # Target companies for filtering (final, corrected)
        self.target_companies = [
            "Capital One", "Fannie Mae", "Freddie Mac", "Navy Federal Credit Union", "PenFed Credit Union", "EagleBank", "Capital Bank N.A."
        ]
        
        # Default timezone for RSS feeds (most US financial feeds are in EST/EDT)
        self.default_rss_timezone = ZoneInfo("America/New_York")
        
        # System timezone for comparison
        self.system_timezone = ZoneInfo("America/Los_Angeles")  # Pacific Time

    def _parse_rss_datetime(self, entry, field_name):
        """
        Parse datetime from RSS feed with proper timezone handling.
        Returns timezone-aware datetime in system timezone.
        """
        if not hasattr(entry, field_name) or not getattr(entry, field_name):
            return None
        
        parsed_time = getattr(entry, field_name)
        
        try:
            # Create naive datetime from parsed time
            naive_dt = datetime(*parsed_time[:6])
            
            # Check if the feed provides timezone information
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                # Some RSS feeds include timezone info in the original string
                original_date_str = getattr(entry, field_name.replace('_parsed', ''), '')
                
                # Try to extract timezone from original string
                if original_date_str:
                    # Common timezone patterns in RSS feeds
                    tz_patterns = [
                        ('GMT', ZoneInfo("GMT")),
                        ('UTC', ZoneInfo("UTC")),
                        ('EST', ZoneInfo("America/New_York")),
                        ('EDT', ZoneInfo("America/New_York")),
                        ('PST', ZoneInfo("America/Los_Angeles")),
                        ('PDT', ZoneInfo("America/Los_Angeles")),
                        ('CST', ZoneInfo("America/Chicago")),
                        ('CDT', ZoneInfo("America/Chicago")),
                    ]
                    
                    for tz_str, tz_info in tz_patterns:
                        if tz_str in original_date_str.upper():
                            # Found timezone info, use it
                            aware_dt = naive_dt.replace(tzinfo=tz_info)
                            # Convert to system timezone
                            return aware_dt.astimezone(self.system_timezone)
            
            # No timezone info found, assume default RSS timezone
            aware_dt = naive_dt.replace(tzinfo=self.default_rss_timezone)
            
            # Convert to system timezone for consistent comparison
            return aware_dt.astimezone(self.system_timezone)
            
        except Exception as e:
            print(f"⚠️  Error parsing RSS datetime: {e}")
            return None

    def _get_system_datetime(self):
        """Get current datetime in system timezone."""
        return datetime.now(self.system_timezone)

    def _is_recent_article(self, pub_date, hours_back=24):
        """
        Check if article is within the specified time window.
        All datetimes should be timezone-aware and in the same timezone.
        """
        if not pub_date:
            return False
        
        # Ensure pub_date is timezone-aware
        if pub_date.tzinfo is None:
            print(f"⚠️  Warning: Article has naive datetime, assuming system timezone")
            pub_date = pub_date.replace(tzinfo=self.system_timezone)
        
        # Get current time in system timezone
        now = self._get_system_datetime()
        
        # Calculate cutoff time
        cutoff_time = now - timedelta(hours=hours_back)
        
        # Compare timezone-aware datetimes
        is_recent = pub_date >= cutoff_time
        
        if is_recent:
            print(f"   ✅ Recent article: {pub_date.strftime('%Y-%m-%d %H:%M %Z')} (within {hours_back}h)")
        else:
            print(f"   ⚪ Old article: {pub_date.strftime('%Y-%m-%d %H:%M %Z')} (older than {hours_back}h)")
        
        return is_recent

    def fetch_from_rss(self):
        """Parses all known RSS feeds with proper timezone handling."""
        articles = []
        for company, url in self.rss_feeds.items():
            try:
                print(f"Fetching RSS feed for {company}...")
                response = ethical_get(url, timeout=30)
                if response is None or response.status_code != 200:
                    print(f"Blocked or failed to fetch RSS feed for {company}")
                    continue
                feed = feedparser.parse(response.content)
                
                for entry in feed.entries:
                    # Parse publication date with timezone handling
                    pub_date = None
                    
                    # Try published_parsed first, then updated_parsed
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_date = self._parse_rss_datetime(entry, 'published_parsed')
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        pub_date = self._parse_rss_datetime(entry, 'updated_parsed')
                    
                    # Check if article is recent (within last 24 hours)
                    if pub_date and self._is_recent_article(pub_date, hours_back=24):
                        articles.append({
                            'company': company,
                            'title': entry.title,
                            'link': entry.link,
                            'summary': entry.summary if hasattr(entry, 'summary') else '',
                            'published_date': pub_date.isoformat(),
                            'source': 'RSS',
                            'type': 'news'
                        })
                        
            except Exception as e:
                print(f"Error fetching RSS feed for {company}: {e}")
                continue
        
        print(f"Found {len(articles)} recent articles from RSS feeds")
        return articles

    def fetch_from_api(self):
        """Fetches news from Marketaux API for companies without RSS."""
        if not self.marketaux_api_key:
            print("Warning: MARKETAUX_API_KEY not found. Skipping API news fetch.")
            return []
        
        articles = []
        try:
            print("Fetching news from Marketaux API...")
            
            # Search for each target company
            for company in self.api_targets:
                params = {
                    'api_token': self.marketaux_api_key,
                    'entity': company,
                    'language': 'en',
                    'limit': 10,
                    'sort': 'published_at'
                }
                
                response = ethical_get("https://api.marketaux.com/v1/news/all", params=params, timeout=30)
                if response is None:
                    print(f"Blocked or failed to fetch Marketaux API for {company}")
                    continue
                response.raise_for_status()
                data = response.json()
                
                for article in data.get("data", []):
                    pub_date_str = article.get("published_at", "")
                    if pub_date_str:
                        try:
                            # Marketaux API provides ISO 8601 format with timezone
                            # Handle both 'Z' (UTC) and explicit timezone offsets
                            if pub_date_str.endswith('Z'):
                                # Convert UTC to system timezone
                                utc_dt = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
                                pub_date = utc_dt.astimezone(self.system_timezone)
                            else:
                                # Already has timezone info
                                pub_date = datetime.fromisoformat(pub_date_str)
                                # Convert to system timezone for consistency
                                pub_date = pub_date.astimezone(self.system_timezone)
                            
                            # Check if article is recent
                            if self._is_recent_article(pub_date, hours_back=24):
                                articles.append({
                                    'company': company,
                                    'title': article.get("title", ""),
                                    'link': article.get("url", ""),
                                    'summary': article.get("description", ""),
                                    'published_date': pub_date.isoformat(),
                                    'source': 'Marketaux API',
                                    'type': 'news'
                                })
                        except ValueError as e:
                            print(f"⚠️  Invalid date format in API response: {pub_date_str} - {e}")
                            continue
                            
        except requests.RequestException as e:
            print(f"Error fetching data from Marketaux API: {e}")
        except Exception as e:
            print(f"Unexpected error in API news fetch: {e}")
        
        print(f"Found {len(articles)} recent articles from Marketaux API")
        return articles

    def get_all_news(self):
        """Combines news from both RSS and API sources."""
        rss_articles = self.fetch_from_rss()
        api_articles = self.fetch_from_api()
        
        all_articles = rss_articles + api_articles
        print(f"Total news articles found: {len(all_articles)}")
        
        return all_articles 