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
        
        # Target companies to monitor (corrected)
        self.target_companies = [
            "Capital One",
            "Fannie Mae", 
            "Freddie Mac",
            "Navy Federal Credit Union",
            "EagleBank",
            "Capital Bank N.A."
        ]
        
        # API quota management
        self.api_calls_made = 0
        self.max_api_calls = 95  # Leave buffer for other operations
        self.quota_reset_date = None

    def extract_value_usd(self, text):
        """Extracts the largest dollar value from the text."""
        if not text:
            return None
            
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
        return int(max_value) if max_value else None

    def fetch_notice_details(self, notice_url):
        """Fetch detailed description for a specific notice."""
        if self.api_calls_made >= self.max_api_calls:
            print(f"⚠️  API quota limit reached ({self.api_calls_made}/{self.max_api_calls})")
            return None
            
        try:
            # Handle URL parameters properly
            separator = '&' if '?' in notice_url else '?'
            api_url = f"{notice_url}{separator}api_key={self.api_key}"
            
            print(f"🔗 Fetching: {api_url[:80]}...")
            response = ethical_get(api_url, timeout=30)
            if response is None:
                print("Request blocked or failed by ethical_get.")
                return None
                
            response.raise_for_status()
            self.api_calls_made += 1
            
            data = response.json()
            
            # Debug: Print the structure to understand the API response
            print(f"📋 API Response keys: {list(data.keys())}")
            
            # Try different possible paths for the description
            description = None
            
            # Path 1: data.opportunity.description
            if 'opportunity' in data and isinstance(data['opportunity'], dict):
                opportunity = data['opportunity']
                print(f"📋 Opportunity keys: {list(opportunity.keys())}")
                description = opportunity.get('description', '')
            
            # Path 2: data.description (direct)
            elif 'description' in data:
                description = data['description']
            
            # Path 3: data.fullText or data.content
            elif 'fullText' in data:
                description = data['fullText']
            elif 'content' in data:
                description = data['content']
            
            # Path 4: Check for any text-like fields
            else:
                text_fields = ['summary', 'details', 'text', 'body', 'content']
                for field in text_fields:
                    if field in data and data[field]:
                        description = data[field]
                        print(f"📋 Found description in field: {field}")
                        break
            
            if description:
                print(f"✅ Successfully extracted description ({len(description)} characters)")
                return description
            else:
                print(f"⚠️  No description found in API response")
                print(f"📋 Available fields: {list(data.keys())}")
                return None
            
        except Exception as e:
            print(f"❌ Error fetching notice details: {e}")
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

    def test_api_structure(self, max_test_notices=1):
        """Test the API response structure to understand the correct data paths."""
        if not self.api_key:
            print("Error: SAM_API_KEY not found in environment variables.")
            return

        # Get a few recent notices
        yesterday = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')  # Look back 7 days for more data
        today = datetime.now().strftime('%Y-%m-%d')
        
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
            response = ethical_get(self.base_url, params=params, timeout=30)
            if response is None:
                print("Request blocked or failed by ethical_get.")
                return
            response.raise_for_status()
            self.api_calls_made += 1
            
            data = response.json()
            notices = data.get("opportunitiesData", [])
            
            if not notices:
                print("⚠️  No notices found for testing")
                return
            
            print(f"📋 Found {len(notices)} notices for structure testing")
            
            # Test the first notice
            for i, notice in enumerate(notices[:max_test_notices]):
                print(f"\n🧪 Testing notice {i+1}:")
                print(f"   Title: {notice.get('title', 'N/A')}")
                print(f"   Description URL: {notice.get('description', 'N/A')}")
                
                # Try to fetch details
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
            print(f"❌ Error testing API structure: {e}")

    def get_quota_status(self):
        """Get current API quota status."""
        return {
            'calls_made': self.api_calls_made,
            'max_calls': self.max_api_calls,
            'remaining': self.max_api_calls - self.api_calls_made
        } 