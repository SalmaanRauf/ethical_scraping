import asyncio
from typing import List, Dict, Any
from datetime import datetime, timedelta
import logging
from sec_api import QueryApi
from bs4 import BeautifulSoup
from config.config import AppConfig
from services.profile_loader import ProfileLoader
from agents.scraper_agent import ScraperAgent
from services.error_handler import log_error

# Set up developer logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

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
        # Use lazy loading instead of loading profiles in constructor
        self._company_profiles = None

        # API quota management
        self.api_calls_made = 0
        self.max_api_calls = 2 # Strict cap per run as per old implementation
        
        logger.info("🔍 SECExtractor initialized")

    @property
    def company_profiles(self):
        """Lazy load company profiles when first accessed."""
        if self._company_profiles is None:
            self._company_profiles = self.profile_loader.load_profiles()
        return self._company_profiles

    async def get_recent_filings(self, days_back: int = None) -> List[Dict[str, Any]]:
        """
        Fetches recent filings for all configured companies within a specified date range.
        Enhances filings with full scraped content if a scraper agent is available.
        """
        if days_back is None:
            days_back = AppConfig.SEC_DAYS_BACK
        
        logger.info("📄 Starting SEC filing extraction (days_back: %d)", days_back)
        
        if not self.query_api:
            logger.error("❌ SEC API key not configured")
            return []

        if self.api_calls_made >= self.max_api_calls:
            logger.error("❌ SEC API quota limit reached (%d/%d)", self.api_calls_made, self.max_api_calls)
            return []

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        all_filings = []
        for company_name, profile in self.company_profiles.items():
            cik = profile.get("sec_cik")
            if not cik:
                logger.warning("⚠️  No CIK found for company: %s", company_name)
                continue

            logger.info("🔍 Fetching SEC filings for %s (CIK: %s)", company_name, cik)

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

                logger.info("📄 SEC API returned %d filings for %s", len(filings), company_name)

                # Limit to max_per_company filings per company (from old implementation)
                max_per_company = 3
                company_filings_count = 0
                for filing in filings:
                    if company_filings_count < max_per_company:
                        all_filings.append(filing)
                        company_filings_count += 1

                logger.info("✅ Added %d filings for %s", company_filings_count, company_name)

                if self.api_calls_made >= self.max_api_calls:
                    logger.warning("⚠️  SEC API quota limit reached (%d/%d). Stopping early.", self.api_calls_made, self.max_api_calls)
                    break # Stop processing further companies if quota hit

            except Exception as e:
                log_error(e, f"Error fetching SEC filings for {company_name} (CIK: {cik})")

        logger.info("📊 Total SEC filings found: %d", len(all_filings))

        # Enhance all found filings with full content
        enhancement_tasks = [self._gracefully_enhance_filing(filing) for filing in all_filings]
        enhanced_filings = await asyncio.gather(*enhancement_tasks)
        
        final_filings = [filing for filing in enhanced_filings if filing]
        logger.info("✅ SEC extraction complete: %d enhanced filings", len(final_filings))
        
        return final_filings

    async def _gracefully_enhance_filing(self, filing: Dict) -> Dict:
        """
        Attempts to scrape the full text of a filing from its SEC URL.
        If scraping fails, it falls back to the original extracted text or summary.
        """
        filing_url = filing.get('linkToFilingDetails')
        if not filing_url:
            logger.warning("⚠️  No filing URL found for: %s", filing.get('title', 'Unknown'))
            return filing

        try:
            logger.debug("🔍 Scraping SEC filing: %s", filing_url)
            html_content = await self.scraper_agent.fetch_content(filing_url, wait_selector="body")
            
            if html_content:
                # Use BeautifulSoup to extract clean text
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # Get text and clean it up
                full_text = soup.get_text()
                lines = (line.strip() for line in full_text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                full_text = ' '.join(chunk for chunk in chunks if chunk)
                
                if len(full_text) > 500:  # Only use scraped content if substantial
                    filing['content'] = full_text
                    logger.info("✅ Successfully scraped SEC filing: %s (%d chars)", 
                               filing.get('title', 'Unknown'), len(full_text))
                else:
                    logger.warning("⚠️  Scraped content too short for SEC filing: %s (%d chars)", 
                                  filing.get('title', 'Unknown'), len(full_text))
            else:
                logger.warning("⚠️  Failed to scrape content for SEC filing: %s", filing.get('title', 'Unknown'))
                
        except Exception as e:
            logger.error("❌ Error scraping SEC filing %s: %s", filing_url, str(e))
        
        return filing
