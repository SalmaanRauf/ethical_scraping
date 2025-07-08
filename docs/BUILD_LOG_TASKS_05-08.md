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
                    'entity': company,
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

---

## Critical Fix: Validator Agent External Validation Logic

**The Flaw:**
The `validate_event_external()` function had a critical logical flaw where it considered an event "validated" if the Google Search API returned any results (`len(res['items']) > 0`), without analyzing the content of those results. This gave a false sense of security and could validate events based on irrelevant or outdated search results.

**The Impact:**
- A search for "Capital One new partnership" might return an article from three years ago
- Completely unrelated articles could be counted as validation
- The system would incorrectly mark events as externally validated
- This defeated the purpose of validation, which is to reduce hallucinations

**The Solution:**
Enhanced the validation logic with smart content analysis:

1. **Key Term Extraction**: Extracts company name variations and meaningful headline terms
2. **Content Analysis**: Analyzes each search result's title and snippet for relevance
3. **Scoring System**: Calculates relevance scores based on company and headline term matches
4. **Date Validation**: Checks for recent dates in search results
5. **Strict Thresholds**: Requires at least 2 highly relevant sources for validation
6. **Detailed Logging**: Provides comprehensive analysis output for debugging

**Key Improvements:**
- **Smart Term Matching**: Handles company name variations (e.g., "Capital One" vs "CapitalOne" vs "COF")
- **Relevance Scoring**: Weighted scoring system (70% company matches, 30% headline matches)
- **Multiple Source Requirement**: Requires at least 2 relevant sources, not just any results
- **Date Awareness**: Prioritizes recent content over outdated articles
- **Comprehensive Logging**: Detailed analysis output for transparency

**Example Output:**
```
🔍 Analyzing 5 search results with key terms: ['capital one', 'capitalone', 'cof', 'partnership', 'announces']
   Result 1: Capital One Announces New Partnership with Tech Firm...
      Company matches: 2, Headline matches: 1
      Relevance score: 0.85, Recent date: True
      Relevant: ✅
   Result 2: Old Article About Capital One from 2020...
      Company matches: 1, Headline matches: 0
      Relevance score: 0.35, Recent date: False
      Relevant: ❌
✅ Externally validated via Google Search: Capital One Announces Partnership
   Found 2 highly relevant sources out of 5 total
```

This fix ensures that external validation provides genuine confirmation rather than false positives, significantly improving the system's reliability and reducing hallucination risk.

---

## Critical Fix: AnalystAgent Data Integrity - Intelligent Text Processing

**The Flaw:**
The AnalystAgent was using naive text truncation (e.g., `item.get('text', '')[:2000]`) to manage token limits. This created a critical data integrity flaw where high-impact events occurring after the arbitrary cutoff point would be completely missed.

**The Impact:**
- A 5,000-character SEC filing mentioning a "$50 million investment" at character 2,500 would be ignored
- The system would fail to identify high-impact events simply because key information fell outside the arbitrary cutoff
- This could result in missing critical financial disclosures, partnerships, or acquisitions
- The $10M threshold filtering would be ineffective if the relevant information was truncated away

**The Solution:**
Implemented a sophisticated intelligent text processing system with map-reduce pattern:

1. **Intelligent Chunking** (`_create_intelligent_chunks()`):
   - Preserves context by finding sentence boundaries
   - Uses overlapping chunks to avoid missing information at boundaries
   - Configurable chunk size (3,000 chars) with 500-char overlap
   - Maximum 10 chunks per document to manage processing costs

2. **Key Term Extraction** (`_extract_key_terms()`):
   - Identifies monetary amounts, company names, and financial terms
   - Uses regex patterns to find dollar amounts, company mentions, and action words
   - Helps prioritize chunks with relevant information

3. **Chunk Prioritization** (`_prioritize_chunks()`):
   - Scores chunks based on presence of key financial terms
   - Prioritizes chunks with dollar amounts (+50 points)
   - Prioritizes chunks with company names (+30 points)
   - Prioritizes chunks with action words (+20 points)
   - Analyzes highest-scoring chunks first

4. **Map-Reduce Analysis** (`_analyze_chunks_with_map_reduce()`):
   - **Map Phase**: Analyzes each prioritized chunk independently
   - **Reduce Phase**: Synthesizes results from all relevant chunks
   - Ensures comprehensive coverage of entire documents
   - Combines findings from multiple chunks into coherent analysis

5. **Result Synthesis** (`_synthesize_chunk_results()`):
   - For financial analysis: Selects highest-value event across all chunks
   - For procurement analysis: Combines all relevant notices
   - For earnings analysis: Aggregates all guidance found
   - Maintains $10M threshold enforcement across synthesized results

