#!/usr/bin/env python3
"""
Real-world integration tests for AnalystAgent
Tests complete workflow with actual API calls and data sources.
"""

import os
import sys
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.analyst_agent import AnalystAgent
from extractors.news_extractor import NewsExtractor
from extractors.sec_extractor import SECExtractor
from extractors.sam_extractor import SAMExtractor


class TestAnalystAgentIntegration:
    """Integration tests for AnalystAgent with real API calls."""
    
    def __init__(self):
        """Initialize the integration test suite."""
        self.setup_logging()
        self.check_environment()
        self.analyst = None
        self.test_data = []
        
    def setup_logging(self):
        """Setup logging for the integration tests."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('integration_test.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def check_environment(self):
        """Check that required environment variables are set."""
        required_vars = [
            'OPENAI_API_KEY',
            'GNEWS_API_KEY',
            'SEC_API_KEY',
            'SAM_API_KEY'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            self.logger.error(f"❌ Missing required environment variables: {missing_vars}")
            self.logger.error("Please set these variables in your .env file")
            raise EnvironmentError(f"Missing environment variables: {missing_vars}")
        
        self.logger.info("✅ All required environment variables are set")
    
    async def setup_analyst_agent(self):
        """Initialize the AnalystAgent with test configuration."""
        try:
            self.logger.info("🔧 Setting up AnalystAgent...")
            
            # Use smaller chunk sizes for testing to reduce API costs
            self.analyst = AnalystAgent(
                chunk_size=1500,  # Smaller chunks for testing
                chunk_overlap=200,
                max_chunks=3      # Limit chunks for testing
            )
            
            self.logger.info("✅ AnalystAgent initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize AnalystAgent: {e}")
            return False
    
    def generate_test_data(self):
        """Generate realistic test data from multiple sources."""
        self.logger.info("📊 Generating test data from multiple sources...")
        
        test_data = []
        
        # 1. News data (simulated)
        news_data = [
            {
                'company': 'Capital One',
                'title': 'Capital One Announces $100M Investment in Fintech Startup',
                'text': 'Capital One Financial Corporation today announced a $100 million strategic investment in a leading fintech startup focused on digital banking solutions. The investment represents Capital One\'s continued commitment to innovation and digital transformation in the financial services industry.',
                'source': 'news',
                'type': 'news',
                'published_date': datetime.now().isoformat()
            },
            {
                'company': 'Fannie Mae',
                'title': 'Fannie Mae Reports Strong Q4 Earnings with $50M in New Initiatives',
                'text': 'Fannie Mae today reported fourth-quarter earnings that exceeded analyst expectations. The company announced $50 million in new technology initiatives aimed at improving mortgage processing efficiency and reducing costs for lenders and borrowers.',
                'source': 'news',
                'type': 'news',
                'published_date': datetime.now().isoformat()
            },
            {
                'company': 'Navy Federal Credit Union',
                'title': 'Navy Federal Credit Union Seeks IT Consulting Services Worth $25M',
                'text': 'Navy Federal Credit Union has issued a Request for Proposals (RFP) for comprehensive IT consulting services valued at approximately $25 million. The project aims to modernize the credit union\'s digital infrastructure and enhance member services.',
                'source': 'news',
                'type': 'news',
                'published_date': datetime.now().isoformat()
            }
        ]
        
        # 2. SEC filing data (simulated)
        sec_data = [
            {
                'company': 'Capital One',
                'title': 'Capital One 8-K Filing: Major Investment Announcement',
                'text': 'Pursuant to Section 13 or 15(d) of the Securities Exchange Act of 1934, Capital One Financial Corporation (the "Company") hereby furnishes the following information. The Company today announced a strategic investment of $100 million in a fintech startup. This investment aligns with the Company\'s digital transformation strategy and represents a significant opportunity for growth in the digital banking sector.',
                'source': 'SEC',
                'type': 'filing',
                'filedAt': datetime.now().isoformat()
            },
            {
                'company': 'Freddie Mac',
                'title': 'Freddie Mac 10-K Filing: Annual Report with Technology Investments',
                'text': 'Freddie Mac\'s annual report discloses significant technology investments totaling $75 million in digital mortgage platforms and automated underwriting systems. These investments are expected to improve operational efficiency and reduce processing times for mortgage applications.',
                'source': 'SEC',
                'type': 'filing',
                'filedAt': datetime.now().isoformat()
            }
        ]
        
        # 3. Procurement data (simulated)
        procurement_data = [
            {
                'company': 'Navy Federal Credit Union',
                'title': 'IT Consulting Services RFP - Navy Federal Credit Union',
                'text': 'Navy Federal Credit Union is seeking proposals for comprehensive IT consulting services. The project includes digital transformation consulting, system architecture design, and implementation support. Estimated contract value: $25 million. Response deadline: 30 days from posting.',
                'source': 'procurement',
                'type': 'procurement',
                'value_usd': 25000000
            },
            {
                'company': 'PenFed Credit Union',
                'title': 'Cybersecurity Consulting Services RFP',
                'text': 'PenFed Credit Union is seeking cybersecurity consulting services to enhance its security infrastructure. The project includes security assessment, threat modeling, and implementation of advanced security measures. Estimated contract value: $15 million.',
                'source': 'procurement',
                'type': 'procurement',
                'value_usd': 15000000
            }
        ]
        
        test_data.extend(news_data)
        test_data.extend(sec_data)
        test_data.extend(procurement_data)
        
        self.test_data = test_data
        self.logger.info(f"✅ Generated {len(test_data)} test data items")
        
        return test_data
    
    async def test_triage_functionality(self):
        """Test the triage functionality with real data."""
        self.logger.info("🔍 Testing triage functionality...")
        
        try:
            # Test with a mix of relevant and irrelevant data
            test_items = [
                {
                    'company': 'Capital One',
                    'title': 'Capital One Announces Major Investment',
                    'text': 'Capital One announced a $100 million investment in fintech.',
                    'source': 'news',
                    'type': 'news'
                },
                {
                    'company': 'Generic Corp',
                    'title': 'Weather Report for Today',
                    'text': 'Today\'s weather will be sunny with a high of 75 degrees.',
                    'source': 'news',
                    'type': 'news'
                }
            ]
            
            result = await self.analyst.triage_data(test_items)
            
            # Should filter out irrelevant items
            self.logger.info(f"📊 Triage processed {len(test_items)} items, returned {len(result)} relevant items")
            
            # STRICT: Fail if no relevant items found
            assert len(result) > 0, "Triage should find at least one relevant item in synthetic data!"
            
            if result:
                self.logger.info("✅ Triage functionality working correctly")
                return True
            else:
                self.logger.warning("⚠️  Triage returned no relevant items (this might be expected)")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Triage test failed: {e}")
            return False
    
    async def test_financial_analysis(self):
        """Test financial event analysis with real data."""
        self.logger.info("💰 Testing financial event analysis...")
        
        try:
            # Filter test data for news items
            news_items = [item for item in self.test_data if item.get('type') == 'news']
            
            if not news_items:
                self.logger.warning("⚠️  No news items found for financial analysis test")
                return True
            
            result = await self.analyst.analyze_financial_events(news_items)
            
            self.logger.info(f"📊 Financial analysis processed {len(news_items)} items, found {len(result)} events")
            
            # STRICT: Fail if no events found
            assert len(result) > 0, "Financial analysis should find at least one event in synthetic data!"
            
            if result:
                for event in result:
                    self.logger.info(f"   💰 Found financial event: {event.get('event_type', 'Unknown')} - ${event.get('value_usd', 0):,}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Financial analysis test failed: {e}")
            return False
    
    async def test_procurement_analysis(self):
        """Test procurement analysis with real data."""
        self.logger.info("📋 Testing procurement analysis...")
        
        try:
            # Filter test data for procurement items
            procurement_items = [item for item in self.test_data if item.get('type') == 'procurement']
            
            if not procurement_items:
                self.logger.warning("⚠️  No procurement items found for analysis test")
                return True
            
            result = await self.analyst.analyze_procurement(procurement_items)
            
            self.logger.info(f"📊 Procurement analysis processed {len(procurement_items)} items, found {len(result)} events")
            
            # STRICT: Fail if no events found
            assert len(result) > 0, "Procurement analysis should find at least one event in synthetic data!"
            
            if result:
                for event in result:
                    self.logger.info(f"   📋 Found procurement event: {event.get('event_type', 'Unknown')} - ${event.get('value_usd', 0):,}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Procurement analysis test failed: {e}")
            return False
    
    async def test_earnings_analysis(self):
        """Test earnings call analysis with real data."""
        self.logger.info("📈 Testing earnings call analysis...")
        
        try:
            # Filter test data for SEC filings
            sec_items = [item for item in self.test_data if item.get('type') == 'filing']
            
            if not sec_items:
                self.logger.warning("⚠️  No SEC filings found for earnings analysis test")
                return True
            
            result = await self.analyst.analyze_earnings_calls(sec_items)
            
            self.logger.info(f"📊 Earnings analysis processed {len(sec_items)} items, found {len(result)} events")
            
            # STRICT: Fail if no events found
            assert len(result) > 0, "Earnings analysis should find at least one event in synthetic data!"
            
            if result:
                for event in result:
                    self.logger.info(f"   📈 Found earnings event: {event.get('event_type', 'Unknown')} - ${event.get('value_usd', 0):,}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Earnings analysis test failed: {e}")
            return False
    
    async def test_insight_generation(self):
        """Test insight generation with real data."""
        self.logger.info("🧠 Testing insight generation...")
        
        try:
            # Create sample events for insight generation
            sample_events = [
                {
                    'company': 'Capital One',
                    'event_type': 'Investment',
                    'value_usd': 100000000,
                    'summary': 'Capital One invests $100M in fintech startup'
                },
                {
                    'company': 'Navy Federal Credit Union',
                    'event_type': 'Procurement',
                    'value_usd': 25000000,
                    'summary': 'Navy Federal seeks IT consulting services worth $25M'
                }
            ]
            
            result = await self.analyst.generate_insights(sample_events)
            
            self.logger.info(f"📊 Insight generation processed {len(sample_events)} events, generated {len(result)} insights")
            
            # STRICT: Fail if no insights generated
            assert len(result) > 0, "Insight generation should produce at least one insight for synthetic data!"
            
            if result:
                for insight in result:
                    self.logger.info(f"   🧠 Generated insight for {insight.get('company', 'Unknown')}: {insight.get('headline', 'No headline')}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Insight generation test failed: {e}")
            return False
    
    async def test_complete_workflow(self):
        """Test the complete analysis workflow end-to-end."""
        self.logger.info("🚀 Testing complete analysis workflow...")
        
        try:
            # Use a subset of test data to avoid excessive API calls
            workflow_data = self.test_data[:5]  # Use first 5 items
            
            self.logger.info(f"📊 Starting complete workflow with {len(workflow_data)} data items")
            
            result = await self.analyst.analyze_all_data(workflow_data)
            
            self.logger.info(f"📊 Complete workflow processed {len(workflow_data)} items, generated {len(result)} final results")
            
            # STRICT: Fail if no results
            assert len(result) > 0, "Complete workflow should produce at least one result for synthetic data!"
            
            if result:
                for i, event in enumerate(result, 1):
                    self.logger.info(f"   📋 Result {i}: {event.get('company', 'Unknown')} - {event.get('headline', 'No headline')}")
                    
                    # Check for required fields
                    insights = event.get('insights', {})
                    if insights:
                        self.logger.info(f"      💡 What happened: {insights.get('what_happened', 'N/A')[:100]}...")
                        self.logger.info(f"      💡 Why it matters: {insights.get('why_it_matters', 'N/A')[:100]}...")
                        self.logger.info(f"      💡 Consulting angle: {insights.get('consulting_angle', 'N/A')[:100]}...")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Complete workflow test failed: {e}")
            return False
    
    async def test_real_data_sources(self):
        """Test with real data from actual sources (limited scope)."""
        self.logger.info("🌐 Testing with real data sources...")
        
        try:
            # Test with a small amount of real data to avoid excessive API usage
            real_data = []
            
            # Try to get a small amount of real news data
            try:
                news_extractor = NewsExtractor()
                real_news = news_extractor.get_all_news()
                if real_news:
                    real_data.extend(real_news[:2])  # Use only 2 items
                    self.logger.info(f"📰 Added {len(real_news[:2])} real news items")
            except Exception as e:
                self.logger.warning(f"⚠️  Could not fetch real news data: {e}")
            
            # Try to get a small amount of real SEC data
            try:
                sec_extractor = SECExtractor()
                real_sec = sec_extractor.get_recent_filings(days_back=7)
                if real_sec:
                    real_data.extend(real_sec[:2])  # Use only 2 items
                    self.logger.info(f"📄 Added {len(real_sec[:2])} real SEC filings")
            except Exception as e:
                self.logger.warning(f"⚠️  Could not fetch real SEC data: {e}")
            
            if not real_data:
                self.logger.warning("⚠️  No real data available for testing")
                return True
            
            self.logger.info(f"📊 Testing with {len(real_data)} real data items")
            
            # Run a quick analysis on real data
            result = await self.analyst.analyze_all_data(real_data)
            
            self.logger.info(f"📊 Real data analysis completed, generated {len(result)} results")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Real data test failed: {e}")
            return False
    
    async def run_all_tests(self):
        """Run all integration tests."""
        self.logger.info("🧪 Starting AnalystAgent Integration Tests")
        self.logger.info("=" * 60)
        
        test_results = {}
        
        # Setup
        if not await self.setup_analyst_agent():
            self.logger.error("❌ Failed to setup AnalystAgent, aborting tests")
            return False
        
        # Generate test data
        self.generate_test_data()
        
        # Run individual tests
        tests = [
            ("Triage Functionality", self.test_triage_functionality),
            ("Financial Analysis", self.test_financial_analysis),
            ("Procurement Analysis", self.test_procurement_analysis),
            ("Earnings Analysis", self.test_earnings_analysis),
            ("Insight Generation", self.test_insight_generation),
            ("Complete Workflow", self.test_complete_workflow),
            ("Real Data Sources", self.test_real_data_sources)
        ]
        
        for test_name, test_func in tests:
            self.logger.info(f"\n🔍 Running: {test_name}")
            try:
                result = await test_func()
                test_results[test_name] = result
                status = "✅ PASSED" if result else "❌ FAILED"
                self.logger.info(f"{status}: {test_name}")
            except Exception as e:
                self.logger.error(f"❌ FAILED: {test_name} - Exception: {e}")
                test_results[test_name] = False
        
        # Summary
        self.logger.info("\n" + "=" * 60)
        self.logger.info("📊 INTEGRATION TEST SUMMARY")
        self.logger.info("=" * 60)
        
        passed = sum(1 for result in test_results.values() if result)
        total = len(test_results)
        
        for test_name, result in test_results.items():
            status = "✅ PASSED" if result else "❌ FAILED"
            self.logger.info(f"{status}: {test_name}")
        
        self.logger.info(f"\n📈 Overall Result: {passed}/{total} tests passed")
        
        if passed == total:
            self.logger.info("🎉 ALL INTEGRATION TESTS PASSED!")
            return True
        else:
            self.logger.error("❌ SOME INTEGRATION TESTS FAILED!")
            return False


async def main():
    """Main function to run integration tests."""
    tester = TestAnalystAgentIntegration()
    success = await tester.run_all_tests()
    
    if success:
        print("\n🎉 Integration tests completed successfully!")
    else:
        print("\n❌ Integration tests failed!")
        exit(1)


if __name__ == '__main__':
    asyncio.run(main()) 