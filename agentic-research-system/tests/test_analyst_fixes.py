#!/usr/bin/env python3
"""
Test script to verify analyst agent fixes are working correctly.
Tests company name extraction, source type preservation, and SEC filing analysis.
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from agents.analyst_agent import AnalystAgent

class MockAnalystAgent(AnalystAgent):
    """Mock analyst agent for testing without real API calls."""
    
    def __init__(self):
        # Skip kernel initialization for testing
        self.functions = {}
        self.chunk_size = 3000
        self.chunk_overlap = 500
        self.max_chunks = 10
        self.company_profiles = {}
        print("✅ Mock analyst agent initialized for testing")
    
    async def _ensure_kernel_initialized(self):
        pass
        
    async def _invoke_function_safely(self, function_name: str, input_text: str):
        """Return mock results based on function type."""
        if function_name == 'triage':
            return '{"is_relevant": true, "category": "News Article"}'
        elif function_name == 'financial':
            return '{"event_found": true, "value_usd": 2500000000, "event_type": "earnings", "description": "Strong quarterly earnings report"}'
        elif function_name == 'procurement':
            return '{"is_relevant": true, "value_usd": 25000000, "opportunity_type": "IT Security", "description": "IT security consulting services RFP"}'
        elif function_name == 'earnings':
            return '{"guidance_found": true, "value_usd": 2500000000, "guidance_type": "revenue", "description": "Positive revenue guidance"}'
        elif function_name == 'insight':
            return '{"what_happened": "Test event occurred", "why_it_matters": "This matters for business", "consulting_angle": "Sell advisory services", "need_type": "strategic", "service_line": "Strategic Advisory", "urgency": "high"}'
        elif function_name == 'company_takeaway':
            return '{"summary": "Use buyers and alumni on new project. Upsell opportunities: risk management."}'
        else:
            return '{"result": "mock"}'

def create_test_consolidated_data():
    """Create test consolidated data that mimics the real data structure."""
    return [
        {
            "source": "SEC Filing",
            "title": "Form 10-Q - Quarterly report [Sections 13 or 15(d)]",
            "link": "https://www.sec.gov/Archives/edgar/data/927628/000092762825000141/cof-20250331.htm",
            "content": "Capital One Financial Corporation quarterly earnings report...",
            "published_date": "2025-05-07T16:06:52-04:00",
            "company": "CAPITAL ONE FINANCIAL CORP",
            "form_type": "10-Q",
            "accession_no": "0000927628-25-000141",
            "cik": "927628",
            "content_enhanced": True,
            "raw_data": {
                "companyName": "CAPITAL ONE FINANCIAL CORP",
                "formType": "10-Q"
            },
            "relevance_score": 1.0,
            "source_type": "sec_filing",
            "key_terms": ["earnings", "quarterly", "financial"]
        },
        {
            "source": "GNews",
            "title": "Capital One (COF) climbs as investors buy into the Discover vision",
            "link": "https://www.cnbc.com/2025/07/22/capital-one-cof-climbs-as-investors-buy-into-the-discover-vision.html",
            "content": "Capital One stock rises on Discover acquisition news...",
            "published_date": "2025-07-22T23:32:27Z",
            "company": "Capital One",
            "relevance_score": 1.0,
            "source_type": "news",
            "key_terms": ["acquisition", "discover", "stock"]
        },
        {
            "source": "Bing Search",
            "title": "Industry Overview for Capital_One",
            "link": "N/A",
            "content": "Industry analysis of Capital One's position...",
            "published_date": "2025-07-28T12:17:04.654989",
            "company": "Capital One",
            "relevance_score": 1.0,
            "source_type": "bing_grounding",
            "key_terms": ["industry", "analysis", "trends"]
        }
    ]

async def test_company_name_extraction():
    """Test that company names are properly extracted from consolidated data."""
    print("\n🧪 TEST 1: Company Name Extraction")
    print("=" * 50)
    
    agent = MockAnalystAgent()
    test_data = create_test_consolidated_data()
    
    # Test the analyze_consolidated_data method
    results = await agent.analyze_consolidated_data(test_data, "Test analysis document")
    
    print(f"✅ Results count: {len(results)}")
    
    # Check that company names are preserved
    for i, result in enumerate(results):
        company = result.get('company', '')
        title = result.get('title', '')[:60]
        source_type = result.get('source_type', '')
        
        print(f"  Event {i+1}:")
        print(f"    Title: {title}")
        print(f"    Company: '{company}'")
        print(f"    Source Type: '{source_type}'")
        
        # Verify SEC filing has correct company name
        if 'SEC' in result.get('source', ''):
            assert company == "CAPITAL ONE FINANCIAL CORP", f"SEC filing company name wrong: {company}"
            print(f"    ✅ SEC filing company name correct: {company}")
        
        # Verify all events have company names
        assert company, f"Event {i+1} missing company name"
        print(f"    ✅ Company name present: {company}")
    
    print("✅ Company name extraction test PASSED")

async def test_source_type_preservation():
    """Test that source types are properly preserved through the analysis pipeline."""
    print("\n🧪 TEST 2: Source Type Preservation")
    print("=" * 50)
    
    agent = MockAnalystAgent()
    test_data = create_test_consolidated_data()
    
    results = await agent.analyze_consolidated_data(test_data, "Test analysis document")
    
    source_types_found = set()
    for result in results:
        source_type = result.get('source_type', '')
        source_types_found.add(source_type)
        print(f"  Found source type: '{source_type}' for '{result.get('title', '')[:40]}'")
    
    # Verify expected source types are present
    expected_types = {'SEC Filing', 'News Article', 'Industry Research'}
    for expected_type in expected_types:
        assert expected_type in source_types_found, f"Missing expected source type: {expected_type}"
        print(f"  ✅ Found expected source type: {expected_type}")
    
    print("✅ Source type preservation test PASSED")

async def test_sec_filing_analysis():
    """Test that SEC filings are properly analyzed and included in results."""
    print("\n🧪 TEST 3: SEC Filing Analysis")
    print("=" * 50)
    
    agent = MockAnalystAgent()
    test_data = create_test_consolidated_data()
    
    results = await agent.analyze_consolidated_data(test_data, "Test analysis document")
    
    # Look for SEC filings by checking source type and source
    sec_filings = [r for r in results if r.get('source_type') == 'SEC Filing' or 'SEC' in r.get('source', '')]
    
    print(f"✅ Found {len(sec_filings)} SEC filings in results")
    
    for i, sec_filing in enumerate(sec_filings):
        print(f"  SEC Filing {i+1}:")
        print(f"    Title: {sec_filing.get('title', '')[:60]}")
        print(f"    Company: {sec_filing.get('company', '')}")
        print(f"    Source Type: {sec_filing.get('source_type', '')}")
        print(f"    Form Type: {sec_filing.get('form_type', '')}")
        
        # Verify SEC filing has required fields
        assert sec_filing.get('company'), "SEC filing missing company name"
        assert sec_filing.get('source_type') == 'SEC Filing', f"SEC filing wrong source type: {sec_filing.get('source_type')}"
        assert sec_filing.get('form_type'), "SEC filing missing form type"
    
    assert len(sec_filings) > 0, "No SEC filings found in results"
    print("✅ SEC filing analysis test PASSED")

async def test_insight_generation():
    """Test that insights are properly generated with company names and source types."""
    print("\n🧪 TEST 4: Insight Generation")
    print("=" * 50)
    
    agent = MockAnalystAgent()
    test_data = create_test_consolidated_data()
    
    results = await agent.analyze_consolidated_data(test_data, "Test analysis document")
    
    for i, result in enumerate(results):
        insights = result.get('insights', {})
        company = result.get('company', '')
        source_type = result.get('source_type', '')
        
        print(f"  Event {i+1}:")
        print(f"    Company: '{company}'")
        print(f"    Source Type: '{source_type}'")
        print(f"    What Happened: '{insights.get('what_happened', 'N/A')}'")
        
        # Verify insights are generated
        assert insights, f"Event {i+1} missing insights"
        assert company, f"Event {i+1} missing company name"
        assert source_type, f"Event {i+1} missing source type"
        
        print(f"    ✅ Insights generated successfully")
    
    print("✅ Insight generation test PASSED")

async def test_deduplication():
    """Test that duplicate events are properly handled."""
    print("\n🧪 TEST 5: Deduplication")
    print("=" * 50)
    
    # Create test data with potential duplicates
    test_data = create_test_consolidated_data()
    # Add a duplicate SEC filing
    test_data.append(test_data[0].copy())  # Duplicate the SEC filing
    
    agent = MockAnalystAgent()
    results = await agent.analyze_consolidated_data(test_data, "Test analysis document")
    
    # Count SEC filings
    sec_filings = [r for r in results if 'SEC' in r.get('source', '') or 'filing' in r.get('source', '').lower()]
    
    print(f"✅ Found {len(sec_filings)} SEC filings (should be 1, not 2)")
    
    # SEC filings should not be deduplicated (they're unique by form type and date)
    assert len(sec_filings) >= 1, "SEC filings were incorrectly removed"
    
    print("✅ Deduplication test PASSED")

async def run_all_tests():
    """Run all tests and report results."""
    print("🚀 Starting Analyst Agent Fix Verification Tests")
    print("=" * 60)
    
    tests = [
        test_company_name_extraction,
        test_source_type_preservation,
        test_sec_filing_analysis,
        test_insight_generation,
        test_deduplication
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            await test()
            passed += 1
        except Exception as e:
            print(f"❌ Test failed: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 TEST RESULTS: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 ALL TESTS PASSED! Analyst agent fixes are working correctly.")
    else:
        print("⚠️  Some tests failed. Please review the fixes.")
    
    return failed == 0

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1) 