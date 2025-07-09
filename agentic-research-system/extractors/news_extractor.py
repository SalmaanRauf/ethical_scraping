import os
import requests
import feedparser
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from agents.http_utils import ethical_get

class NewsExtractor:
    def __init__(self):
        """Initializes the extractor with API keys, target lists, and timezone info."""
        load_dotenv()
        self.gnews_api_key = os.getenv("GNEWS_API_KEY")
        
        # RSS feeds - Company-specific and regulatory feeds
        self.rss_feeds = {
            # Company-Specific Feeds
            "Capital One": "https://www.capitalone.com/about/newsroom/rss.xml",
            "Freddie Mac": "https://www.freddiemac.com/news/rss.xml",
            "Fannie Mae": "https://www.fanniemae.com/news/rss.xml",
            # Regulatory Feeds (General - will be processed for all companies)
            "OCC Enforcement Actions": "https://www.occ.gov/static/rss/ea-all-rss.xml",
            "Federal Reserve Enforcement Actions": "https://www.federalreserve.gov/feeds/enforcementactions.xml"
        }
        
        # Companies requiring API search via GNews.io (those without RSS feeds)
        self.api_targets = [
            "Navy Federal Credit Union", "PenFed Credit Union", "EagleBank", "Capital Bank N.A."
        ]
        
        # Target companies for filtering and analysis
        self.target_companies = [
            "Capital One", "Fannie Mae", "Freddie Mac", "Navy Federal Credit Union", 
            "PenFed Credit Union", "EagleBank", "Capital Bank N.A."
        ]
        
        # Timezone configuration
        self.default_rss_timezone = ZoneInfo("America/New_York")
        self.system_timezone = ZoneInfo("America/Los_Angeles")

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

    def _is_relevant_to_target_companies(self, title, summary, source_name):
        """
        Check if a regulatory RSS article is relevant to our target companies.
        """
        if source_name in ["OCC Enforcement Actions", "Federal Reserve Enforcement Actions"]:
            # For regulatory feeds, check if any target company is mentioned
            text_to_check = f"{title} {summary}".lower()
            return any(company.lower() in text_to_check for company in self.target_companies)
        else:
            # For company-specific feeds, always relevant
            return True

    def fetch_from_rss(self):
        """Parses all known RSS feeds for recent articles."""
        articles = []
        
        for source_name, url in self.rss_feeds.items():
            try:
                print(f"Fetching RSS feed for {source_name}...")
                response = ethical_get(url, timeout=30)
                if response is None or response.status_code != 200:
                    print(f"❌ Blocked or failed to fetch RSS feed for {source_name}")
                    continue
                
                feed = feedparser.parse(response.content)
                feed_articles_count = 0
                
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
                        # For regulatory feeds, check if relevant to target companies
                        summary = entry.summary if hasattr(entry, 'summary') else ''
                        
                        if self._is_relevant_to_target_companies(entry.title, summary, source_name):
                            # For regulatory feeds, try to identify which company is mentioned
                            company_mentioned = self._identify_mentioned_company(entry.title, summary)
                            
                            articles.append({
                                'company': company_mentioned or source_name,
                                'title': entry.title,
                                'link': entry.link,
                                'summary': summary,
                                'published_date': pub_date.isoformat(),
                                'source': 'RSS',
                                'type': 'news',
                                'feed_source': source_name  # Track which RSS feed it came from
                            })
                            feed_articles_count += 1
                        
                print(f"   📰 Found {feed_articles_count} relevant articles from {source_name}")
                        
            except Exception as e:
                print(f"❌ Error fetching RSS feed for {source_name}: {e}")
                continue
        
        print(f"✅ Found {len(articles)} total recent articles from RSS feeds")
        return articles

    def _identify_mentioned_company(self, title, summary):
        """
        Try to identify which target company is mentioned in a regulatory article.
        """
        text_to_check = f"{title} {summary}".lower()
        
        # Check for exact company name matches
        for company in self.target_companies:
            if company.lower() in text_to_check:
                return company
        
        # Check for common variations/abbreviations
        company_variations = {
            "capital one": "Capital One",
            "capitalone": "Capital One",
            "cof": "Capital One",
            "fannie mae": "Fannie Mae",
            "fanniemae": "Fannie Mae",
            "fnma": "Fannie Mae",
            "freddie mac": "Freddie Mac",
            "freddiemac": "Freddie Mac",
            "fmcc": "Freddie Mac",
            "navy federal": "Navy Federal Credit Union",
            "navy federal credit union": "Navy Federal Credit Union",
            "penfed": "PenFed Credit Union",
            "penfed credit union": "PenFed Credit Union",
            "eaglebank": "EagleBank",
            "eagle bank": "EagleBank",
            "egbn": "EagleBank",
            "capital bank": "Capital Bank N.A.",
            "capital bank n.a.": "Capital Bank N.A.",
            "cbnk": "Capital Bank N.A."
        }
        
        for variation, company in company_variations.items():
            if variation in text_to_check:
                return company
        
        return None

    def fetch_from_gnews(self):
        """
        Fetches news from GNews.io API for companies without dedicated RSS feeds.
        """
        if not self.gnews_api_key:
            print("⚠️  Warning: GNEWS_API_KEY not found. Skipping API news fetch.")
            return []
        
        articles = []
        base_url = "https://gnews.io/api/v4/search"
        print("Fetching news from GNews.io API...")

        for company in self.api_targets:
            try:
                # Use exact company name for better precision
                query = f'"{company}"'
                params = {
                    'q': query,
                    'lang': 'en',
                    'apikey': self.gnews_api_key,
                    'max': 10,
                    'sortby': 'publishedAt'  # Get most recent articles first
                }
                
                response = ethical_get(base_url, params=params, timeout=30)
                if response is None or response.status_code != 200:
                    print(f"❌ Blocked or received bad status code from GNews API for {company}")
                    continue
                
                data = response.json()
                
                if 'errors' in data:
                    print(f"❌ GNews API returned an error for '{company}': {data['errors']}")
                    continue

                company_articles_count = 0
                for article in data.get("articles", []):
                    pub_date_str = article.get("publishedAt")
                    if not pub_date_str:
                        continue

                    try:
                        # GNews provides UTC timestamps
                        utc_dt = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
                        pub_date_local = utc_dt.astimezone(self.system_timezone)

                        if self._is_recent_article(pub_date_local, hours_back=24):
                            articles.append({
                                'company': company,
                                'title': article.get("title", ""),
                                'link': article.get("url", ""),
                                'summary': article.get("description", ""),
                                'published_date': pub_date_local.isoformat(),
                                'source': 'GNews API',
                                'type': 'news',
                                'feed_source': 'GNews API'
                            })
                            company_articles_count += 1
                    except ValueError as e:
                        print(f"⚠️  Invalid date format in GNews response: {pub_date_str} - {e}")
                        continue
                
                print(f"   📰 Found {company_articles_count} recent articles for {company}")
            
            except requests.RequestException as e:
                print(f"❌ Error fetching data from GNews API for {company}: {e}")
            except Exception as e:
                print(f"❌ Unexpected error in GNews fetch for {company}: {e}")

        print(f"✅ Found {len(articles)} total recent articles from GNews API")
        return articles

    def get_all_news(self):
        """Combines news from both RSS and GNews API sources."""
        rss_articles = self.fetch_from_rss()
        api_articles = self.fetch_from_gnews()
        
        all_articles = rss_articles + api_articles
        print(f"📰 Total news articles found: {len(all_articles)}")
        
        # Log breakdown by source
        rss_count = len(rss_articles)
        api_count = len(api_articles)
        print(f"   📊 RSS Articles: {rss_count}")
        print(f"   📊 GNews API Articles: {api_count}")
        
        return all_articles 