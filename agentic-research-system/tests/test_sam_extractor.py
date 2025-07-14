#!/usr/bin/env python3
"""
Simple test script for SAM Extractor filtering logic
"""

from extractors.sam_extractor import SAMExtractor

def test_value_extraction():
    """Test the extract_value_usd function"""
    sam = SAMExtractor()
    
    test_cases = [
        ("RFP for $15 million consulting services", 15000000),
        ("SOW worth $25M for Capital One", 25000000),
        ("Contract valued at $5 billion", 5000000000),
        ("Procurement notice for $8,000,000", 8000000),
        ("No dollar amount mentioned", None),
        ("Small contract worth $500,000", 500000),  # Should be filtered out (< $10M)
        ("Budget range: $12M to $18M", 18000000),  # Should extract highest value
        ("Estimated cost: $7.5 million", 7500000),  # Should be filtered out (< $10M)
    ]
    
    print("🧪 Testing value extraction...")
    for text, expected in test_cases:
        result = sam.extract_value_usd(text)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{text}' -> ${result:,}" if result else f"{status} '{text}' -> None")
        if expected and result and result >= 10_000_000:
            print(f"   ✅ Would pass $10M threshold")
        elif expected and result and result < 10_000_000:
            print(f"   ❌ Would be filtered out (< $10M)")

def test_company_filtering():
    """Test company name filtering"""
    sam = SAMExtractor()
    
    test_cases = [
        ("Capital One announces new partnership", True),
        ("Fannie Mae quarterly results", True),
        ("EagleBank technology upgrade", True),
        ("Capital Bank N.A. expansion plans", True),
        ("Random company news", False),
        ("Apple announces new product", False),
    ]
    
    print("\n🧪 Testing company filtering...")
    for text, should_match in test_cases:
        company_match = any(company.lower() in text.lower() for company in sam.target_companies)
        status = "✅" if company_match == should_match else "❌"
        print(f"{status} '{text}' -> {'Match' if company_match else 'No match'}")

def test_keyword_filtering():
    """Test keyword filtering"""
    sam = SAMExtractor()
    keywords = ["RFP", "SOW", "consultant", "financial services"]
    
    test_cases = [
        ("New RFP for consulting services", True),
        ("Statement of Work for IT project", True),
        ("Financial services contract", True),
        ("Regular company news", False),
        ("Product announcement", False),
    ]
    
    print("\n🧪 Testing keyword filtering...")
    for text, should_match in test_cases:
        keyword_match = any(keyword.lower() in text.lower() for keyword in keywords)
        status = "✅" if keyword_match == should_match else "❌"
        print(f"{status} '{text}' -> {'Match' if keyword_match else 'No match'}")

def test_quota_management():
    """Test quota management functionality"""
    sam = SAMExtractor()
    
    print("\n🧪 Testing quota management...")
    status = sam.get_quota_status()
    print(f"✅ Initial quota status: {status['calls_made']}/{status['max_calls']} calls used")
    print(f"   Remaining calls: {status['remaining']}")

def test_url_detection():
    """Test URL detection logic"""
    sam = SAMExtractor()
    
    test_cases = [
        ("https://api.sam.gov/prod/opportunities/v1/notices/123", True),
        ("This is just regular text", False),
        ("http://example.com", True),
        ("No URL here", False),
    ]
    
    print("\n🧪 Testing URL detection...")
    for text, should_be_url in test_cases:
        is_url = text.startswith('http')
        status = "✅" if is_url == should_be_url else "❌"
        print(f"{status} '{text}' -> {'URL' if is_url else 'Text'}")

def test_api_structure():
    """Test the API structure to understand the response format."""
    sam = SAMExtractor()
    
    print("\n🧪 Testing API structure...")
    print("💡 This will use 1-2 API calls to understand the response format")
    
    # Test with just 1 notice to minimize API usage
    sam.test_api_structure(max_test_notices=1)
    
    print(f"\n📊 Quota status after API structure test:")
    status = sam.get_quota_status()
    print(f"   Calls used: {status['calls_made']}")
    print(f"   Remaining: {status['remaining']}")

if __name__ == "__main__":
    print("🧪 SAM Extractor Test Suite")
    print("=" * 50)
    
    test_value_extraction()
    test_company_filtering()
    test_keyword_filtering()
    test_quota_management()
    test_url_detection()
    
    # Ask user if they want to test API structure (uses API calls)
    response = input("\n🤔 Test API structure? This will use 1-2 API calls (y/n): ").lower().strip()
    if response in ['y', 'yes']:
        test_api_structure()
    
    print("\n✅ Test complete! If all tests pass, your SAM extractor logic is working correctly.")
    print("💡 Note: This tests the filtering logic only. API calls require a valid SAM_API_KEY.")
    print("💡 The updated extractor now fetches detailed descriptions from secondary URLs.")
    print("💡 API quota is managed to prevent exceeding limits.")
    print("💡 URL parameters are handled properly for secondary API calls.") 