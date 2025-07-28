import asyncio
import re
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
from bs4 import BeautifulSoup
from agents.scraper_agent import ScraperAgent
from config.config import AppConfig
from services.error_handler import log_error
from extractors.http_utils import safe_async_get
from services.profile_loader import ProfileLoader

# Set up developer logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class SAMExtractor:
    """
    Extracts procurement notices from SAM.gov using a hybrid approach.
    It first attempts to use the official SAM.gov API. If the API fails or
    provides insufficient data, it falls back to web scraping. It then enhances
    all found notices by scraping their full detail pages.
    """
    def __init__(self, scraper_agent: ScraperAgent, profile_loader: ProfileLoader):
        self.scraper = scraper_agent
        self.api_key = AppConfig.SAM_API_KEY
        self.base_url = "https://api.sam.gov/prod/opportunities/v2/search"
        self.keywords = AppConfig.SAM_KEYWORDS
        self.profile_loader = profile_loader
        # Use lazy loading instead of loading profiles in constructor
        self._company_profiles = None

        # API quota management with rate limiting
        self.api_calls_made = 0
        self.max_api_calls = 3  # Reduced from 5 to 3 to stay under daily limit
        self.last_api_call = 0
        self.min_call_interval = 2  # Minimum 2 seconds between API calls
        
        # Financial institution specific keywords for better filtering
        self.financial_keywords = [
            "financial", "banking", "credit", "lending", "mortgage", "insurance",
            "investment", "securities", "compliance", "regulatory", "audit",
            "risk management", "cybersecurity", "data security", "fraud",
            "anti-money laundering", "aml", "kyc", "know your customer",
            "banking software", "financial technology", "fintech",
            "core banking", "payment processing", "card processing",
            "loan servicing", "mortgage servicing", "credit card",
            "debit card", "atm", "online banking", "mobile banking",
            "digital banking", "wealth management", "asset management",
            "trust services", "custody", "clearing", "settlement"
        ]

        logger.info("🔍 SAMExtractor initialized")
        logger.info("🔑 SAM API key configured: %s", "Yes" if self.api_key else "No")
        logger.info("⏱️  Rate limiting: %d calls max, %d seconds between calls", self.max_api_calls, self.min_call_interval)

    @property
    def company_profiles(self):
        """Lazy load company profiles when first accessed."""
        if self._company_profiles is None:
            self._company_profiles = self.profile_loader.load_profiles()
        return self._company_profiles

    async def get_all_notices(self, days_back: int = None) -> List[Dict[str, Any]]:
        """
        Fetches all recent notices and enhances them with full content.
        """
        if days_back is None:
            days_back = AppConfig.SAM_DAYS_BACK
        
        logger.info("📋 Starting SAM.gov extraction (days_back: %d)", days_back)
        
        # API-First Approach
        notice_summaries = await self._fetch_notices_from_api(days_back)
        logger.info("📊 SAM API returned %d notices", len(notice_summaries))

        # Scraper-Fallback Approach
        if not notice_summaries:
            logger.warning("⚠️  SAM.gov API failed or returned no results, falling back to scraper")
            notice_summaries = await self._fetch_notices_from_scraper()
            logger.info("📊 SAM scraper returned %d notices", len(notice_summaries))

        if not notice_summaries:
            logger.warning("⚠️  No SAM.gov notices found")
            return []

        # Graceful Scraper Enhancement
        logger.info("🔍 Enhancing %d notices with full content", len(notice_summaries))
        enhancement_tasks = [self._gracefully_enhance_notice(notice) for notice in notice_summaries]
        enhanced_notices = await asyncio.gather(*enhancement_tasks)
        
        # Apply business logic filters after enhancement
        filtered_notices = self._apply_business_filters(enhanced_notices)
        logger.info("✅ SAM extraction complete: %d filtered notices", len(filtered_notices))
        
        return [notice for notice in filtered_notices if notice] # Filter out any None results

    async def _fetch_notices_from_api(self, days_back: int) -> List[Dict[str, Any]]:
        """API-FIRST: Tries to fetch notice summaries from the official SAM.gov API."""
        if not self.api_key:
            logger.warning("⚠️  SAM.gov API key not configured")
            return []
        
        if self.api_calls_made >= self.max_api_calls:
            logger.error("❌ SAM.gov API quota limit reached (%d/%d)", self.api_calls_made, self.max_api_calls)
            return []

        # Rate limiting: ensure minimum time between API calls
        current_time = time.time()
        time_since_last_call = current_time - self.last_api_call
        if time_since_last_call < self.min_call_interval:
            sleep_time = self.min_call_interval - time_since_last_call
            logger.info(f"⏱️  Rate limiting: waiting {sleep_time:.1f} seconds before API call")
            await asyncio.sleep(sleep_time)

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        # More conservative parameters to avoid 400 errors
        # Use date format from original version: MM/DD/YYYY
        yesterday = (start_date).strftime('%m/%d/%Y')
        today = end_date.strftime('%m/%d/%Y')
        
        # Add financial keywords to the search to get more relevant results
        financial_keyword_query = " OR ".join([f'"{k}"' for k in self.financial_keywords[:10]])  # Limit to first 10 keywords
        
        params = {
            'api_key': self.api_key,
            'postedFrom': yesterday,
            'postedTo': today,
            'limit': 10,
            'sortBy': 'postedDate',
            'order': 'desc',
            'keyword': financial_keyword_query  # Add financial keywords to search
        }
        
        logger.info("🔍 SAM API request: %s", self.base_url)
        logger.info("🔍 Financial keywords in search: %s", financial_keyword_query)
        
        try:
            self.last_api_call = time.time()  # Record the API call time
            response = await safe_async_get(self.base_url, params=params)
            if not response:
                logger.error("❌ No response from SAM.gov API")
                return []

            # Check for HTTP error status
            if response.status_code != 200:
                logger.error("❌ SAM.gov API returned status %d: %s", response.status_code, response.text)
                return []

            data = response.json()
            self.api_calls_made += 1  # Increment call count only on successful API response
            
            notices = [self._format_api_notice(notice) for notice in data.get("opportunitiesData", [])]
            logger.info("✅ SAM API call successful: %d notices", len(notices))
            return notices
        except Exception as e:
            log_error(e, "Failed to parse SAM.gov API response")
            return []

    async def _fetch_notices_from_scraper(self) -> List[Dict[str, Any]]:
        """
        SCRAPER-FALLBACK: Scrapes the public search results page if the API fails.
        This method does not count towards the API quota.
        """
        keyword_query = " OR ".join([f'"{k}"' for k in self.keywords])
        search_url = f"https://sam.gov/search/?keywords={keyword_query}&sort=-modifiedDate&page=1"
        
        logger.info("🔍 SAM scraper URL: %s", search_url)
        
        html_content = await self.scraper.fetch_content(search_url, wait_selector="[id^='search-results-']")
        if not html_content:
            logger.error("❌ SAM scraper failed to fetch content")
            return []
        
        logger.info("✅ SAM scraper fetched %d chars of HTML", len(html_content))
        
        notices = self._parse_search_results_page(html_content)
        logger.info("📊 SAM scraper parsed %d notices", len(notices))
        return notices

    def _parse_search_results_page(self, html: str) -> List[Dict[str, Any]]:
        """Parses the SAM.gov search results page HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        results = []
        
        # Look for notice items
        notice_items = soup.find_all("div", {"class": "search-result"})
        logger.info("🔍 Found %d notice items in HTML", len(notice_items))
        
        for item in notice_items:
            title_tag = item.find("a", {"class": "title"})
            title = title_tag.text.strip() if title_tag else "No Title"
            link = "https://sam.gov" + title_tag['href'] if title_tag and title_tag.has_attr('href') else ""
            content_div = item.find("div", {"class": "display-notes"})
            summary_content = content_div.text.strip() if content_div else ""
            
            results.append({
                "source": "SAM.gov Scraper",
                "title": title,
                "link": link,
                "content": summary_content,
            })
        
        logger.info("✅ Parsed %d notices from HTML", len(results))
        return results

    async def _gracefully_enhance_notice(self, notice: Dict[str, Any]) -> Dict[str, Any]:
        """
        SCRAPER-ENHANCEMENT: Scrapes the full detail page for a notice.
        This method does not count towards the API quota.
        """
        url = notice.get('link')
        if not url:
            logger.warning("⚠️  No URL found for notice: %s", notice.get('title', 'Unknown'))
            return notice
        
        try:
            logger.debug("🔍 Scraping SAM notice: %s", url)
            html_content = await self.scraper.fetch_content(url, wait_selector="#description")
            
            if html_content:
                soup = BeautifulSoup(html_content, 'html.parser')
                description_section = soup.find(id="description")
                if description_section:
                    full_content = description_section.get_text(separator='\n', strip=True)
                    notice['content'] = full_content
                    logger.info("✅ Successfully scraped SAM notice: %s (%d chars)", 
                               notice.get('title', 'Unknown'), len(full_content))
                else:
                    logger.warning("⚠️  No description section found for SAM notice: %s", notice.get('title', 'Unknown'))
            else:
                logger.warning("⚠️  Failed to scrape content for SAM notice: %s", notice.get('title', 'Unknown'))
                
        except Exception as e:
            logger.error("❌ Error scraping SAM notice %s: %s", url, str(e))
        
        return notice

    def _format_api_notice(self, notice: Dict) -> Dict:
        """Formats a notice from the API into our standard dictionary format."""
        title = notice.get("title", "No Title")
        description_or_url = notice.get("description", "")
        link = description_or_url if description_or_url.startswith('http') else f"https://sam.gov/opp/{notice.get('noticeId')}/view"

        return {
            "source": "SAM.gov API",
            "title": title,
            "link": link,
            "content": description_or_url, # Start with summary, enhance later
            "published_date": notice.get("postedDate"),
        }

    def _apply_business_filters(self, notices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Applies business logic filters: USD value extraction ($10M+) and company matching.
        Now with much stricter filtering for financial institution relevance.
        """
        filtered_notices = []
        for notice in notices:
            full_text = f"{notice.get('title', '')} {notice.get('content', '')}"
            value_usd = self._extract_value_usd(full_text)
            
            # Check for company mention
            company_mentioned = False
            for company_name, profile in self.company_profiles.items():
                if company_name.lower() in full_text.lower():
                    company_mentioned = True
                    break
            
            # Check for financial keywords (much stricter now)
            financial_keyword_mentioned = any(keyword.lower() in full_text.lower() for keyword in self.financial_keywords)
            
            # Check for general keywords
            keyword_mentioned = any(keyword.lower() in full_text.lower() for keyword in self.keywords)

            # MUCH STRICTER FILTERING: Only keep notices that are clearly relevant to financial institutions
            is_relevant = False
            
            # Case 1: Company mentioned AND (financial keyword OR high value)
            if company_mentioned and (financial_keyword_mentioned or (value_usd is not None and value_usd >= 10_000_000)):
                is_relevant = True
                logger.info(f"✅ SAM notice relevant: Company mentioned + (financial keyword OR high value): {notice.get('title', 'Unknown')}")
            
            # Case 2: High value ($50M+) even without company mention
            elif value_usd is not None and value_usd >= 50_000_000:
                is_relevant = True
                logger.info(f"✅ SAM notice relevant: High value (${value_usd:,}): {notice.get('title', 'Unknown')}")
            
            # Case 3: Strong financial keyword match (multiple keywords)
            elif financial_keyword_mentioned:
                # Count how many financial keywords are present
                financial_keyword_count = sum(1 for keyword in self.financial_keywords if keyword.lower() in full_text.lower())
                if financial_keyword_count >= 2:  # Require at least 2 financial keywords
                    is_relevant = True
                    logger.info(f"✅ SAM notice relevant: Multiple financial keywords ({financial_keyword_count}): {notice.get('title', 'Unknown')}")
            
            if is_relevant:
                notice['value_usd'] = value_usd
                notice['financial_keyword_count'] = sum(1 for keyword in self.financial_keywords if keyword.lower() in full_text.lower())
                filtered_notices.append(notice)
            else:
                logger.info(f"❌ SAM notice filtered out: {notice.get('title', 'Unknown')} (not relevant to financial institutions)")
        
        logger.info(f"📊 SAM filtering: {len(notices)} total notices, {len(filtered_notices)} relevant to financial institutions")
        return filtered_notices

    def _extract_value_usd(self, text: str) -> Optional[int]:
        """
        Extracts the largest USD dollar value from the text, only if no non-USD currency present.
        Re-integrated from old implementation.
        """
        if not text:
            return None
        non_usd_currencies = ['€', '£', 'C$', 'A$', '¥', '₹', '₽', '₩', '₪', '₨', '₦', '₡', '₱', '₴', '₸', '₺', '₼', '₾', '₿']
        found_non_usd = [c for c in non_usd_currencies if c in text]
        if found_non_usd:
            log_error(Exception(f"Found non-USD currencies in text: {found_non_usd}"), "Mixed currency detected")
            return None  # Be conservative if mixed currencies

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
            except Exception as ex:
                log_error(ex, f"Value extraction error for amount: {amount} {unit}")
                continue
        return int(max_value) if max_value > 0 else None
