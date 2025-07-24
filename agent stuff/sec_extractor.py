"""
Module to interact with SEC EDGAR filings using the sec_api package.
Provides extraction and filtering for important companies and forms.

Classes:
    SECExtractor: Extracts filings and their text for select financial institutions.
"""

import os
import logging
from sec_api import QueryApi, ExtractorApi
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Configure logging for the module
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)

# Mapping for canonical company names consistent across the pipeline
CANONICAL_COMPANIES = {
    "Capital One Financial Corporation": "Capital One",
    "Federal Home Loan Mortgage Corporation": "Freddie Mac",
    "Federal National Mortgage Association": "Fannie Mae",
    "Eagle Bancorp Inc.": "EagleBank",
    "Capital Bancorp Inc.": "Capital Bank N.A."
}
# NOTE: "Navy Federal Credit Union" and "PenFed Credit Union" do not have public tickers and
# will not be in SEC filings.

class SECExtractor:
    """
    Class to fetch and extract text from recent SEC filings for selected companies.

    Attributes:
        query_api (QueryApi): Instance for running SEC EDGAR queries.
        extractor_api (ExtractorApi): (Unused) Instance for extracting SEC filing text.
        target_tickers (dict): Maps tickers to company names.
        scraper_agent: Optional; a web scraper agent for supplemental extraction.
    """

    def __init__(self, scraper_agent=None):
        """
        Initializes SECExtractor by loading environment variables, setting up APIs,
        and preparing the target companies to monitor. Allows for optional web scraper agent.

        Args:
            scraper_agent: Optional web scraper agent for supplemental extraction.
        Raises:
            EnvironmentError: If SEC_API_KEY is missing from environment variables.
        """
        load_dotenv()
        self.api_key = os.getenv("SEC_API_KEY")
        self.scraper_agent = scraper_agent

        if not self.api_key:
            logger.error("SEC_API_KEY not found in environment variables.")
            return

        self.query_api = QueryApi(api_key=self.api_key)
        # self.extractor_api = ExtractorApi(api_key=self.api_key)  # Not currently used
        self.target_tickers = {
            "COF": "Capital One Financial Corporation",
            "FMCC": "Federal Home Loan Mortgage Corporation",    # Freddie Mac
            "FNMA": "Federal National Mortgage Association",     # Fannie Mae
            "EGBN": "Eagle Bancorp Inc.",
            "CBNK": "Capital Bancorp Inc."
        }
        # NOTE: PenFed and Navy Federal Credit Union do not have public tickers; cannot be queried.

        # --- API quota management (strict for free tier) ---
        self.api_calls_made = 0
        self.max_api_calls = 2  # Hard cap per run

    def get_filings_and_text(self):
        """
        Fetches the 25 most recent SEC filings (10-Q, 10-K) for target companies.
        Extracts relevant info and the 'extractedText' for each result, falling back to
        scraper_agent if provided and extractedText is missing or too short.
        Limits to max_per_company filings per company.

        Returns:
            list: List of dictionaries, each containing filing details and text.
                  Returns an empty list on error or if SEC_API_KEY is missing.
        """
        if not self.api_key:
            logger.warning("SECExtractor is not initialized due to missing API key.")
            return []

        if self.api_calls_made >= self.max_api_calls:
            msg = f"⚠️  SECExtractor API quota limit reached ({self.api_calls_made}/{self.max_api_calls}) -- not making any more API calls this run."
            print(msg)
            logger.error(msg)
            return []

        ticker_list = " OR ".join([f'ticker:\"{ticker}\"' for ticker in self.target_tickers.keys()])
        query = {
            "query": {
                "query_string": {
                    "query": f"({ticker_list}) AND (formType:\"10-Q\" OR formType:\"10-K\")"
                }
            },
            "from": "0",
            "size": "25",
            "sort": [{"filedAt": {"order": "desc"}}]
        }

        try:
            logger.info("Fetching recent SEC filings...")
            filings = self.query_api.get_filings(query).get('filings', [])
            self.api_calls_made += 1

            # Limit to max_per_company filings per company
            company_counts = {}
            max_per_company = 3
            limited_filings = []
            for filing in filings:
                company = filing.get('companyName', '') or ''
                if company not in company_counts:
                    company_counts[company] = 0
                if company_counts[company] < max_per_company:
                    limited_filings.append(filing)
                    company_counts[company] += 1

            extracted_data = []
            for filing in limited_filings:
                try:
                    canonical_company = CANONICAL_COMPANIES.get(
                        filing.get('companyName', ''), filing.get('companyName', '')
                    )
                    result = {
                        'company': canonical_company,
                        'ticker': filing.get('ticker', ''),
                        'type': filing.get('formType', ''),
                        'filedAt': filing.get('filedAt', ''),
                        'link': filing.get('linkToFilingDetails', ''),
                        'source': 'SEC',
                        'data_type': 'filing'
                    }
                    extracted_text = filing.get('extractedText', '') or ''
                    text_to_use = extracted_text
                    scraped_content = None
                    link = result['link']

                    # Fallback: Use scraper_agent if primary text is short/missing
                    if (not extracted_text or len(extracted_text.strip()) < 200) and self.scraper_agent is not None and hasattr(self.scraper_agent, 'scrape_url'):
                        try:
                            import asyncio
                            scraped_content = asyncio.run(self.scraper_agent.scrape_url(link, "sec_filing"))
                            if scraped_content:
                                text_to_use = scraped_content
                                logger.info(f"✅ Used scraped_content from ScraperAgent for {link}")
                        except Exception as scrape_exc:
                            logger.warning(f"⚠️  Scraping SEC filing failed: {scrape_exc}")
                    # always set text to best available, for downstream code
                    result['text'] = text_to_use
                    # Optionally include scraped_content for debugging
                    if scraped_content:
                        result['scraped_content'] = scraped_content
                    extracted_data.append(result)
                except Exception as e:
                    logger.exception(f"Error processing filing {filing.get('ticker', 'Unknown')}: {e}")
                    continue
            logger.info(f"Successfully processed {len(extracted_data)} SEC filings (with scraping if available)")
            return extracted_data
        except Exception as ex:
            logger.exception(f"Error during SEC extraction: {ex}")
            return []

    def get_recent_filings(self, days_back=178):
        """
        Fetches and (if possible) enhances SEC filings with full scraped content.
        Extremely verbose logs for each document.
        """
        import asyncio
        if not self.api_key:
            logger.warning("SECExtractor is not initialized due to missing API key.")
            return []

        if self.api_calls_made >= self.max_api_calls:
            msg = f"⚠️  SECExtractor API quota limit reached ({self.api_calls_made}/{self.max_api_calls}) -- not making any more API calls this run."
            print(msg)
            logger.error(msg)
            return []

        logger.info(f"📄 SEC: Fetching recent filings for last {days_back} days...")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        ticker_list = " OR ".join([f'ticker:\"{ticker}\"' for ticker in self.target_tickers.keys()])
        query = {
            "query": {
                "query_string": {
                    "query": (
                        f"({ticker_list}) AND formType:(10-Q OR 10-K) "
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

            # ---- LIMIT PER COMPANY ----
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

            logger.info(f"🔍 {len(limited_filings)} filings fetched from EDGAR API.")

            if self.scraper_agent and self.scraper_agent.is_available():
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
                            full_content = asyncio.run(self.scraper_agent.scrape_url(url, "sec_filing"))
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
            logger.exception(f"Error during SEC extraction: {e}")
            return []