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
        
        # Use ticker symbols like the original version
        self.target_tickers = {
            "COF": "Capital One Financial Corporation",
            "FMCC": "Federal Home Loan Mortgage Corporation",    # Freddie Mac
            "FNMA": "Federal National Mortgage Association",     # Fannie Mae
            "EGBN": "Eagle Bancorp Inc.",
            "CBNK": "Capital Bancorp Inc."
        }
        # NOTE: PenFed and Navy Federal Credit Union do not have public tickers; cannot be queried.

        # API quota management
        self.api_calls_made = 0
        self.max_api_calls = 2 # Strict cap per run as per old implementation
        
        logger.info("🔍 SECExtractor initialized")

    def _get_ticker_for_company(self, company_name: str) -> str:
        """
        Get the ticker symbol for a specific company.
        """
        # Map company names to tickers
        company_to_ticker = {
            "Capital One": "COF",
            "Capital One Financial Corporation": "COF",
            "Freddie Mac": "FMCC", 
            "Federal Home Loan Mortgage Corporation": "FMCC",
            "Fannie Mae": "FNMA",
            "Federal National Mortgage Association": "FNMA",
            "Eagle Bank": "EGBN",
            "Eagle Bancorp Inc.": "EGBN",
            "Capital Bank": "CBNK",
            "Capital Bancorp Inc.": "CBNK"
        }
        
        # Try exact match first
        if company_name in company_to_ticker:
            return company_to_ticker[company_name]
        
        # Try partial matches
        for company, ticker in company_to_ticker.items():
            if company_name.lower() in company.lower() or company.lower() in company_name.lower():
                return ticker
        
        return None

    async def get_recent_filings(self, days_back: int = None, company_name: str = None) -> List[Dict[str, Any]]:
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

        # Use ticker-based query like the original version
        if company_name:
            # Query for specific company only
            ticker = self._get_ticker_for_company(company_name)
            if not ticker:
                logger.warning("⚠️  No ticker found for company: %s", company_name)
                return []
            
            logger.info("🔍 Querying SEC filings for %s (ticker: %s)", company_name, ticker)
            ticker_query = f'ticker:"{ticker}"'
        else:
            # Query for all companies (fallback for batch mode)
            ticker_list = " OR ".join([f'ticker:\"{ticker}\"' for ticker in self.target_tickers.keys()])
            ticker_query = f"({ticker_list})"
            logger.info("🔍 Querying SEC filings for all companies")
        
        query = {
            "query": {
                "query_string": {
                    "query": (
                        f"{ticker_query} AND formType:(10-Q OR 10-K) "
                        f"AND filedAt: [{start_date.strftime('%Y-%m-%d')} TO {end_date.strftime('%Y-%m-%d')}]"
                    )
                }
            },
            "from": "0",
            "size": "50",
            "sort": [{"filedAt": {"order": "desc"}}]
        }

        try:
            filings = self.query_api.get_filings(query).get('filings', [])
            self.api_calls_made += 1

            logger.info("📄 SEC API returned %d filings", len(filings))

            # Limit to max_per_company filings per company (from old implementation)
            max_per_company = 3
            company_counts = {}
            limited_filings = []
            for filing in filings:
                company = filing.get('companyName', '') or ''
                if company not in company_counts:
                    company_counts[company] = 0
                if company_counts[company] < max_per_company:
                    limited_filings.append(filing)
                    company_counts[company] += 1

            logger.info("✅ Limited to %d filings (%d companies)", len(limited_filings), len(company_counts))

            # Enhance all found filings with full content
            if self.scraper_agent and hasattr(self.scraper_agent, 'is_available') and self.scraper_agent.is_available():
                logger.info("🕷️  Enhancing filings with extracted full context via ScraperAgent...")
                enhanced = []
                success = 0
                fail = 0
                for idx, filing in enumerate(limited_filings):
                    url = filing.get('linkToFilingDetails') or filing.get('link') or filing.get('url')
                    title = filing.get('companyName', 'No Title')[:70]
                    if url:
                        try:
                            logger.info(f"➡️ [{idx+1}/{len(limited_filings)}] Scraping SEC filing: {title}\n    URL: {url}")
                            full_content = await self.scraper_agent.scrape_url(url, "sec_filing")
                            if full_content:
                                filing['full_content'] = full_content
                                filing['content_enhanced'] = True
                                logger.info(f"✅ SEC filing scraped successfully ({len(full_content)} chars): {title}")
                                success += 1
                            else:
                                filing['full_content'] = None
                                filing['content_enhanced'] = False
                                logger.warning(f"⚠️  Failed to extract content for SEC filing: {title}")
                                fail += 1
                        except Exception as e:
                            filing['full_content'] = None
                            filing['content_enhanced'] = False
                            logger.error(f"❌ Exception scraping SEC filing '{title}': {e}")
                            fail += 1
                    else:
                        filing['full_content'] = None
                        filing['content_enhanced'] = False
                        logger.warning(f"⚠️  SEC filing missing URL: '{title}'")
                        fail += 1
                    enhanced.append(filing)
                logger.info(f"📊 Filing enhancement summary: {success} ok, {fail} failed, {len(limited_filings)} total")
                return enhanced
            else:
                logger.warning("⚠️  ScraperAgent not available for SEC filings; sending plain results.")
                return limited_filings

        except Exception as e:
            log_error(e, "Error fetching SEC filings")
            return []

    async def extract_for_company(self, company_name: str, progress_handler=None) -> List[Dict[str, Any]]:
        """
        Extract SEC filings for a specific company.
        This method is called by the single company workflow.
        """
        logger.info("🔍 Extracting SEC filings for company: %s", company_name)
        
        # Get recent filings for the specific company only
        filings = await self.get_recent_filings(days_back=90, company_name=company_name)
        
        logger.info("✅ Found %d SEC filings for %s", len(filings), company_name)
        return filings
