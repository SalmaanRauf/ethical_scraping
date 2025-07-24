import asyncio
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from agents.scraper_agent import ScraperAgent
from config.config import AppConfig
from services.error_handler import log_error
from extractors.http_utils import safe_async_get
from services.profile_loader import ProfileLoader

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
        self.company_profiles = self.profile_loader.load_profiles()

        # API quota management
        self.api_calls_made = 0
        self.max_api_calls = 5 # Max 5 API calls as per requirement

    async def get_all_notices(self, days_back: int = None) -> List[Dict[str, Any]]:
        """
        Fetches all recent notices and enhances them with full content.
        """
        if days_back is None:
            days_back = AppConfig.SAM_DAYS_BACK
        """
        Fetches all recent notices and enhances them with full content.
        """
        # API-First Approach
        notice_summaries = await self._fetch_notices_from_api(days_back)

        # Scraper-Fallback Approach
        if not notice_summaries:
            log_error(Exception("SAM.gov API failed or returned no results, falling back to scraper."), "SAM.gov API Fallback")
            notice_summaries = await self._fetch_notices_from_scraper()

        if not notice_summaries:
            return []

        # Graceful Scraper Enhancement
        enhancement_tasks = [self._gracefully_enhance_notice(notice) for notice in notice_summaries]
        enhanced_notices = await asyncio.gather(*enhancement_tasks)
        
        # Apply business logic filters after enhancement
        filtered_notices = self._apply_business_filters(enhanced_notices)
        
        return [notice for notice in filtered_notices if notice] # Filter out any None results

    async def _fetch_notices_from_api(self, days_back: int) -> List[Dict[str, Any]]:
        """API-FIRST: Tries to fetch notice summaries from the official SAM.gov API."""
        if not self.api_key:
            return []
        
        if self.api_calls_made >= self.max_api_calls:
            log_error(Exception(f"SAM.gov API quota limit reached ({self.api_calls_made}/{self.max_api_calls})."), "SAM.gov API Quota Exceeded")
            return []

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        params = {
            'api_key': self.api_key,
            'limit': 25, # Fetch a reasonable number of recent notices
            'sortBy': '-modifiedDate',
            'postedFrom': start_date.strftime('%Y-%m-%d'),
            'postedTo': end_date.strftime('%Y-%m-%d'),
        }
        response = await safe_async_get(self.base_url, params=params)
        if not response:
            return []

        try:
            data = response.json()
            self.api_calls_made += 1 # Increment call count only on successful API response
            return [self._format_api_notice(notice) for notice in data.get("opportunitiesData", [])]
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
        
        html_content = await self.scraper.fetch_content(search_url, wait_selector="[id^='search-results-']")
        if not html_content:
            return []
        
        return self._parse_search_results_page(html_content)

    def _parse_search_results_page(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        results = []
        for item in soup.select("[id^='search-results-']"):
            title_tag = item.select_one("h3 a")
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
        return results

    async def _gracefully_enhance_notice(self, notice: Dict[str, Any]) -> Dict[str, Any]:
        """
        SCRAPER-ENHANCEMENT: Scrapes the full detail page for a notice.
        This method does not count towards the API quota.
        """
        url = notice.get('link')
        if not url:
            return notice
        try:
            html_content = await self.scraper.fetch_content(url, wait_selector="#description")
            if html_content:
                soup = BeautifulSoup(html_content, 'html.parser')
                description_section = soup.find(id="description")
                if description_section:
                    notice['content'] = description_section.get_text(separator='\n', strip=True)
        except Exception as e:
            log_error(e, f"Graceful enhancement failed for SAM.gov URL {url}. Falling back to summary.")
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
            
            # Check for keyword mention
            keyword_mentioned = any(keyword.lower() in full_text.lower() for keyword in self.keywords)

            # Apply the old logic: Only keep notice if about our target companies AND (keyword OR value_usd >= $10M+)
            if company_mentioned and (keyword_mentioned or (value_usd is not None and value_usd >= 10_000_000)):
                notice['value_usd'] = value_usd
                filtered_notices.append(notice)
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
