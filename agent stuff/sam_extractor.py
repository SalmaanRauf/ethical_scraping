import os
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
import re
import logging
from extractors.http_utils import ethical_get

# Configure persistent logging (file + timestamp + level)
logging.basicConfig(
    filename='sam_extractor.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)

class SAMExtractor:
    """
    Extracts and filters procurement notices from SAM.gov,
    searching for key companies and financial terms.
    Enforces USD, filters for $10M+, and manages API quota.
    """
    def __init__(self, scraper_agent=None):
        # Load environment variables
        load_dotenv()
        self.api_key = os.getenv("SAM_API_KEY")
        self.base_url = "https://api.sam.gov/prod/opportunities/v2/search"
        self.scraper_agent = scraper_agent
        # Target companies to monitor (canonical)
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
        self.max_api_calls = 2  # Leave buffer for other operations

    def extract_value_usd(self, text):
        """Extracts the largest USD dollar value from the text, only if no non-USD currency present."""
        if not text:
            return None
        non_usd_currencies = ['€', '£', 'C$', 'A$', '¥', '₹', '₽', '₩', '₪', '₨', '₦', '₡', '₱', '₴', '₸', '₺', '₼', '₾', '₿']
        found_non_usd = [c for c in non_usd_currencies if c in text]
        if found_non_usd:
            msg = f"⚠️  Found non-USD currencies in text: {found_non_usd}"
            print(msg)
            logger.warning(msg)
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
                logger.error(f"Value extraction error: {ex} | In text: {amount} {unit}")
                continue
        if max_value > 0:
            if found_non_usd:
                msg = f"⚠️  Mixed currencies detected. USD value: ${max_value:,}, but also found: {found_non_usd}"
                print(msg)
                logger.warning(msg)
                return None  # Be conservative if mixed currencies
            return int(max_value)
        return None

    def fetch_notice_details(self, notice_url):
        """Fetches detailed notice description from SAM.gov API."""
        if self.api_calls_made >= self.max_api_calls:
            msg = f"⚠️  API quota limit reached ({self.api_calls_made}/{self.max_api_calls})"
            print(msg)
            logger.error(msg)
            return None
        try:
            separator = '&' if '?' in notice_url else '?'
            api_url = f"{notice_url}{separator}api_key={self.api_key}"
            response = ethical_get(api_url, timeout=30, skip_robots=True)
            if response is None:
                error_msg = (
                    f"Request blocked or failed by ethical_get for detail fetch.\n"
                    f"  API URL: {api_url}\n"
                    f"  (Possible causes: bad API key, quota exceeded, HTTP 403/401, network issue, or invalid URL)\n"
                    f"  Check the HTTP debug printouts (status/body) above for details."
                )
                print(error_msg)
                logger.error(error_msg, exc_info=True)
                return None
            response.raise_for_status()
            self.api_calls_made += 1
            data = response.json()
            description = None
            if 'opportunity' in data and isinstance(data['opportunity'], dict):
                description = data['opportunity'].get('description', '')
            elif 'description' in data:
                description = data['description']
            elif 'fullText' in data:
                description = data['fullText']
            elif 'content' in data:
                description = data['content']
            else:
                for field in ['summary', 'details', 'text', 'body', 'content']:
                    if field in data and data[field]:
                        description = data[field]
                        break
            if not description:
                msg = f"⚠️  No description found in API response. Available fields: {list(data.keys())}"
                print(msg)
                logger.error(msg)
            return description
        except Exception as e:
            msg = f"❌ Error fetching notice details: {e}"
            print(msg)
            logger.error(msg, exc_info=True)
            return None

    async def fetch_notices(self, keywords=["RFP", "SOW", "consultant", "financial services"], max_notices=1, days_back=85):
        """Async: Fetches procurement notices from SAM.gov, filters and returns only relevant notices.
        Only keeps notices for target companies AND (keyword OR value_usd >= $10M).
        """
        if self.api_calls_made >= self.max_api_calls:
            msg = f"⚠️  SAMExtractor API quota limit reached ({self.api_calls_made}/{self.max_api_calls}) -- not making any more API calls this run."
            print(msg)
            logger.error(msg)
            return []
        
        if not self.api_key:
            error_msg = (
                f"Request blocked or failed by ethical_get during SAM.gov summary fetch.\n"
                f"  URL: {self.base_url}\n"
                f"  (Possible causes: API key/permissions, quota exceeded, 4xx/5xx error, or network issue)\n"
                f"  Check detailed HTTP debug printouts for more diagnostics."
            )
            print(error_msg)
            logger.error(error_msg, exc_info=True)
            return []
        # Corrected date format!
        yesterday = (datetime.now() - timedelta(days=days_back)).strftime('%m/%d/%Y')
        today = datetime.now().strftime('%m/%d/%Y')
        params = {
            'api_key': self.api_key,
            'postedFrom': yesterday,
            'postedTo': today,
            'limit': max_notices,
            'sortBy': 'postedDate',
            'order': 'desc'
        }
        try:
            print(f"Fetching SAM.gov notices from {yesterday} to {today}...")
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: ethical_get(self.base_url, params=params, timeout=30, skip_robots=True)
            )
            if response is None:
                error_msg = (
                    f"Request blocked or failed by ethical_get for summary fetch.\n"
                    f"  URL: {self.base_url}\n"
                    f"  Params: {params}\n"
                    f"  (Possible causes: bad API key, quota exceeded, HTTP 4xx/5xx, network issue, or invalid URL)\n"
                    f"  Check debug HTTP logs above for details."
                )
                print(error_msg)
                logger.error(error_msg, exc_info=True)
                return []
            response.raise_for_status()
            self.api_calls_made += 1
            data = response.json()
            notices = data.get("opportunitiesData", [])
            print(f"Found {len(notices)} notices in summary data")
            relevant_notices = []
            for notice in notices:
                title = str(notice.get("title", ""))
                description_url = notice.get("description", "")
                # Fetch details if description is a URL; otherwise, use as-is
                if isinstance(description_url, str) and description_url.startswith('http'):
                    if self.scraper_agent and getattr(self.scraper_agent, 'is_available', lambda: False)():
                        try:
                            scraped_content = await self.scraper_agent.scrape_url(description_url, "procurement")
                            full_description = scraped_content if scraped_content else self.fetch_notice_details(description_url)
                            if scraped_content:
                                print(f"✅ Enhanced procurement notice with scraped content")
                                logger.info(f"Enhanced procurement notice with scraped content: {description_url}")
                        except Exception as scrape_error:
                            msg = f"⚠️  Scraping failed, falling back to API: {scrape_error}"
                            print(msg)
                            logger.error(msg)
                            full_description = self.fetch_notice_details(description_url)
                    else:
                        full_description = self.fetch_notice_details(description_url)
                    if full_description is None:
                        continue
                else:
                    full_description = description_url
                full_text = f"{title} {full_description}"
                value_usd = self.extract_value_usd(full_text)
                company_match = any(company.lower() in full_text.lower() for company in self.target_companies)
                keyword_match = any(keyword.lower() in full_text.lower() for keyword in keywords)
                usd_match = value_usd is not None and value_usd >= 10_000_000
                # Only keep notice if about our target companies AND (keyword OR $10M+)
                relevant = company_match or (keyword_match or usd_match)
                if relevant:
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
                    print(f"  ✅ Found relevant notice: ${value_usd if value_usd else 'N/A'} - {title[:50]}...")
                    logger.info(f"Relevant notice: ${value_usd if value_usd else 'N/A'} - {title[:50]}...")
                if self.api_calls_made >= self.max_api_calls:
                    msg = f"⚠️  Stopping early due to API quota limit ({self.api_calls_made}/{self.max_api_calls})"
                    print(msg)
                    logger.warning(msg)
                    break
            print(f"Found {len(relevant_notices)} relevant procurement notices (company AND (keyword or $10M+))")
            print(f"API calls used: {self.api_calls_made}")
            logger.info(f"Total relevant procurement notices found: {len(relevant_notices)}")
            logger.info(f"API calls used: {self.api_calls_made}")
            return relevant_notices
        except Exception as e:
            error_msg = f"Error fetching data from SAM.gov: {e}"
            print(error_msg)
            logger.error(error_msg, exc_info=True)
            return []

    async def get_all_notices(self, days_back=85, keywords=None):
        """
        Fetch and enhance all SAM procurement notices.
        If ScraperAgent is available, add full HTML/text from each notice URL.
        Provides detailed logging for development/testability.
        """
        logger.info(f"📥 Fetching procurement notices for last {days_back} days...")
        notices = await self.fetch_notices(keywords=keywords or ["RFP", "SOW", "consultant", "financial services"], days_back=days_back)
        logger.info(f"🔍 {len(notices)} procurement notices fetched.")

        if self.scraper_agent and self.scraper_agent.is_available():
            logger.info("🕷️  Enhancing each notice with full content via ScraperAgent...")
            enhanced = []
            success = 0
            fail = 0
            for idx, notice in enumerate(notices):
                url = notice.get('link') or notice.get('url')
                title = notice.get('title', 'No Title')[:60]
                if url:
                    try:
                        logger.info(f"➡️ [{idx+1}/{len(notices)}] Scraping notice: {title}\n    URL: {url}")
                        full_content = await self.scraper_agent.scrape_url(url, "procurement")
                        if full_content:
                            notice['full_content'] = full_content
                            notice['content_enhanced'] = True
                            logger.info(f"✅ Notice scraped successfully ({len(full_content)} characters): {title}")
                            success += 1
                        else:
                            notice['full_content'] = None
                            notice['content_enhanced'] = False
                            logger.warning(f"⚠️  No content extracted for notice: {title}")
                            fail += 1
                    except Exception as e:
                        notice['full_content'] = None
                        notice['content_enhanced'] = False
                        logger.error(f"❌ Exception scraping notice '{title}': {e}")
                        fail += 1
                else:
                    notice['full_content'] = None
                    notice['content_enhanced'] = False
                    logger.warning(f"⚠️  Procurement notice missing URL: '{title}'")
                    fail += 1
                enhanced.append(notice)
            logger.info(f"📊 Notices enhancement summary: {success} succeeded, {fail} failed, {len(notices)} total")
            return enhanced
        else:
            logger.warning("⚠️  ScraperAgent not available for procurement notices; sending plain results.")
        return notices

    def get_quota_status(self):
        """Get current API quota status."""
        return {
            'calls_made': self.api_calls_made,
            'max_calls': self.max_api_calls,
            'remaining': self.max_api_calls - self.api_calls_made
        }

    def test_api_structure(self, max_test_notices=1):
        """Test the API response structure to understand correct data paths."""
        if not self.api_key:
            error_msg = "Error: SAM_API_KEY not found in environment variables."
            print(error_msg)
            logger.error(error_msg)
            return
        yesterday = (datetime.now() - timedelta(days=7)).strftime('%m/%d/%Y')
        today = datetime.now().strftime('%m/%d/%Y')
        params = {
            'api_key': self.api_key,
            'postedFrom': yesterday,
            'postedTo': today,
            'limit': max_test_notices,
            'sortBy': 'postedDate',
            'order': 'desc'
        }
        try:
            print(f"🧪 Testing API structure with {max_test_notices} notice(s)...")
            response = ethical_get(self.base_url, params=params, timeout=30, skip_robots=True)
            if response is None:
                error_msg = (
                    f"Request blocked or failed by ethical_get in test_api_structure.\n"
                    f"  URL: {self.base_url}\n"
                    f"  Params: {params}\n"
                    f"  Check prior HTTP debug printouts for status code/response body."
                )
                print(error_msg)
                logger.error(error_msg, exc_info=True)
                return
            response.raise_for_status()
            self.api_calls_made += 1
            data = response.json()
            notices = data.get("opportunitiesData", [])
            if not notices:
                msg = "⚠️  No notices found for testing"
                print(msg)
                logger.warning(msg)
                return
            print(f"📋 Found {len(notices)} notices for structure testing")
            for i, notice in enumerate(notices[:max_test_notices]):
                print(f"\n🧪 Testing notice {i+1}:")
                print(f"   Title: {notice.get('title', 'N/A')}")
                print(f"   Description URL: {notice.get('description', 'N/A')}")
                description_url = notice.get("description", "")
                if description_url.startswith('http'):
                    print(f"   🔗 Testing detail fetch...")
                    description = self.fetch_notice_details(description_url)
                    if description:
                        print(f"   ✅ Successfully fetched description")
                        print(f"   📝 Preview: {description[:200]}...")
                    else:
                        print(f"   ❌ Failed to fetch description")
                else:
                    print(f"   ⚠️  Description is not a URL: {description_url}")
        except Exception as e:
            error_msg = f"❌ Error testing API structure: {e}"
            print(error_msg)
            logger.error(error_msg, exc_info=True)