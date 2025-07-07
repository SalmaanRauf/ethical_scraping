import os
import requests
from typing import Dict, Any, List
from googleapiclient.discovery import build
from dotenv import load_dotenv

class Validator:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
        self.cse_id = os.getenv("GOOGLE_CSE_ID")
        
        # Target companies for validation
        self.target_companies = [
            "Capital One", "Truist", "Freddie Mac", "Navy Federal", 
            "PenFed", "Fannie Mae", "USAA"
        ]

    def validate_event_internal(self, event_headline: str, company_name: str, internal_data: Dict[str, List]) -> bool:
        """
        Internal validation: Check if keywords from headline appear in internal data sources.
        """
        # Extract key words from headline (first 3-5 words)
        headline_words = event_headline.split()[:5]
        
        # Check SEC filings
        for filing in internal_data.get('sec_filings', []):
            if (company_name.lower() in filing.get('company', '').lower() and 
                any(word.lower() in filing.get('text', '').lower() for word in headline_words)):
                print(f"✅ Internally validated via SEC filing: {event_headline}")
                return True
        
        # Check news articles
        for article in internal_data.get('news', []):
            if (company_name.lower() in article.get('company', '').lower() and 
                any(word.lower() in article.get('title', '').lower() for word in headline_words)):
                print(f"✅ Internally validated via news article: {event_headline}")
                return True
        
        # Check procurement notices
        for notice in internal_data.get('procurement', []):
            if (company_name.lower() in notice.get('title', '').lower() and 
                any(word.lower() in notice.get('description', '').lower() for word in headline_words)):
                print(f"✅ Internally validated via procurement notice: {event_headline}")
                return True
        
        return False

    def validate_event_external(self, event_headline: str, company_name: str) -> bool:
        """
        External validation using Google Custom Search API.
        """
        if not self.api_key or not self.cse_id:
            print("⚠️  Google Search API credentials not found. Skipping external validation.")
            return False
        
        try:
            service = build("customsearch", "v1", developerKey=self.api_key)
            
            # Create search query
            query = f'"{event_headline}" "{company_name}"'
            
            # Search for recent results (last month)
            res = service.cse().list(
                q=query, 
                cx=self.cse_id, 
                num=3,
                dateRestrict='m1'  # Restrict to last month
            ).execute()
            
            # If we get at least one result, consider it validated
            if 'items' in res and len(res['items']) > 0:
                print(f"✅ Externally validated via Google Search: {event_headline}")
                print(f"   Found {len(res['items'])} confirming sources")
                return True
            else:
                print(f"❌ No external confirmation found for: {event_headline}")
                return False
                
        except Exception as e:
            print(f"❌ Google Search validation failed: {e}")
            return False

    def validate_event(self, event: Dict[str, Any], internal_data: Dict[str, List]) -> Dict[str, Any]:
        """
        Main validation method that combines internal and external validation.
        """
        event_headline = event.get('headline', '')
        company_name = event.get('company', '')
        
        print(f"🔍 Validating event: {event_headline}")
        
        # Step 1: Internal validation
        internal_validated = self.validate_event_internal(event_headline, company_name, internal_data)
        
        if internal_validated:
            event['validation_status'] = 'validated_internal'
            event['validation_method'] = 'internal_cross_reference'
            return event
        
        # Step 2: External validation (fallback)
        external_validated = self.validate_event_external(event_headline, company_name)
        
        if external_validated:
            event['validation_status'] = 'validated_external'
            event['validation_method'] = 'google_search'
        else:
            event['validation_status'] = 'unvalidated'
            event['validation_method'] = 'none'
        
        return event

    def validate_all_events(self, events: List[Dict[str, Any]], internal_data: Dict[str, List]) -> List[Dict[str, Any]]:
        """
        Validate all events in a batch.
        """
        validated_events = []
        
        for event in events:
            validated_event = self.validate_event(event, internal_data)
            validated_events.append(validated_event)
        
        # Count validation results
        internal_count = sum(1 for e in validated_events if e['validation_status'] == 'validated_internal')
        external_count = sum(1 for e in validated_events if e['validation_status'] == 'validated_external')
        unvalidated_count = sum(1 for e in validated_events if e['validation_status'] == 'unvalidated')
        
        print(f"📊 Validation Summary:")
        print(f"   - Internally validated: {internal_count}")
        print(f"   - Externally validated: {external_count}")
        print(f"   - Unvalidated: {unvalidated_count}")
        
        return validated_events

    def get_validation_stats(self, events: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Get validation statistics for a list of events.
        """
        stats = {
            'total_events': len(events),
            'validated_internal': 0,
            'validated_external': 0,
            'unvalidated': 0
        }
        
        for event in events:
            status = event.get('validation_status', 'unvalidated')
            if status in stats:
                stats[status] += 1
        
        return stats 