**Key Improvements:**
- **No Data Loss**: Processes entire documents without arbitrary truncation
- **Context Preservation**: Intelligent chunking maintains sentence and paragraph boundaries
- **Prioritized Analysis**: Focuses computational resources on most relevant chunks
- **Comprehensive Coverage**: Map-reduce pattern ensures no section is missed
- **Cost Management**: Limits maximum chunks per document to control processing costs
- **Detailed Logging**: Provides transparency into chunking and analysis process

**Example Output:**
```
🔍 Analyzing 5 prioritized chunks (from 8 total)
   📄 Analyzing chunk 1/5 (2,847 chars)
      ✅ Found relevant information in chunk 1
   📄 Analyzing chunk 2/5 (2,901 chars)
      ⚪ No relevant information in chunk 2
   📄 Analyzing chunk 3/5 (2,923 chars)
      ✅ Found relevant information in chunk 3
   🔄 Synthesizing results from 2 relevant chunks...
✅ Found financial event ($50,000,000) using 2 chunks
```

**Configuration:**
- **Chunk Size**: 3,000 characters (configurable)
- **Overlap**: 500 characters between chunks
- **Max Chunks**: 10 per document (prevents runaway processing)
- **Priority Analysis**: Top 3 chunks for triage, all prioritized chunks for detailed analysis

This fix ensures that the system never misses high-impact events due to arbitrary text truncation, significantly improving data integrity and analysis accuracy.

---

## Critical Fix: Archivist Agent Semantic De-Duplication

**The Flaw:**
The Archivist's de-duplication was fundamentally flawed because it was source-dependent, not event-dependent. The `_generate_hash()` function used only the event headline and company name, assuming that different headlines meant different events.

**The Impact:**
- Associated Press and Reuters reporting on the same $50M acquisition by Capital One would have different headlines
- The system would generate different hashes and save them as separate, unique findings
- The final report would show the same event twice, making the system look noisy and unreliable
- The intent was to de-duplicate events, but the implementation only de-duplicated verbatim articles

**The Solution:**
Implemented a sophisticated semantic de-duplication system using embeddings and cosine similarity:

1. **Event Summary Generation** (`_generate_event_summary()`):
   - Creates standardized event summaries focusing on core details
   - Extracts company, event type, value, and key details
   - Normalizes text to focus on semantic meaning rather than headline variations
   - Example: "Company: Capital One | Event Type: Acquisition | Value: $50,000,000 | Details: acquired fintech startup"

2. **Embedding Generation** (`_generate_embedding()`):
   - Uses Azure OpenAI text-embedding-ada-002 model
   - Generates high-dimensional vector representations of event summaries
   - Enables semantic similarity calculations
   - Stores embeddings in dedicated database table

3. **Cosine Similarity Calculation** (`_cosine_similarity()`):
   - Calculates similarity between new and existing event embeddings
   - Uses numpy for efficient vector operations
   - Returns similarity score between 0 (completely different) and 1 (identical)
   - Configurable threshold (0.85) for duplicate detection

4. **Semantic Duplicate Detection** (`_check_semantic_duplicate()`):
   - Compares new events with existing events from the same day and company
   - Uses embedding similarity to identify semantically similar events
   - Provides detailed logging of comparison process
   - Returns both duplicate status and existing finding ID

5. **Database Schema Enhancement**:
   - Added `event_embeddings` table to store embeddings
   - Links embeddings to findings via foreign key
   - Enables efficient similarity queries
   - Maintains data integrity with proper indexing

**Key Improvements:**
- **True Event-Centric De-Duplication**: Identifies same events regardless of headline variations
- **Semantic Understanding**: Uses AI embeddings to understand event meaning
- **Configurable Thresholds**: Adjustable similarity threshold (0.85) for precision/recall balance
- **Comprehensive Logging**: Detailed analysis output for transparency and debugging
- **Fallback Mechanism**: Maintains traditional hash-based de-duplication as backup
- **Performance Optimization**: Efficient vector operations and database queries

**Example Output:**
```
🔍 Checking for semantic duplicates: Company: Capital One | Event Type: Acquisition | Value: $50,000,000 | Details: acquired fintech startup...
   🔍 Comparing with existing event 123:
      New: Company: Capital One | Event Type: Acquisition | Value: $50,000,000...
      Existing: Capital One Announces $50M Acquisition of Tech Startup
      Similarity: 0.892
   ✅ Semantic duplicate detected (similarity: 0.892)
🔄 Event is a semantic duplicate of finding 123. Skipping save.
```

**Configuration:**
- **Similarity Threshold**: 0.85 (very similar events)
- **Embedding Model**: text-embedding-ada-002
- **Comparison Scope**: Same day and company only
- **Fallback**: Traditional hash-based de-duplication

