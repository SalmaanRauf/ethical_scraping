import os
import requests
from typing import Dict, Any, List
from googleapiclient.discovery import build
from dotenv import load_dotenv
import re

class Validator:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
        self.cse_id = os.getenv("GOOGLE_CSE_ID")
        
        # Target companies for validation (final, corrected)
        self.target_companies = [
            "Capital One", "Fannie Mae", "Freddie Mac", "Navy Federal Credit Union", 
            "PenFed Credit Union", "EagleBank", "Capital Bank N.A."
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

    def _extract_key_terms(self, event_headline: str, company_name: str) -> List[str]:
        """Extract key terms for validation from event headline and company name."""
        # Extract company name variations
        company_terms = []
        company_lower = company_name.lower()
        
        # Handle company name variations
        if "capital one" in company_lower:
            company_terms.extend(["capital one", "capitalone", "cof"])
        elif "fannie mae" in company_lower:
            company_terms.extend(["fannie mae", "fanniemae", "fnma"])
        elif "freddie mac" in company_lower:
            company_terms.extend(["freddie mac", "freddiemac", "fmcc"])
        elif "navy federal" in company_lower:
            company_terms.extend(["navy federal", "navy federal credit union"])
        elif "penfed" in company_lower:
            company_terms.extend(["penfed", "penfed credit union"])
        elif "eaglebank" in company_lower or "eagle bank" in company_lower:
            company_terms.extend(["eaglebank", "eagle bank", "egbn"])
        elif "capital bank" in company_lower:
            company_terms.extend(["capital bank", "capital bank n.a.", "cbnk"])
        else:
            company_terms.append(company_name.lower())
        
        # Extract key terms from headline (excluding common words)
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'}
        
        headline_words = [word.lower() for word in event_headline.split() 
                         if word.lower() not in common_words and len(word) > 2]
        
        # Combine all terms
        all_terms = company_terms + headline_words[:5]  # Limit to first 5 meaningful words
        
        return all_terms

    def _analyze_search_result_relevance(self, result: Dict[str, Any], key_terms: List[str], event_headline: str, company_name: str) -> Dict[str, Any]:
        """Analyze the relevance of a single search result."""
        title = result.get('title', '').lower()
        snippet = result.get('snippet', '').lower()
        link = result.get('link', '').lower()
        
        # Combine all text for analysis
        full_text = f"{title} {snippet}"
        
        # Check for company name matches
        company_matches = 0
        for company_term in key_terms[:len(key_terms)//2]:  # First half are company terms
            if company_term in full_text:
                company_matches += 1
        
        # Check for headline term matches
        headline_matches = 0
        for term in key_terms[len(key_terms)//2:]:  # Second half are headline terms
            if term in full_text:
                headline_matches += 1
        
        # Check for date relevance (look for recent dates)
        date_patterns = [
            r'\b(2024|2023)\b',  # Recent years
            r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+\d{4}\b',
            r'\b\d{1,2}/\d{1,2}/\d{4}\b',
            r'\b\d{1,2}-\d{1,2}-\d{4}\b'
        ]
        
        recent_date_found = False
        for pattern in date_patterns:
            if re.search(pattern, full_text):
                recent_date_found = True
                break
        
        # Calculate relevance score
        total_terms = len(key_terms)
        company_score = company_matches / max(len(key_terms) // 2, 1)
        headline_score = headline_matches / max(len(key_terms) // 2, 1)
        
        # Weight the scores (company name is more important)
        relevance_score = (company_score * 0.7) + (headline_score * 0.3)
        
        # Determine if result is relevant
        is_relevant = (
            company_matches >= 1 and  # Must mention company
            headline_matches >= 1 and  # Must mention at least one headline term
            relevance_score >= 0.3     # Overall relevance threshold
        )
        
        return {
            'title': result.get('title', ''),
            'link': result.get('link', ''),
            'snippet': result.get('snippet', ''),
            'company_matches': company_matches,
            'headline_matches': headline_matches,
            'relevance_score': relevance_score,
            'recent_date_found': recent_date_found,
            'is_relevant': is_relevant
        }

    def validate_event_external(self, event_headline: str, company_name: str) -> bool:
        """
        Enhanced external validation using Google Custom Search API with smart content analysis.
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
                num=5,  # Increased to get more results for analysis
                dateRestrict='m1'  # Restrict to last month
            ).execute()
            
            if 'items' not in res or len(res['items']) == 0:
                print(f"❌ No external confirmation found for: {event_headline}")
                return False
            
            # Extract key terms for validation
            key_terms = self._extract_key_terms(event_headline, company_name)
            print(f"🔍 Analyzing {len(res['items'])} search results with key terms: {key_terms}")
            
            # Analyze each search result
            relevant_results = []
            for i, result in enumerate(res['items']):
                analysis = self._analyze_search_result_relevance(result, key_terms, event_headline, company_name)
                
                print(f"   Result {i+1}: {analysis['title'][:50]}...")
                print(f"      Company matches: {analysis['company_matches']}, Headline matches: {analysis['headline_matches']}")
                print(f"      Relevance score: {analysis['relevance_score']:.2f}, Recent date: {analysis['recent_date_found']}")
                print(f"      Relevant: {'✅' if analysis['is_relevant'] else '❌'}")
                
                if analysis['is_relevant']:
                    relevant_results.append(analysis)
            
            # Determine validation result
            if len(relevant_results) >= 2:
                print(f"✅ Externally validated via Google Search: {event_headline}")
                print(f"   Found {len(relevant_results)} highly relevant sources out of {len(res['items'])} total")
                return True
            elif len(relevant_results) == 1:
                print(f"⚠️  Weak external validation: {event_headline}")
                print(f"   Found only 1 relevant source out of {len(res['items'])} total")
                return False  # Require at least 2 relevant sources
            else:
                print(f"❌ No relevant external confirmation found for: {event_headline}")
                print(f"   Found 0 relevant sources out of {len(res['items'])} total")
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