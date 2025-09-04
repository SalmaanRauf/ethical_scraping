#!/usr/bin/env python3
"""
Test script to verify SEC filing processing fixes.
"""

import asyncio
import json
from pathlib import Path
import sys

# Add the parent directory to Python path for imports
parent_dir = Path(__file__).parent
sys.path.insert(0, str(parent_dir))

from extractors.sec_extractor import SECExtractor
from agents.data_consolidator import DataConsolidator
from agents.analyst_agent import AnalystAgent
from services.profile_loader import ProfileLoader
from agents.scraper_agent import ScraperAgent

async def test_sec_pipeline():
    """Test the complete SEC filing pipeline."""
    print("🧪 Testing SEC filing pipeline...")
    
    # Initialize components
    profile_loader = ProfileLoader()
    scraper_agent = ScraperAgent()
    
    # Test SEC extractor
    print("\n1. Testing SEC Extractor...")
    sec_extractor = SECExtractor(scraper_agent, profile_loader)
    
    # Test with Capital One
    sec_filings = await sec_extractor.extract_for_company("Capital One")
    print(f"✅ SEC Extractor returned {len(sec_filings)} filings")
    
    if sec_filings:
        print("📄 Sample SEC filing structure:")
        sample = sec_filings[0]
        print(f"  Title: {sample.get('title', 'N/A')}")
        print(f"  Source: {sample.get('source', 'N/A')}")
        print(f"  Content: {sample.get('content', 'N/A')[:100]}...")
        print(f"  Description: {sample.get('description', 'N/A')[:100]}...")
        print(f"  Source Type: {sample.get('source_type', 'N/A')}")
    
    # Test data consolidator
    print("\n2. Testing Data Consolidator...")
    consolidator = DataConsolidator(profile_loader)
    
    # Create test data with SEC filings
    test_data = sec_filings if sec_filings else [
        {
            'source': 'SEC Filing',
            'title': 'Form 10-Q - Quarterly report',
            'content': 'Capital One Financial Corporation filed quarterly report with SEC',
            'description': 'Capital One Financial Corporation filed quarterly report with SEC',
            'company': 'CAPITAL ONE FINANCIAL CORP',
            'form_type': '10-Q',
            'source_type': 'sec_filing',
            'published_date': '2025-07-25'
        }
    ]
    
    consolidated_result = consolidator.process_raw_data(test_data)
    consolidated_items = consolidated_result.get('consolidated_items', [])
    print(f"✅ Data Consolidator processed {len(consolidated_items)} items")
    
    if consolidated_items:
        print("📊 Sample consolidated item:")
        sample = consolidated_items[0]
        print(f"  Title: {sample.get('title', 'N/A')}")
        print(f"  Source Type: {sample.get('source_type', 'N/A')}")
        print(f"  Relevance Score: {sample.get('relevance_score', 'N/A')}")
        print(f"  Content: {sample.get('content', 'N/A')[:100]}...")
    
    # Test analyst agent
    print("\n3. Testing Analyst Agent...")
    analyst = AnalystAgent()
    
    # Set up company profiles
    profiles = {
        'CAPITAL ONE FINANCIAL CORP': {
            'description': 'Financial services company',
            'key_buyers': [],
            'projects': [],
            'protiviti_alumni': []
        }
    }
    analyst.set_profiles(profiles)
    
    # Test analysis
    analyzed_events = await analyst.analyze_consolidated_data(consolidated_items, "Test analysis document")
    print(f"✅ Analyst Agent processed {len(analyzed_events)} events")
    
    if analyzed_events:
        print("🎯 Sample analyzed event:")
        sample = analyzed_events[0]
        print(f"  Title: {sample.get('title', 'N/A')}")
        print(f"  Source Type: {sample.get('source_type', 'N/A')}")
        insights = sample.get('insights', {})
        print(f"  What Happened: {insights.get('what_happened', 'N/A')}")
        print(f"  Why It Matters: {insights.get('why_it_matters', 'N/A')}")
        print(f"  Consulting Angle: {insights.get('consulting_angle', 'N/A')}")
    
    print("\n✅ SEC filing pipeline test complete!")
    return len(analyzed_events) > 0

if __name__ == "__main__":
    success = asyncio.run(test_sec_pipeline())
    if success:
        print("\n🎉 SEC filing processing is working correctly!")
    else:
        print("\n❌ SEC filing processing needs attention.")
        sys.exit(1) 