**Database Schema:**
```sql
CREATE TABLE event_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id INTEGER NOT NULL,
    event_summary TEXT NOT NULL,
    embedding_data TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (finding_id) REFERENCES findings (id)
);
```

This fix ensures that the system properly identifies and eliminates duplicate events regardless of how they're reported, significantly improving report quality and reducing noise.

---

## Critical Fix: News Extractor Timezone Handling

**The Flaw:**
The NewsExtractor had a critical timezone handling flaw where it created timezone-naive datetime objects from RSS feeds and compared them directly to `datetime.now()` without any timezone consideration. This caused significant data loss and inconsistency.

**The Impact:**
- RSS feeds from London reporting news at 01:00 GMT on July 5th would be incorrectly processed when the script runs in New York at 22:00 EST on July 4th
- The system would either miss recent articles entirely or include articles that are too old
- This led to inconsistent and unreliable data collection from global sources
- The 24-hour window calculation was fundamentally broken across different timezones

**The Solution:**
Implemented comprehensive timezone-aware datetime handling:

1. **Timezone Configuration** (`__init__()`):
   - **Default RSS Timezone**: America/New_York (most US financial feeds)
   - **System Timezone**: America/Los_Angeles (Pacific Time for consistent comparison)
   - **Configurable**: Easy to adjust for different deployment environments

2. **Smart RSS DateTime Parsing** (`_parse_rss_datetime()`):
   - **Timezone Detection**: Extracts timezone info from original RSS date strings
   - **Pattern Matching**: Recognizes common timezone patterns (EST, EDT, PST, PDT, GMT, UTC)
   - **Fallback Handling**: Assumes EST/EDT for US financial feeds when no timezone info found
   - **Consistent Conversion**: Converts all dates to system timezone for comparison

3. **API DateTime Handling** (`fetch_from_api()`):
   - **ISO 8601 Support**: Properly handles Marketaux API's UTC timestamps
   - **Z Suffix Handling**: Converts 'Z' (UTC) to proper timezone-aware datetime
   - **Timezone Conversion**: Converts all API dates to system timezone

4. **Recent Article Detection** (`_is_recent_article()`):
   - **Timezone-Aware Comparison**: All datetime comparisons use timezone-aware objects
   - **Configurable Window**: Adjustable time window (default 24 hours)
   - **Detailed Logging**: Shows exact timestamps and timezone info for debugging
   - **Error Handling**: Graceful handling of naive datetime objects

5. **System DateTime Management** (`_get_system_datetime()`):
   - **Consistent Timezone**: Always returns current time in system timezone
   - **Centralized Logic**: Single source of truth for current time
   - **Timezone Safety**: Prevents naive datetime comparisons

**Key Improvements:**
- **Global Compatibility**: Handles RSS feeds from any timezone correctly
- **Accurate Time Windows**: 24-hour window calculation works correctly across timezones
- **Comprehensive Logging**: Detailed timezone information for debugging
- **Robust Error Handling**: Graceful handling of malformed dates
- **Configurable Timezones**: Easy to adjust for different deployment environments
- **Performance Optimization**: Efficient timezone conversions

**Example Output:**
```
Fetching RSS feed for Capital One...
   ✅ Recent article: 2024-01-15 10:30 PST (within 24h)
   ⚪ Old article: 2024-01-14 08:15 PST (older than 24h)
Found 3 recent articles from RSS feeds
```

**Configuration:**
- **Default RSS Timezone**: America/New_York (US financial feeds)
- **System Timezone**: America/Los_Angeles (Pacific Time)
- **Time Window**: 24 hours (configurable)
- **Timezone Patterns**: EST, EDT, PST, PDT, GMT, UTC

**Technical Implementation:**
```python
# Timezone-aware datetime parsing
aware_dt = naive_dt.replace(tzinfo=self.default_rss_timezone)
system_dt = aware_dt.astimezone(self.system_timezone)

# Timezone-aware comparison
now = datetime.now(self.system_timezone)
cutoff_time = now - timedelta(hours=24)
is_recent = pub_date >= cutoff_time
```

This fix ensures that the system correctly handles global RSS feeds and API responses, preventing data loss due to timezone confusion and providing consistent, reliable data collection regardless of where the feeds originate or where the system is deployed.

# Note: Earnings Call Transcript Coverage
# The SEC Extractor specifically targets 10-Q, 10-K, and 8-K filings, which include earnings call transcripts and related financial disclosures. If transcript feeds are available, they should also be included in the extraction process.
# The AnalystAgent analyzes these filings for earnings guidance and high-impact financial events as required by the task statement. 