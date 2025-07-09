#!/usr/bin/env python3
"""
Comprehensive test script for the Agentic Account Research System.
This script tests each component individually and then runs a full integration test.
"""

import asyncio
import sys
import os
from datetime import datetime

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

REQUIRED_ENV_VARS = [
    "OPENAI_API_KEY",
    "BASE_URL",
    "PROJECT_ID",
    "API_VERSION",
    "MODEL",
    "GOOGLE_SEARCH_API_KEY",
    "GOOGLE_CSE_ID",
    "SEC_API_KEY",
    "GNEWS_API_KEY",
    "SAM_API_KEY"
]

def test_environment():
    """Test environment setup and API keys."""
    print("🔧 Testing Environment Setup...")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    missing_keys = []
    for key in REQUIRED_ENV_VARS:
        if not os.getenv(key):
            missing_keys.append(key)
    
    if missing_keys:
        print(f"❌ Missing API keys: {', '.join(missing_keys)}")
        print("   Please add these to your .env file")
        return False
    else:
        print("✅ All required API keys found")
        return True

def test_database():
    """Test database setup and connectivity."""
    print("\n🗄️  Testing Database...")
    
    try:
        from config.database_setup import setup_database, check_database_status
        setup_database()
        check_database_status()
        print("✅ Database setup successful")
        return True
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_sam_extractor():
    """Test SAM extractor."""
    print("\n🔍 Testing SAM Extractor...")
    
    try:
        from extractors.sam_extractor import SAMExtractor
        extractor = SAMExtractor()
        
        # Test value extraction
        test_text = "The contract is valued at $15 million with additional options up to $25 million."
        value = extractor.extract_value_usd(test_text)
        print(f"✅ Value extraction: ${value:,}")
        
        # Test quota management
        quota_status = extractor.get_quota_status()
        print(f"✅ Quota status: {quota_status['calls_made']}/{quota_status['max_calls']}")
        
        # Test notice fetching (limited to avoid API usage)
        notices = extractor.fetch_notices(max_notices=5)
        print(f"✅ Found {len(notices)} notices")
        
        return True
    except Exception as e:
        print(f"❌ SAM Extractor test failed: {e}")
        return False

def test_news_extractor():
    """Test news extractor."""
    print("\n📰 Testing News Extractor...")
    
    try:
        from extractors.news_extractor import NewsExtractor
        extractor = NewsExtractor()
        
        # Test RSS feeds
        articles = extractor.fetch_from_rss()
        print(f"✅ RSS articles: {len(articles)}")
        
        # Test API feeds
        api_articles = extractor.fetch_from_api()
        print(f"✅ API articles: {len(api_articles)}")
        
        # Test combined
        all_news = extractor.get_all_news()
        print(f"✅ Total news: {len(all_news)}")
        
        return True
    except Exception as e:
        print(f"❌ News Extractor test failed: {e}")
        return False

def test_sec_extractor():
    """Test SEC extractor."""
    print("\n📄 Testing SEC Extractor...")
    
    try:
        from extractors.sec_extractor import SECExtractor
        extractor = SECExtractor()
        
        # Check API key
        if not extractor.api_key:
            print("❌ SEC_API_KEY not available")
            return False
        
        print(f"✅ SEC Extractor initialized")
        print(f"📊 Target tickers: {list(extractor.target_tickers.keys())}")
        
        # Test API connectivity
        try:
            # Simple connectivity test
            query = {
                "query": {
                    "query_string": {
                        "query": 'ticker:"COF" AND formType:"8-K"'
                    }
                },
                "from": "0",
                "size": "1"
            }
            
            result = extractor.query_api.get_filings(query)
            print(f"✅ API connectivity: {len(result.get('filings', []))} test filings")
            
        except Exception as e:
            print(f"❌ API connectivity failed: {e}")
            return False
        
        # Test recent filings
        try:
            filings = extractor.get_recent_filings(days_back=7)
            print(f"✅ Recent filings: {len(filings)}")
            
            # Check data quality
            if filings:
                sample = filings[0]
                required_fields = ['company', 'ticker', 'type', 'filedAt', 'link', 'text', 'source', 'data_type']
                missing_fields = [field for field in required_fields if field not in sample]
                
                if missing_fields:
                    print(f"⚠️  Missing fields in sample: {missing_fields}")
                else:
                    print(f"✅ Data structure validation passed")
                
                print(f"📋 Sample: {sample.get('company', 'N/A')} - {sample.get('type', 'N/A')}")
            
        except Exception as e:
            print(f"❌ Recent filings test failed: {e}")
            return False
        
        # Test full extraction
        try:
            all_filings = extractor.get_filings_and_text()
            print(f"✅ Full extraction: {len(all_filings)} filings")
            
        except Exception as e:
            print(f"❌ Full extraction failed: {e}")
            return False
        
        return True
    except Exception as e:
        print(f"❌ SEC Extractor test failed: {e}")
        return False

