import asyncio
from typing import List, Dict, Any
from datetime import datetime, timedelta
from sec_api import QueryApi
from bs4 import BeautifulSoup
from config.config import AppConfig
from services.profile_loader import ProfileLoader
from agents.scraper_agent import ScraperAgent
from services.error_handler import log_error

class SECExtractor:
    """
    Extracts recent SEC filings for specified companies using the SEC-API.io.
    Implements API quota management and uses a scraper for full content enhancement.
    """
    def __init__(self, scraper_agent: ScraperAgent, profile_loader: ProfileLoader):
        self.api_key = AppConfig.SEC_API_KEY
        self.query_api = QueryApi(api_key=self.api_key) if self.api_key else None
        self.scraper_agent = scraper_agent
        self.profile_loader = profile_loader
        self.company_profiles = self.profile_loader.load_profiles()

        # API quota management
        self.api_calls_made = 0
        self.max_api_calls = 2 # Strict cap per run as per old implementation

    async def get_recent_filings(self, days_back: int = None) -> List[Dict[str, Any]]:
        """
        Fetches recent filings for all configured companies within a specified date range.
        Enhances filings with full scraped content if a scraper agent is available.
        """
        if days_back is None:
            days_back = AppConfig.SEC_DAYS_BACK
        """
        Fetches recent filings for all configured companies within a specified date range.
        Enhances filings with full scraped content if a scraper agent is available.
        """
        if not self.query_api:
            log_error(Exception("SEC API key not configured."), "SEC Extractor not initialized")
            return []

        if self.api_calls_made >= self.max_api_calls:
            log_error(Exception(f"SEC API quota limit reached ({self.api_calls_made}/{self.max_api_calls})."), "SEC API Quota Exceeded")
            return []

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        all_filings = []
        for company_name, profile in self.company_profiles.items():
            cik = profile.get("sec_cik")
            if not cik:
                continue

            query = {
                "query": {
                    "query_string": {
                        "query": (
                            f"cik:\"{cik}\" AND formType:(\"10-Q\" OR \"10-K\") "
                            f"AND filedAt:[{start_date.strftime('%Y-%m-%d')} TO {end_date.strftime('%Y-%m-%d')}]"
                        )
                    }
                },
                "from": "0",
                "size": "10", # Fetch a reasonable number per company
                "sort": [{"filedAt": {"order": "desc"}}]
            }

            try:
                filings = self.query_api.get_filings(query).get('filings', [])
                self.api_calls_made += 1

                # Limit to max_per_company filings per company (from old implementation)
                max_per_company = 3
                company_filings_count = 0
                for filing in filings:
                    if company_filings_count < max_per_company:
                        all_filings.append(filing)
                        company_filings_count += 1

                if self.api_calls_made >= self.max_api_calls:
                    log_error(Exception(f"SEC API quota limit reached ({self.api_calls_made}/{self.max_api_calls}). Stopping early."), "SEC API Quota Exceeded")
                    break # Stop processing further companies if quota hit

            except Exception as e:
                log_error(e, f"Error fetching SEC filings for {company_name} (CIK: {cik})")

        # Enhance all found filings with full content
        enhancement_tasks = [self._gracefully_enhance_filing(filing) for filing in all_filings]
        enhanced_filings = await asyncio.gather(*enhancement_tasks)
        
        return [filing for filing in enhanced_filings if filing]

    async def _gracefully_enhance_filing(self, filing: Dict) -> Dict:
        """
        Attempts to scrape the full text of a filing from its SEC URL.
        If scraping fails, it falls back to the original extracted text or summary.
        """
        filing_url = filing.get('linkToFilingDetails')
        if not filing_url:
            return filing

        try:
            html_content = await self.scraper_agent.fetch_content(filing_url, wait_selector="body")
            if html_content:
                soup = BeautifulSoup(html_content, 'html.parser')
                main_content = soup.find('div', {'id': 'content'})
                if main_content:
                    filing['content'] = main_content.get_text(separator='\n', strip=True)
                else:
                    filing['content'] = soup.body.get_text(separator='\n', strip=True) if soup.body else ""
        except Exception as e:
            log_error(e, f"Graceful enhancement failed for SEC filing {filing_url}. Falling back to summary.")
        
        return filing
