import os
import asyncio
from sec_api import QueryApi, ExtractorApi
from datetime import datetime, timedelta
from dotenv import load_dotenv

class SECExtractor:
    def __init__(self, scraper_agent=None):
        # Load environment variables
        load_dotenv()
        self.api_key = os.getenv("SEC_API_KEY")
        self.scraper_agent = scraper_agent
        
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

    async def get_recent_filings(self, days_back=7):
        """Fetch recent SEC filings for all target companies within the last N days."""
        if not self.api_key:
            return []
            
        # Calculate date range with proper ISO format
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)
        
        # Build query with date filter using ISO format
        ticker_list = " OR ".join([f'ticker:"{ticker}"' for ticker in self.target_tickers.keys()])
        
        query = {
            "query": {
                "query_string": {
                    "query": f"({ticker_list}) AND formType:(8-K OR 10-Q OR 10-K) AND filedAt:[{start_date.isoformat()} TO {end_date.isoformat()}]"
                }
            },
            "from": "0",
            "size": "50",
            "sort": [{"filedAt": {"order": "desc"}}]
        }
        
        try:
            print(f"Fetching SEC filings from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")
            
            # Run the sync API call in an executor to avoid blocking
            loop = asyncio.get_event_loop()
            filings = await loop.run_in_executor(
                None,
                lambda: self.query_api.get_filings(query).get('filings', [])
            )
            
            extracted_data = []
            for filing in filings:
                try:
                    # Use ExtractorApi for cleaner text extraction
                    filing_link = filing.get('linkToFilingDetails', '')
                    extracted_text = filing.get('extractedText', '')
                    
                    # Try to enhance with scraper if available
                    if self.scraper_agent and self.scraper_agent.is_available() and filing_link:
                        try:
                            scraped_content = await self.scraper_agent.scrape_url(filing_link, "sec_filing")
                            if scraped_content:
                                extracted_text = scraped_content
                                print(f"✅ Enhanced SEC filing with scraped content: {filing.get('ticker', 'Unknown')}")
                            else:
                                # Fallback to ExtractorApi
                                try:
                                    extracted_text = self.extractor_api.get_content(filing_link)
                                except Exception as extract_error:
                                    print(f"Warning: Could not extract text for {filing.get('ticker', 'Unknown')}: {extract_error}")
                        except Exception as scrape_error:
                            print(f"Warning: Could not scrape {filing_link}: {scrape_error}")
                            # Fallback to ExtractorApi
                            try:
                                extracted_text = self.extractor_api.get_content(filing_link)
                            except Exception as extract_error:
                                print(f"Warning: Could not extract text for {filing.get('ticker', 'Unknown')}: {extract_error}")
                    elif filing_link:
                        try:
                            extracted_text = self.extractor_api.get_content(filing_link)
                        except Exception as extract_error:
                            print(f"Warning: Could not extract text for {filing.get('ticker', 'Unknown')}: {extract_error}")
                    
                    extracted_data.append({
                        'company': filing.get('companyName', ''),
                        'ticker': filing.get('ticker', ''),
                        'type': filing.get('formType', ''),
                        'filedAt': filing.get('filedAt', ''),
                        'link': filing.get('linkToFilingDetails', ''),
                        'text': extracted_text,
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