def test_semantic_kernel():
    """Test Semantic Kernel setup."""
    print("\n🤖 Testing Semantic Kernel...")
    
    try:
        from config.kernel_setup import test_kernel_connection
        result = asyncio.run(test_kernel_connection())
        if result:
            print("✅ Semantic Kernel test successful")
            return True
        else:
            print("❌ Semantic Kernel test failed")
            return False
    except Exception as e:
        print(f"❌ Semantic Kernel test failed: {e}")
        return False

def test_analyst_agent():
    """Test analyst agent."""
    print("\n🧠 Testing Analyst Agent...")
    
    try:
        from agents.analyst_agent import AnalystAgent
        agent = AnalystAgent()
        
        # Test function loading
        if agent.functions:
            print(f"✅ Loaded {len(agent.functions)} functions")
            return True
        else:
            print("❌ No functions loaded")
            return False
    except Exception as e:
        print(f"❌ Analyst Agent test failed: {e}")
        return False

def test_validator():
    """Test validator agent."""
    print("\n🔍 Testing Validator Agent...")
    
    try:
        from agents.validator import Validator
        validator = Validator()
        
        # Test internal validation
        test_headline = "Capital One Announces New Partnership"
        test_company = "Capital One"
        test_data = {
            'sec_filings': [{'company': 'Capital One', 'text': 'Partnership announced'}],
            'news': [],
            'procurement': []
        }
        
        result = validator.validate_event_internal(test_headline, test_company, test_data)
        print(f"✅ Internal validation: {result}")
        
        return True
    except Exception as e:
        print(f"❌ Validator Agent test failed: {e}")
        return False

def test_archivist():
    """Test archivist agent."""
    print("\n💾 Testing Archivist Agent...")
    
    try:
        from agents.archivist import Archivist
        archivist = Archivist()
        
        # Test saving a sample finding
        sample_finding = {
            'company': 'Test Company',
            'headline': 'Test Event',
            'what_happened': 'Test description',
            'why_it_matters': 'Test impact',
            'consulting_angle': 'Test opportunity',
            'source_url': 'https://example.com',
            'event_type': 'Test',
            'value_usd': 1000000,
            'source_type': 'test'
        }
        
        result = archivist.save_finding(sample_finding)
        print(f"✅ Archivist Agent: {result}")
        
        # Test semantic de-duplication
        print("🧪 Testing semantic de-duplication...")
        archivist.test_semantic_deduplication()
        
        return True
    except Exception as e:
        print(f"❌ Archivist Agent test failed: {e}")
        return False

def test_reporter():
    """Test reporter agent."""
    print("\n📋 Testing Reporter Agent...")
    
    try:
        from agents.reporter import Reporter
        reporter = Reporter()
        
        # Test report generation
        report_content = reporter.generate_report()
        summary = reporter.get_report_summary()
        
        print(f"✅ Reporter Agent: Report generated, {summary.get('total_findings', 0)} findings")
        return True
    except Exception as e:
        print(f"❌ Reporter Agent test failed: {e}")
        return False

def test_integration():
    """Test full integration workflow."""
    print("\n🚀 Testing Full Integration...")
    
    try:
        from main import ResearchOrchestrator
        print("Running full integration test...")
        asyncio.run(ResearchOrchestrator().research_workflow())
        print("✅ Integration test completed")
        return True
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 Agentic Account Research System - Comprehensive Test Suite")
    print("=" * 70)
    print(f"📅 Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Run individual component tests
    tests = [
        ("Environment", test_environment),
        ("Database", test_database),
        ("Semantic Kernel", test_semantic_kernel),
        ("Extractors", test_sam_extractor),
        ("Analyst Agent", test_analyst_agent),
        ("Validation", test_validator),
        ("Archivist", test_archivist),
        ("Reporter", test_reporter),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! System is ready for use.")
        
        # Ask if user wants to run integration test
        response = input("\n🤔 Run full integration test? (y/n): ").lower().strip()
        if response in ['y', 'yes']:
            test_integration()
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        print("💡 Make sure all API keys are set in your .env file")

if __name__ == "__main__":
    main() 