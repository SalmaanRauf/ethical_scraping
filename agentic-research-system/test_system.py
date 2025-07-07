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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REQUIRED_ENV_VARS = [
    "OPENAI_API_KEY",
    "BASE_URL",
    "PROJECT_ID",
    "API_VERSION",
    "MODEL",
    "GOOGLE_SEARCH_API_KEY",
    "GOOGLE_CSE_ID",
    "SEC_API_KEY",
    "MARKETAUX_API_KEY",
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

def test_extractors():
    """Test data extractors."""
    print("\n📊 Testing Data Extractors...")
    
    # Test SAM Extractor
    try:
        from extractors.sam_extractor import SAMExtractor
        sam = SAMExtractor()
        notices = sam.get_all_notices()
        print(f"✅ SAM Extractor: {len(notices)} notices found")
    except Exception as e:
        print(f"❌ SAM Extractor failed: {e}")
    
    # Test News Extractor
    try:
        from extractors.news_extractor import NewsExtractor
        news = NewsExtractor()
        articles = news.get_all_news()
        print(f"✅ News Extractor: {len(articles)} articles found")
    except Exception as e:
        print(f"❌ News Extractor failed: {e}")
    
    # Test SEC Extractor
    try:
        from extractors.sec_extractor import SECExtractor
        sec = SECExtractor()
        filings = sec.get_recent_filings(days_back=1)
        print(f"✅ SEC Extractor: {len(filings)} filings found")
    except Exception as e:
        print(f"❌ SEC Extractor failed: {e}")

def test_analyst_agent():
    """Test the analyst agent."""
    print("\n🧠 Testing Analyst Agent...")
    
    try:
        from agents.analyst_agent import AnalystAgent
        analyst = AnalystAgent()
        print("✅ Analyst Agent initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Analyst Agent test failed: {e}")
        return False

def test_validation():
    """Test validation agent."""
    print("\n🔍 Testing Validation Agent...")
    
    try:
        from agents.validator import Validator
        validator = Validator()
        print("✅ Validation Agent initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Validation Agent test failed: {e}")
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
        from main import run_manual_test
        print("Running full integration test...")
        run_manual_test()
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
        ("Extractors", test_extractors),
        ("Analyst Agent", test_analyst_agent),
        ("Validation", test_validation),
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