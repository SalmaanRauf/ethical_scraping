#!/usr/bin/env python3
"""
Test script for the updated news extractor implementation.
Tests the RSS feeds (company-specific + regulatory) and GNews API for all companies.
"""

import os
import sys
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "agentic-research-system"))

def test_news_extractor():
    """Test the updated news extractor implementation."""
    print("🧪 Testing Updated News Extractor Implementation")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    
    # Check API key
    gnews_api_key = os.getenv("GNEWS_API_KEY")
    if not gnews_api_key:
        print("❌ GNEWS_API_KEY not found in environment variables")
        print("   Please add it to your .env file")
        return False
    
    print("✅ GNEWS_API_KEY found")
    
    try:
        from extractors.news_extractor import NewsExtractor
        
        # Initialize the extractor
        extractor = NewsExtractor()
        print("✅ NewsExtractor initialized successfully")
        
        # Test RSS feeds configuration
        print(f"\n📰 RSS Feeds configured:")
        for source, url in extractor.rss_feeds.items():
            print(f"   - {source}: {url}")
        
        # Test API targets (now includes ALL companies)
        print(f"\n🔍 GNews API Targets (ALL companies):")
        for company in extractor.api_targets:
            print(f"   - {company}")
        
        # Test RSS fetching (limited test)
        print(f"\n🔍 Testing RSS feeds...")
        rss_articles = extractor.fetch_from_rss()
        print(f"✅ RSS test completed: {len(rss_articles)} articles found")
        
        # Test GNews API (limited test)
        print(f"\n🔍 Testing GNews API for all companies...")
        api_articles = extractor.fetch_from_gnews()
        print(f"✅ GNews API test completed: {len(api_articles)} articles found")
        
        # Test combined functionality
        print(f"\n🔍 Testing combined news gathering...")
        all_news = extractor.get_all_news()
        print(f"✅ Combined test completed: {len(all_news)} total articles")
        
        # Show sample data structure
        if all_news:
            sample = all_news[0]
            print(f"\n📋 Sample article structure:")
            for key, value in sample.items():
                print(f"   {key}: {str(value)[:100]}{'...' if len(str(value)) > 100 else ''}")
        
        # Show breakdown by source
        rss_count = len(rss_articles)
        api_count = len(api_articles)
        print(f"\n📊 Summary:")
        print(f"   📰 RSS Articles: {rss_count}")
        print(f"   🔍 GNews API Articles: {api_count}")
        print(f"   📈 Total Articles: {len(all_news)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_news_extractor()
    if success:
        print("\n🎉 Updated news extractor test completed successfully!")
        print("✅ Hybrid approach working: RSS + GNews API for all companies")
    else:
        print("\n❌ Updated news extractor test failed!")
        sys.exit(1) 