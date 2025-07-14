#!/usr/bin/env python3
"""
Standalone test script for SEC Extractor
Quick test to verify API connectivity and data extraction.
"""

import os
import sys
from datetime import datetime

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_sec_extractor_basic():
    """Basic test of SEC extractor functionality."""
    print("🔍 Testing SEC Extractor...")
    
    try:
        from extractors.sec_extractor import SECExtractor
        
        # Check if API key is available
        if not os.getenv("SEC_API_KEY"):
            print("❌ SEC_API_KEY not found in environment variables")
            print("💡 Please add your SEC API key to the .env file")
            return False
        
        # Initialize extractor
        extractor = SECExtractor()
        
        if not extractor.api_key:
            print("❌ Failed to initialize SEC extractor")
            return False
        
        print(f"✅ SEC Extractor initialized with API key")
        print(f"📊 Target tickers: {list(extractor.target_tickers.keys())}")
        
        # Test API connectivity
        print("\n🔗 Testing API connectivity...")
        try:
            # Simple test query
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
            print(f"✅ API connectivity test passed")
            print(f"📊 Response contains {len(result.get('filings', []))} filings")
            
        except Exception as e:
            print(f"❌ API connectivity test failed: {e}")
            return False
        
        # Test data extraction
        print("\n📄 Testing data extraction...")
        try:
            # Get recent filings (last 1 day to minimize API usage)
            filings = extractor.get_recent_filings(days_back=1)
            
            print(f"✅ Data extraction test passed")
            print(f"📊 Found {len(filings)} filings in the last day")
            
            if filings:
                print("\n📋 Sample filing data:")
                sample = filings[0]
                print(f"   Company: {sample.get('company', 'N/A')}")
                print(f"   Ticker: {sample.get('ticker', 'N/A')}")
                print(f"   Type: {sample.get('type', 'N/A')}")
                print(f"   Filed: {sample.get('filedAt', 'N/A')}")
                print(f"   Text length: {len(sample.get('text', ''))} characters")
            
        except Exception as e:
            print(f"❌ Data extraction test failed: {e}")
            return False
        
        # Test full extraction method
        print("\n🔄 Testing full extraction method...")
        try:
            all_filings = extractor.get_filings_and_text()
            print(f"✅ Full extraction test passed")
            print(f"📊 Total filings found: {len(all_filings)}")
            
        except Exception as e:
            print(f"❌ Full extraction test failed: {e}")
            return False
        
        print("\n🎉 All SEC Extractor tests passed!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure all dependencies are installed")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_sec_extractor_detailed():
    """Detailed test with more comprehensive checks."""
    print("\n" + "="*50)
    print("🔍 Detailed SEC Extractor Test")
    print("="*50)
    
    try:
        from extractors.sec_extractor import SECExtractor
        
        extractor = SECExtractor()
        
        # Test configuration
        print(f"📊 Target Companies:")
        for ticker, company in extractor.target_tickers.items():
            print(f"   {ticker}: {company}")
        
        # Test query building
        print(f"\n🔍 Query Structure:")
        ticker_list = " OR ".join([f'ticker:"{ticker}"' for ticker in extractor.target_tickers.keys()])
        print(f"   Ticker query: {ticker_list}")
        
        # Test recent filings with different time ranges
        print(f"\n📅 Testing different time ranges:")
        for days in [1, 3, 7]:
            try:
                filings = extractor.get_recent_filings(days_back=days)
                print(f"   {days} day(s): {len(filings)} filings")
            except Exception as e:
                print(f"   {days} day(s): Error - {e}")
        
        # Test data quality
        print(f"\n📋 Data Quality Check:")
        filings = extractor.get_recent_filings(days_back=7)
        
        if filings:
            # Check for required fields
            required_fields = ['company', 'ticker', 'type', 'filedAt', 'link', 'text', 'source', 'data_type']
            missing_fields = []
            
            for field in required_fields:
                if not all(field in filing for filing in filings):
                    missing_fields.append(field)
            
            if missing_fields:
                print(f"   ❌ Missing fields: {missing_fields}")
            else:
                print(f"   ✅ All required fields present")
            
            # Check data types
            print(f"   📊 Sample data types:")
            sample = filings[0]
            for field, value in sample.items():
                print(f"      {field}: {type(value).__name__} = {str(value)[:50]}{'...' if len(str(value)) > 50 else ''}")
        
        print(f"\n✅ Detailed test completed")
        
    except Exception as e:
        print(f"❌ Detailed test failed: {e}")


def main():
    """Run all SEC extractor tests."""
    print("🧪 SEC Extractor Test Suite")
    print("="*40)
    print(f"📅 Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run basic test
    basic_success = test_sec_extractor_basic()
    
    if basic_success:
        # Run detailed test
        test_sec_extractor_detailed()
        
        print(f"\n🎉 All tests completed successfully!")
        print(f"💡 The SEC extractor is ready for use in the main system")
    else:
        print(f"\n❌ Basic test failed. Please check your configuration.")
        print(f"💡 Make sure SEC_API_KEY is set in your .env file")


if __name__ == "__main__":
    main() 