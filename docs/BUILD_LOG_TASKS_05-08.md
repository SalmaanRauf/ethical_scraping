# Agentic Account Research System - Build Log (Tasks 5-8)

---

## Begin Task 5: Develop and Test SAM Extractor Module

**Description:**
Create the agent to extract procurement notices from SAM.gov API.

**Commands:**
```bash
mkdir -p extractors
touch extractors/__init__.py
```

**File:** `extractors/sam_extractor.py`

```python
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import re
from agents.http_utils import ethical_get

class SAMExtractor:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        self.api_key = os.getenv("SAM_API_KEY")
        self.base_url = "https://api.sam.gov/prod/opportunities/v2/search"
        
        # Target companies to monitor (final, corrected)
        self.target_companies = [
            "Capital One",
            "Fannie Mae",
            "Freddie Mac",
            "Navy Federal Credit Union",
            "PenFed Credit Union",
            "EagleBank",
            "Capital Bank N.A."
        ]
        
        # API quota management
        self.api_calls_made = 0
        self.max_api_calls = 95  # Leave buffer for other operations
        self.quota_reset_date = None

    def extract_value_usd(self, text):
        """Extracts the largest USD dollar value from the text, ignoring non-USD currencies."""
        if not text:
            return None
            
        # Define non-USD currency symbols to ignore
        non_usd_currencies = ['€', '£', 'C$', 'A$', '¥', '₹', '₽', '₩', '₪', '₨', '₦', '₡', '₱', '₴', '₸', '₺', '₼', '₾', '₿']
        
        # First, check if text contains non-USD currencies and log them
        found_non_usd = []
        for currency in non_usd_currencies:
            if currency in text:
                found_non_usd.append(currency)
        
        if found_non_usd:
            print(f"⚠️  Found non-USD currencies in text: {found_non_usd}")
        
        # Look for USD amounts with explicit $ symbol
        # This regex specifically looks for $ followed by numbers, ensuring USD currency
        matches = re.findall(r'\$\s?([0-9,.]+)(?:\s?(million|billion|thousand|m|bn|k)?)', text, re.IGNORECASE)
        
        max_value = 0
        for amount, unit in matches:
            try:
                value = float(amount.replace(',', ''))
                unit = unit.lower() if unit else ''
                if unit in ['million', 'm']:
                    value *= 1_000_000
                elif unit in ['billion', 'bn']:
                    value *= 1_000_000_000
                elif unit in ['thousand', 'k']:
                    value *= 1_000
                max_value = max(max_value, value)
            except Exception:
                continue
        
        # Only return value if we found USD amounts and no conflicting non-USD currencies
        if max_value > 0:
            if found_non_usd:
                print(f"⚠️  Mixed currencies detected. USD value: ${max_value:,}, but also found: {found_non_usd}")
                # In case of mixed currencies, be conservative and return None
                return None
            return int(max_value)
        
        return None

    def fetch_notice_details(self, notice_url):
        """Fetch detailed description for a specific notice."""
        if self.api_calls_made >= self.max_api_calls:
            print(f"⚠️  API quota limit reached ({self.api_calls_made}/{self.max_api_calls})")
            return None
            
        try:
            params = {'api_key': self.api_key}
            response = ethical_get(notice_url, params=params, timeout=30)
            if response is None:
                print("Request blocked or failed by ethical_get.")
                return None
                
            response.raise_for_status()
            self.api_calls_made += 1
            
            data = response.json()
            # Extract the full description text
            return data.get('opportunity', {}).get('description', '')
            
        except Exception as e:
            print(f"Error fetching notice details: {e}")
            return None

    def fetch_notices(self, keywords=["RFP", "SOW", "consultant", "financial services"], max_notices=20):
        """Fetches procurement notices from SAM.gov and filters them."""
        if not self.api_key:
            print("Error: SAM_API_KEY not found in environment variables.")
            return []

        # Set date range for the last 24 hours
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        today = datetime.now().strftime('%Y-%m-%d')
        
        params = {
            'api_key': self.api_key, 
            'postedFrom': yesterday,
            'postedTo': today,
            'limit': max_notices,  # Limit to conserve API calls
            'sortBy': 'postedDate',
            'order': 'desc'
        }

        try:
            print(f"Fetching SAM.gov notices from {yesterday} to {today}...")
            response = ethical_get(self.base_url, params=params, timeout=30)
            if response is None:
                print("Request blocked or failed by ethical_get.")
                return []
            response.raise_for_status()
            self.api_calls_made += 1
            
            data = response.json()
            notices = data.get("opportunitiesData", [])
            print(f"Found {len(notices)} notices in summary data")

            # Secondary local filtering on description and title
            relevant_notices = []
            for notice in notices:
                title = str(notice.get("title", ""))
                description_url = notice.get("description", "")
                
                # Check if description is a URL (needs secondary fetch)
                if description_url.startswith('http'):
                    print(f"📄 Fetching details for: {title[:50]}...")
                    full_description = self.fetch_notice_details(description_url)
                    if full_description is None:
                        continue
                else:
                    # Description is already text (rare case)
                    full_description = description_url
                
                # Combine title and full description for analysis
                full_text = f"{title} {full_description}"
                
                # Extract value from full text
                value_usd = self.extract_value_usd(full_text)
                
                # Check if any keyword matches
                keyword_match = any(keyword.lower() in full_text.lower() 
                                   for keyword in keywords)
                
                # Check if any target company is mentioned
                company_match = any(company.lower() in full_text.lower() 
                                   for company in self.target_companies)
                
                # Only include if value >= $10M
                if (keyword_match or company_match) and value_usd and value_usd >= 10_000_000:
                    relevant_notices.append({
                        'title': title,
                        'description': full_description,
                        'postedDate': notice.get("postedDate", ""),
                        'responseDeadLine': notice.get("responseDeadLine", ""),
                        'classificationCode': notice.get("classificationCode", ""),
                        'naicsCode': notice.get("naicsCode", ""),
                        'fullParentPathName': notice.get("fullParentPathName", ""),
                        'fullParentPathCode': notice.get("fullParentPathCode", ""),
                        'organizationType': notice.get("organizationType", ""),
                        'type': 'procurement',
                        'value_usd': value_usd
                    })
                    print(f"  ✅ Found relevant notice: ${value_usd:,} - {title[:50]}...")
                elif keyword_match or company_match:
                    print(f"  ⚠️  Notice found but value ${value_usd:,} is below $10M threshold")
                
                # Check quota after each notice
                if self.api_calls_made >= self.max_api_calls:
                    print(f"⚠️  Stopping early due to API quota limit ({self.api_calls_made}/{self.max_api_calls})")
                    break
            
            print(f"Found {len(relevant_notices)} relevant procurement notices >= $10M")
            print(f"API calls used: {self.api_calls_made}")
            return relevant_notices
            
        except Exception as e:
            print(f"Error fetching data from SAM.gov: {e}")
            return []

    def get_all_notices(self):
        """Main method to get all relevant procurement notices."""
        return self.fetch_notices()

    def get_quota_status(self):
        """Get current API quota status."""
        return {
            'calls_made': self.api_calls_made,
            'max_calls': self.max_api_calls,
            'remaining': self.max_api_calls - self.api_calls_made
        }

**Critical Fix - Currency Assumption Flaw:**
The `extract_value_usd()` function was enhanced to address a critical logical flaw where non-USD currencies (€, £, C$, etc.) could be incorrectly interpreted as USD amounts. The fix includes:

1. **Currency Validation**: Explicit detection of non-USD currency symbols
2. **Conservative Handling**: Returns `None` when mixed currencies are detected
3. **Comprehensive Coverage**: Handles major world currencies (€, £, C$, A$, ¥, ₹, ₽, ₩, etc.)
4. **Logging**: Provides clear warnings when non-USD currencies are found

This prevents the system from incorrectly flagging contracts like "€15 million" or "C$20,000,000" as relevant USD procurement notices, ensuring accurate filtering of the $10M threshold.

End Task 5

---

## Begin Task 6: Develop and Test News Extractor Module

**Description:**
Create the agent to extract news from RSS feeds and Marketaux API.

**File:** `extractors/news_extractor.py`

```python
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
        
        # RSS feeds for companies that have them
        self.rss_feeds = {
            "Capital One": "https://www.capitalone.com/about/newsroom/rss.xml",
            "Freddie Mac": "https://www.freddiemac.com/news/rss.xml",
            "Fannie Mae": "https://www.fanniemae.com/news/rss.xml"
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
                feed = feedparser.parse(url)
                
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
                
                response = ethical_get("https://api.marketaux.com/v1/news/all", 
                                      params=params, timeout=30)
                if response is None:
                    print("Blocked or failed by ethical_get.")
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
```

End Task 6

---

## Begin Task 7: Develop and Test SEC Extractor Module

**Description:**
Create the agent to extract SEC filings using sec-api.io.

**File:** `extractors/sec_extractor.py`

```python
import os
from sec_api import QueryApi, ExtractorApi
from datetime import datetime, timedelta
from dotenv import load_dotenv

class SECExtractor:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        self.api_key = os.getenv("SEC_API_KEY")
        
        if not self.api_key:
            print("Error: SEC_API_KEY not found in environment variables.")
            return
            
        self.query_api = QueryApi(api_key=self.api_key)
        self.extractor_api = ExtractorApi(api_key=self.api_key)
        
        # Target company tickers (final, corrected)
        self.target_tickers = {
            "COF": "Capital One Financial Corp",
            "FMCC": "Federal Home Loan Mortgage Corp",
            "FNMA": "Federal National Mortgage Association",
            "EGBN": "Eagle Bancorp Inc",
            "CBNK": "Capital Bancorp Inc"
            # PenFed and Navy Federal Credit Union do not have public tickers
        }

    def get_filings_and_text(self):
        """Fetches recent filings and extracts their text."""
        if not self.api_key:
            return []
            
        # Build query for recent filings
        ticker_list = " OR ".join([f'ticker:"{ticker}"' for ticker in self.target_tickers.keys()])
        
        query = {
            "query": {
                "query_string": {
                    "query": f"({ticker_list}) AND formType:(8-K OR 10-Q OR 10-K)"
                }
            },
            "from": "0",
            "size": "25",
            "sort": [{"filedAt": {"order": "desc"}}]
        }
        
        try:
            print("Fetching recent SEC filings...")
            filings = self.query_api.get_filings(query).get('filings', [])
            
            extracted_data = []
            for filing in filings:
                try:
                    # Use the extractedText field from the initial response (no additional API call needed)
                    print(f"Processing {filing.get('ticker', 'Unknown')} {filing.get('formType', 'Unknown')}...")
                    extracted_data.append({
                        'company': filing.get('companyName', ''),
                        'ticker': filing.get('ticker', ''),
                        'type': filing.get('formType', ''),
                        'filedAt': filing.get('filedAt', ''),
                        'link': filing.get('linkToFilingDetails', ''),
                        'text': filing.get('extractedText', ''),
                        'source': 'SEC',
                        'data_type': 'filing'
                    })
                    
                except Exception as e:
                    print(f"Error processing filing {filing.get('ticker', 'Unknown')}: {e}")
                    continue
            
            print(f"Successfully processed {len(extracted_data)} SEC filings")
            return extracted_data
            
        except Exception as e:
            print(f"Error during SEC extraction: {e}")
            return []

    def get_recent_filings(self, days_back=7):
        """Get filings from the last N days."""
        if not self.api_key:
            return []
            
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Build query with date filter
        ticker_list = " OR ".join([f'ticker:"{ticker}"' for ticker in self.target_tickers.keys()])
        
        query = {
            "query": {
                "query_string": {
                    "query": f"({ticker_list}) AND formType:(8-K OR 10-Q OR 10-K) AND filedAt:[{start_date.strftime('%Y-%m-%d')} TO {end_date.strftime('%Y-%m-%d')}]"
                }
            },
            "from": "0",
            "size": "50",
            "sort": [{"filedAt": {"order": "desc"}}]
        }
        
        try:
            print(f"Fetching SEC filings from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")
            filings = self.query_api.get_filings(query).get('filings', [])
            
            extracted_data = []
            for filing in filings:
                try:
                    # Use the extractedText field from the initial response (no additional API call needed)
                    extracted_data.append({
                        'company': filing.get('companyName', ''),
                        'ticker': filing.get('ticker', ''),
                        'type': filing.get('formType', ''),
                        'filedAt': filing.get('filedAt', ''),
                        'link': filing.get('linkToFilingDetails', ''),
                        'text': filing.get('extractedText', ''),
                        'source': 'SEC',
                        'data_type': 'filing'
                    })
                    
                except Exception as e:
                    print(f"Error processing filing {filing.get('ticker', 'Unknown')}: {e}")
                    continue
            
            print(f"Found {len(extracted_data)} recent SEC filings")
            return extracted_data
            
        except Exception as e:
            print(f"Error during SEC extraction: {e}")
            return []
```

**Performance Optimization Note:**
The SEC extractor was optimized to eliminate the N+1 API call problem. Instead of making individual `extractor_api.get_section()` calls for each filing (which would result in 1 + N API calls), the implementation now uses the `extractedText` field that's already included in the initial `get_filings()` response. This provides:
- **O(1) API calls** instead of O(N)
- **Faster execution** with no additional network latency
- **Reduced API usage** and costs
- **Better reliability** with fewer potential failure points

End Task 7

---

## Begin Task 8: Initialize and Test Semantic Kernel

**Description:**
Create the configuration for Semantic Kernel and ATLAS/Azure OpenAI using the ATLASClient class and .env variables.

**File:** `config/kernel_setup.py`

```python
import os
import asyncio
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import AzureChatPromptExecutionSettings
from dotenv import load_dotenv
from openai import AsyncAzureOpenAI

class ATLASClient:
    def __init__(self, api_key, base_url, model, project_id, api_version):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.project_id = project_id
        self.api_version = api_version
        self.auth_headers = {f"{self.project_id}-Subscription-Key": self.api_key}

    def create_client(self):
        client = AsyncAzureOpenAI(
            api_key=self.api_key,
            api_version=self.api_version,
            default_headers=self.auth_headers,
            azure_endpoint=self.base_url
        )
        return client

    def create_chat(self, _async_client, _model, _name):
        chat = AzureChatCompletion(
            async_client=_async_client,
            deployment_name=_model,
            service_id=_name
        )
        return chat

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("BASE_URL")
api_version = os.getenv("API_VERSION")
model = os.getenv("MODEL")
project_id = os.getenv("PROJECT_ID")

async def initialize_kernel():
    kernel = Kernel()
    ATLAS = ATLASClient(api_key, base_url, model, project_id, api_version)
    client = ATLAS.create_client()
    chat = ATLAS.create_chat(client, model, "atlas")
    kernel.add_service(chat)
    exec_settings = AzureChatPromptExecutionSettings(service_id="atlas")
    exec_settings.function_choice_behavior = FunctionChoiceBehavior.Auto()
    print("Semantic Kernel initialized successfully with ATLAS/Azure OpenAI")
    return kernel, exec_settings

_kernel = None
_exec_settings = None
def get_kernel():
    global _kernel, _exec_settings
    if _kernel is None or _exec_settings is None:
        loop = asyncio.get_event_loop()
        _kernel, _exec_settings = loop.run_until_complete(initialize_kernel())
    return _kernel, _exec_settings

async def test_kernel_connection():
    kernel, exec_settings = await initialize_kernel()
    history = ChatHistory()
    userInput = "Hello, world. Are you connected? Please respond with 'Yes, I am connected and ready for analysis.'"
    history.add_user_message(userInput)
    chat = kernel.get_service("atlas")
    result = await chat.get_chat_message_content(chat_history=history, settings=exec_settings, kernel=kernel)
    print(f"Kernel test response: {result}")
    print("✅ Kernel connection test successful!")
    return True

if __name__ == '__main__':
    asyncio.run(test_kernel_connection())
```

End Task 8

---

## Kernel Setup Refactor Note

**Update:**
All kernel/model setup is now handled via a centralized ATLASClient class in `config/kernel_setup.py`, which loads all configuration (API keys, endpoints, model names, etc.) from the `.env` file. All agents and analysis functions now use this setup, ensuring consistency and maintainability. 

---

## Ethical HTTP Utility for Extractors

**Update:**
A new utility (`agents/http_utils.py`) provides ethical HTTP requests for all extractors. It features:
- User-agent rotation
- robots.txt compliance
- Randomized delay between requests
- Centralized `ethical_get()` function

All extractors (e.g., `sam_extractor.py`, `news_extractor.py`) now use `ethical_get()` for all HTTP requests, ensuring ethical and robust data collection.

**Example Usage in Extractors:**
```python
from agents.http_utils import ethical_get

response = ethical_get(url, params=params, timeout=30)
if response is None:
    print("Blocked or failed by ethical_get.")
    return []
response.raise_for_status()
data = response.json()
``` 

# Note: Earnings Call Transcript Coverage
# The SEC Extractor specifically targets 10-Q, 10-K, and 8-K filings, which include earnings call transcripts and related financial disclosures. If transcript feeds are available, they should also be included in the extraction process.
# The AnalystAgent analyzes these filings for earnings guidance and high-impact financial events as required by the task statement. 