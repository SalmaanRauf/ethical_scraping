"""
Extractor for news related to selected financial institutions.
Fetches recent news both from known RSS feeds and the GNews.io API,
filters for recency and relevance, and normalizes publication datetimes.

Classes:
    NewsExtractor: Combines RSS and API extraction with company/entity matching and timezone handling.
"""

import os
import requests
import feedparser
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from extractors.http_utils import ethical_get
import logging

# Configure logging for this extractor
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)

class NewsExtractor:
    """
    Extracts recent news articles relating to key companies from RSS feeds and GNews.io API.
    Handles timezone normalization, recency filtering, and company reference matching.
    Supports async enhancement of articles via a webscraper agent.
    """
    def __init__(self, scraper_agent=None):
        """
        Initializes the extractor with API keys, target lists, feed sources, and timezone info.
        """
        load_dotenv()
        self.gnews_api_key = os.getenv("GNEWS_API_KEY")
        self.scraper_agent = scraper_agent

        self.target_companies = [
            "Capital One",
            "Fannie Mae",
            "Freddie Mac",
            "Navy Federal Credit Union",
            "PenFed Credit Union",
            "EagleBank",
            "Capital Bank N.A."
        ]

        self.custom_search_queries = {
            "Navy Federal Credit Union": '"Navy Federal Credit Union" OR "Navy Federal" OR "Navy" OR Navy Federal',
            "PenFed Credit Union": '"PenFed Credit Union" OR "PenFed" OR PenFed',
            "EagleBank": '"EagleBank" OR "Eagle Bank" OR EagleBank OR Eagle Bank',
            "Capital Bank N.A.": '"Capital Bank N.A." OR "Capital Bank" OR Capital Bank N.A. OR Capital Bank'
        }

        # RSS feeds - Company-specific and regulatory feeds
        self.rss_feeds = {
            # Company-Specific Feeds
            "Capital One": "https://api.rss2json.com/v1/api.json?rss_url=https%3A%2F%2Fwww.bing.com%2Fnews%2Fsearch%3Fq%3D%2522Capital%2520One%2520Financial%2520Corporation%2522%2520COF%26format%3DRSS",
            "Freddie Mac": "https://api.rss2json.com/v1/api.json?rss_url=https%3A%2F%2Fwww.bing.com%2Fnews%2Fsearch%3Fq%3DFreddie%2520Mac%2520-%2520Federal%2520Home%2520Loan%2520Mortgage%2520Corporation%2520%2522FMCC%2522%26format%3DRSS",
            "Freddie Mac (SECOND FEED)": "https://api.rss2json.com/v1/api.json?rss_url=https%3A%2F%2Fwww.bing.com%2Fnews%2Fsearch%3Fq%3D%2522Freddie%2520Mac%2520-%2520Federal%2520Home%2520Loan%2520Mortgage%2520Corporation%2522%2520FMCC%26format%3DRSS",
            "Fannie Mae":  "https://api.rss2json.com/v1/api.json?rss_url=https%3A%2F%2Fwww.bing.com%2Fnews%2Fsearch%3Fq%3D%2522Federal%2520National%2520Mortgage%2520Association%2522%2520FNMA%26format%3DRSS",
            # Regulatory Feeds
            "OCC Bulletins": "https://www.occ.gov/rss/occ_bulletins.xml",
            "Federal Reserve Enforcement Actions": "https://www.federalreserve.gov/feeds/press_enforcement.xml"
        }
        self.api_targets = [
            "Capital One",
            "Fannie Mae",
            "Freddie Mac",
            "Navy Federal Credit Union",
            "PenFed Credit Union",
            "EagleBank",
            "Capital Bank N.A."
        ]
        self.default_rss_timezone = ZoneInfo("America/New_York")
        self.system_timezone = ZoneInfo("America/Los_Angeles")

    def _parse_rss_datetime(self, entry, field_name):
        """
        Parse datetime from RSS feed, with robust handling for XML and string formats.
        Returns timezone-aware datetime in system timezone, or None if cannot parse.
        """
        if not hasattr(entry, field_name) or not getattr(entry, field_name):
            return None
        parsed_time = getattr(entry, field_name)
        try:
            naive_dt = datetime(*parsed_time[:6])
            # Try to extract explicit timezone if provided in text field
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                original_date_str = getattr(entry, field_name.replace('_parsed', ''), '')
                if original_date_str:
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
                            aware_dt = naive_dt.replace(tzinfo=tz_info)
                            return aware_dt.astimezone(self.system_timezone)
            aware_dt = naive_dt.replace(tzinfo=self.default_rss_timezone)
            return aware_dt.astimezone(self.system_timezone)
        except Exception as e:
            logger.error(f"Error parsing RSS datetime: {e}", exc_info=True)
            return None

    def _parse_json_pubdate(self, pub_date_str):
        """
        Parse pubDate from JSON (rss2json) feeds robustly.
        """
        from email.utils import parsedate_to_datetime
        pub_date = None
        try:
            pub_date = parsedate_to_datetime(pub_date_str)
            if pub_date is not None:
                return pub_date.astimezone(self.system_timezone)
            # Fallback if parsedate_to_datetime returns None or error
        except Exception:
            try:
                pub_date = datetime.strptime(pub_date_str, "%Y-%m-%d %H:%M:%S")
                pub_date = pub_date.replace(tzinfo=ZoneInfo("UTC")).astimezone(self.system_timezone)
                return pub_date
            except Exception as e2:
                logger.warning(f"Couldn't parse pubDate '{pub_date_str}': {e2}")
                return None
        return pub_date

    def _get_system_datetime(self):
        """Get current datetime in system timezone."""
        return datetime.now(self.system_timezone)

    def _is_recent_article(self, pub_date, hours_back=168):
        """
        Check if article is within the specified time window.
        All datetimes should be timezone-aware and in the same timezone.
        Returns True if article is recent, False otherwise.
        """
        if not pub_date:
            return False
        if pub_date.tzinfo is None:
            logger.warning("Article has naive datetime, assuming system timezone")
            pub_date = pub_date.replace(tzinfo=self.system_timezone)
        now = self._get_system_datetime()
        cutoff = now - timedelta(hours=hours_back)
        is_recent = pub_date >= cutoff
        logger.info(f"{'Recent' if is_recent else 'Old'} article: {pub_date.strftime('%Y-%m-%d %H:%M %Z')} ({'within' if is_recent else 'older than'} {hours_back}h)")
        return is_recent

    def _is_relevant_to_target_companies(self, title, summary, source_name):
        """
        Check if a regulatory RSS article is relevant to our target companies.
        For regulatory feeds, checks if any target company is mentioned in title/summary.
        For company-specific feeds, always returns True.
        """
        if source_name in ["OCC Bulletins", "Federal Reserve Enforcement Actions"]:
            text_to_check = f"{title} {summary}".lower()
            return any(company.lower() in text_to_check for company in self.target_companies)
        return True

    def _identify_mentioned_company(self, title, summary):
        """
        Try to identify which target company is mentioned in a regulatory article.
        Returns canonical company name, or None if not found.
        """
        text_to_check = f"{title} {summary}".lower()
        for company in self.target_companies:
            if company.lower() in text_to_check:
                return company
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
        for variation, canon in company_variations.items():
            if variation in text_to_check:
                return canon
        return None

    def fetch_from_rss(self, hours_back=168):
        """
        Parses all known RSS feeds for recent articles.
        Handles both XML (regulator) and JSON (rss2json/Bing) feeds.
        """
        articles = []
        for source_name, url in self.rss_feeds.items():
            try:
                logger.info(f"Fetching RSS feed for {source_name}...")
                response = ethical_get(url, timeout=30)
                if response is None or response.status_code != 200:
                    logger.error(f"Blocked or failed to fetch RSS feed for {source_name}")
                    continue

                # JSON (rss2json) feeds
                if "api.rss2json.com" in url:
                    feed_articles_count = 0
                    data = response.json()
                    items = data.get("items", [])
                    for entry in items:
                        pub_date = None
                        pubdate_source = None
                        if entry.get("pubDate"):
                            pub_date = self._parse_json_pubdate(entry["pubDate"])
                        if pub_date and self._is_recent_article(pub_date, hours_back=hours_back):
                            summary = entry.get("description", "")
                            is_relevant = self._is_relevant_to_target_companies(entry.get("title", ""), summary, source_name)
                            if is_relevant:
                                company_mentioned = self._identify_mentioned_company(entry.get("title", ""), summary)
                                articles.append({
                                    'company': company_mentioned or source_name,
                                    'title': entry.get("title", ""),
                                    'link': entry.get("link", ""),
                                    'summary': summary,
                                    'published_date': pub_date.isoformat(),
                                    'source': 'RSS',
                                    'type': 'news',
                                    'data_type': 'news',
                                    'feed_source': source_name,
                                    'content_enhanced': False
                                })
                                feed_articles_count += 1
                    logger.info(f"Found {feed_articles_count} relevant articles from {source_name} (JSON feed)")
                else:
                    # Assume XML RSS handled by feedparser
                    feed = feedparser.parse(response.content)
                    feed_articles_count = 0
                    for entry in feed.entries:
                        pub_date = None
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            pub_date = self._parse_rss_datetime(entry, 'published_parsed')
                        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                            pub_date = self._parse_rss_datetime(entry, 'updated_parsed')
                        if pub_date and self._is_recent_article(pub_date, hours_back=hours_back):
                            summary = getattr(entry, 'summary', '')
                            if self._is_relevant_to_target_companies(getattr(entry, 'title', ''), summary, source_name):
                                company_mentioned = self._identify_mentioned_company(getattr(entry, 'title', ''), summary)
                                articles.append({
                                    'company': company_mentioned or source_name,
                                    'title': getattr(entry, 'title', ''),
                                    'link': getattr(entry, 'link', ''),
                                    'summary': summary,
                                    'published_date': pub_date.isoformat(),
                                    'source': 'RSS',
                                    'type': 'news',
                                    'data_type': 'news',
                                    'feed_source': source_name,
                                    'content_enhanced': False
                                })
                                feed_articles_count += 1
                    logger.info(f"Found {feed_articles_count} relevant articles from {source_name} (XML feed)")
            except Exception as e:
                logger.error(f"Error fetching RSS feed for {source_name}: {e}", exc_info=True)
        logger.info(f"Found {len(articles)} total recent articles from RSS feeds")
        return articles

    def fetch_from_gnews(self, hours_back=168):
        """
        Fetches news from GNews.io API for all API targets.
        Tries custom queries, then fallback simple queries if needed.
        Only recent articles (within hours_back) are included.
        """
        if not self.gnews_api_key:
            logger.warning("GNEWS_API_KEY not found. Skipping API news fetch.")
            return []
        articles = []
        base_url = "https://gnews.io/api/v4/search"
        logger.info("Fetching news from GNews.io API...")
        print(">>> Entering fetch_from_gnews ... Looping companies ...")
        for company in self.api_targets:
            # Try custom search query, then fallback to quoted company name
            query_variants = [
                self.custom_search_queries.get(company, f'"{company}"'),
                f'"{company}"'
            ]
            got_results = False
            for query in query_variants:
                try:
                    params = {
                        'q': query,
                        'lang': 'en',
                        'apikey': self.gnews_api_key,
                        'max': 2,
                        'sortby': 'publishedAt'
                    }
                    params_to_print = params.copy()
                    params_to_print['apikey'] = '***hidden***'
                    print(f"Calling GNews API for company: {company} with params: {params_to_print}")
                    response = ethical_get(base_url, params=params, timeout=30, skip_robots=True)
                    print(f"ETHICAL_GET RESPONSE status {getattr(response, 'status_code', None)} for {base_url} with params={params}")
                    print(f"-- Response object for {company} (query: {query}): {response}")
                    if response is None or getattr(response, 'status_code', 400) == 400:
                        print(f"Query '{query}' for {company} gave 400 or no response, trying next query if available.")
                        continue
                    elif response.status_code != 200:
                        logger.error(f"Blocked or received bad status code {response.status_code} from GNews API for {company}")
                        print(f"Blocked or received bad status code from GNews API for {company}")
                        break
                    data = response.json()
                    print(f"\n--- GNews API response for '{company}' (using query: {query}) ---")
                    print(data)
                    if 'errors' in data:
                        logger.error(f"GNews API error for '{company}': {data['errors']}")
                        print(f"GNews API returned an error for '{company}': {data['errors']}")
                        continue
                    company_articles_count = 0
                    for article in data.get("articles", []):
                        pub_date_str = article.get("publishedAt")
                        print(f"Article for '{company}': Title: {article.get('title')}, PublishedAt: {pub_date_str}")
                        if not pub_date_str:
                            print("No pub_date_str, skipping article")
                            continue
                        try:
                            utc_dt = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
                            pub_date_local = utc_dt.astimezone(self.system_timezone)
                            if self._is_recent_article(pub_date_local, hours_back=hours_back):
                                print(f"Accepted article for '{company}' with date {pub_date_local}")
                                articles.append({
                                    'company': company,
                                    'title': article.get("title", ""),
                                    'link': article.get("url", ""),
                                    'summary': article.get("description", ""),
                                    'published_date': pub_date_local.isoformat(),
                                    'source': 'GNews API',
                                    'type': 'news',
                                    'data_type': 'news',
                                    'feed_source': 'GNews API',
                                    'content_enhanced': False
                                })
                                company_articles_count += 1
                            else:
                                print(f"Rejected (old) article for '{company}' with date {pub_date_local}")
                        except Exception as e:
                            logger.warning(f"Invalid date for {company}: {e}")
                            print(f"Invalid date format in GNews response: {pub_date_str} - {e}")
                            continue
                    print(f"Found {company_articles_count} GNews articles for '{company}' (query: {query})\n")
                    logger.info(f"Found {company_articles_count} GNews articles for '{company}' (query: {query})")
                    got_results = True
                    break  # Success or partial results; don't try next query
                except requests.RequestException as e:
                    logger.error(f"Error fetching data from GNews API for {company}: {e}", exc_info=True)
                    print(f"Error fetching data from GNews API for {company}: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error in GNews fetch for {company}: {e}", exc_info=True)
                    print(f"Unexpected error in GNews fetch for {company}: {e}")
            if not got_results:
                print(f"No GNews results found for {company} after all query attempts.\n")
        logger.info(f"Found {len(articles)} total recent articles from GNews API")
        print(f"\n>>> FINISHED fetch_from_gnews. Total articles: {len(articles)}\n")
        return articles

    async def get_all_news(self, hours_back=168):
        """
        Combines news from both RSS and GNews sources and enhances with scraper (if present).
        Returns the combined/enhanced article list, adding verbose status logs for every article.
        """
        rss_articles = self.fetch_from_rss(hours_back=hours_back)
        api_articles = self.fetch_from_gnews(hours_back=hours_back)
        all_articles = rss_articles + api_articles
        logger.info(f"📰 Total news articles: {len(all_articles)} (last {hours_back} hours)")
        if self.scraper_agent and self.scraper_agent.is_available():
            logger.info("🔍 Enhancing articles with full content scraping via ScraperAgent...")
            enhanced_articles = []
            success_count = 0
            failure_count = 0
            for idx, article in enumerate(all_articles):
                url = article.get('link') or article.get('url')
                article_id = article.get('title', 'NO TITLE')[:60]
                if url:
                    try:
                        logger.info(f"➡️ [{idx+1}/{len(all_articles)}] Scraping full article: {article_id}\n    URL: {url}")
                        full_content = await self.scraper_agent.scrape_url(url, "news")
                        if full_content:
                            article['full_content'] = full_content
                            article['content_enhanced'] = True
                            logger.info(f"✅ Success: Extracted {len(full_content)} characters for '{article_id}'")
                            success_count += 1
                        else:
                            article['full_content'] = None
                            article['content_enhanced'] = False
                            logger.warning(f"⚠️  Failed: No content extracted for '{article_id}'")
                            failure_count += 1
                    except Exception as e:
                        article['full_content'] = None
                        article['content_enhanced'] = False
                        logger.error(f"❌ Exception scraping '{article_id}': {e}")
                        failure_count += 1
                else:
                    article['full_content'] = None
                    article['content_enhanced'] = False
                    logger.warning(f"⚠️  Skipping article without URL: '{article_id}'")
                    failure_count += 1
                enhanced_articles.append(article)
            logger.info(f"📊 Enhanced Articles: {success_count} succeeded, {failure_count} failed, out of {len(enhanced_articles)}")
            return enhanced_articles
        else:
            logger.warning("⚠️  ScraperAgent not available; returning original articles without full content")
        return all_articles