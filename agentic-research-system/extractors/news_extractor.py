import os
import requests
import feedparser
from datetime import datetime, timedelta
from dotenv import load_dotenv
from agents.http_utils import ethical_get

class NewsExtractor:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        self.marketaux_api_key = os.getenv("MARKETAUX_API_KEY")
        
        # RSS feeds for companies that have them (update as needed)
        self.rss_feeds = {
            "Capital One": "https://www.capitalone.com/about/newsroom/rss.xml",
            "Truist": "https://www.truist.com/news/rss.xml",
            "Freddie Mac": "https://www.freddiemac.com/news/rss.xml",
            "Fannie Mae": "https://www.fanniemae.com/news/rss.xml",
            # Add RSS feeds for EagleBank and Capital Bank N.A. if available
        }
        
        # Companies to search via API (those without RSS feeds)
        self.api_targets = [
            "Navy Federal Credit Union", "PenFed Credit Union", "EagleBank", "Capital Bank N.A."
        ]
        
        # Target companies for filtering
        self.target_companies = [
            "Capital One", "Fannie Mae", "Freddie Mac", "Navy Federal Credit Union", "PenFed Credit Union", "EagleBank", "Capital Bank N.A."
        ]

    def fetch_from_rss(self):
        """Parses all known RSS feeds."""
        articles = []
        for company, url in self.rss_feeds.items():
            try:
                print(f"Fetching RSS feed for {company}...")
                response = ethical_get(url, timeout=30)
                if response is None or response.status_code != 200:
                    print(f"Blocked or failed to fetch RSS feed for {company}")
                    continue
                feed = feedparser.parse(response.content)
                
                # Filter for recent articles (last 24 hours)
                yesterday = datetime.now() - timedelta(days=1)
                
                for entry in feed.entries:
                    # Parse the publication date
                    pub_date = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_date = datetime(*entry.published_parsed[:6])
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        pub_date = datetime(*entry.updated_parsed[:6])
                    
                    # Only include recent articles
                    if pub_date and pub_date >= yesterday:
                        articles.append({
                            'company': company,
                            'title': entry.title,
                            'link': entry.link,
                            'summary': entry.summary if hasattr(entry, 'summary') else '',
                            'published_date': pub_date.isoformat() if pub_date else '',
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
                    'entities': company,
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
                
                # Filter for recent articles (last 24 hours)
                yesterday = datetime.now() - timedelta(days=1)
                
                for article in data.get("data", []):
                    pub_date_str = article.get("published_at", "")
                    if pub_date_str:
                        try:
                            pub_date = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
                            if pub_date >= yesterday:
                                articles.append({
                                    'company': company,
                                    'title': article.get("title", ""),
                                    'link': article.get("url", ""),
                                    'summary': article.get("description", ""),
                                    'published_date': pub_date.isoformat(),
                                    'source': 'Marketaux API',
                                    'type': 'news'
                                })
                        except ValueError:
                            # Skip articles with invalid dates
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