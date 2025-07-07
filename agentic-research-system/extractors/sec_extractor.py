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