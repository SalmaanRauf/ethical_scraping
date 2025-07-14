import asyncio
import time
import signal
import sys
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# Import all agent classes
from extractors.sam_extractor import SAMExtractor
from extractors.news_extractor import NewsExtractor
from extractors.sec_extractor import SECExtractor
from agents.scraper_agent import ScraperAgent
from agents.analyst_agent import AnalystAgent
from agents.validator import Validator
from agents.archivist import Archivist
from agents.reporter import Reporter
from agents.data_consolidator import DataConsolidator

# Import configuration
from config.database_setup import setup_database

class ResearchOrchestrator:
    def __init__(self):
        # Initialize scraper agent for enhanced data extraction
        self.scraper_agent = ScraperAgent()
        
        # Initialize extractors with scraper agent
        self.sam_extractor = SAMExtractor(scraper_agent=self.scraper_agent)
        self.news_extractor = NewsExtractor(scraper_agent=self.scraper_agent)
        self.sec_extractor = SECExtractor(scraper_agent=self.scraper_agent)
        
        # Initialize other agents
        self.data_consolidator = DataConsolidator()
        self.analyst_agent = AnalystAgent()
        self.validator = Validator()
        self.archivist = Archivist()
        self.reporter = Reporter()
        
        # Setup graceful shutdown
        self._setup_shutdown_handlers()

    def _setup_shutdown_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            print(f"\n🛑 Received signal {signum}, shutting down gracefully...")
            asyncio.create_task(self._cleanup())
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def _cleanup(self):
        """Clean up resources on shutdown."""
        cleanup_tasks = []
        
        if hasattr(self, 'scraper_agent') and self.scraper_agent:
            cleanup_tasks.append(self.scraper_agent.close())
        
        # Add other cleanup tasks as needed
        # Future: Add cleanup for other async resources like database connections
        
        if cleanup_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*cleanup_tasks, return_exceptions=True),
                    timeout=30.0
                )
                print("✅ Cleanup completed successfully")
            except asyncio.TimeoutError:
                print("⚠️  Cleanup timed out after 30 seconds")
            except Exception as e:
                print(f"❌ Error during cleanup: {e}")

    async def research_workflow(self):
        """The main, sequential workflow for the research task."""
        start_time = time.time()
        print("🚀 Starting daily research workflow...")
        print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        try:
            # Step 1: Data Extraction Phase
            print("\n📊 PHASE 1: Data Extraction")
            print("-" * 30)
            
            # Extract data from all sources
            print("🔍 Extracting SAM.gov procurement notices...")
            procurement_data = await self.sam_extractor.get_all_notices()
            
            print("📰 Extracting news articles...")
            news_data = await self.news_extractor.get_all_news()
            
            print("📄 Extracting SEC filings...")
            sec_data = await self.sec_extractor.get_recent_filings(days_back=7)
            
            # Combine all raw data
            all_raw_data = procurement_data + news_data + sec_data
            print(f"✅ Data extraction complete: {len(all_raw_data)} total items")
            
            # Save raw data for validation
            self.archivist.save_raw_data(all_raw_data)

            # Step 2: Data Consolidation Phase
            print("\n📋 PHASE 2: Data Consolidation")
            print("-" * 30)
            
            if all_raw_data:
                print("🔄 Consolidating and filtering data...")
                consolidation_result = self.data_consolidator.process_raw_data(all_raw_data)
                consolidated_items = consolidation_result['consolidated_items']
                analysis_document = consolidation_result['analysis_document']
                
                print(f"✅ Consolidation complete: {len(consolidated_items)} relevant items identified")
                print(f"📄 Analysis document created: {consolidation_result['files'].get('markdown_file', 'N/A')}")
                
                # Save the analysis document for reference
                if consolidation_result['files'].get('markdown_file'):
                    print(f"💾 Document saved to: {consolidation_result['files']['markdown_file']}")
            else:
                print("⚠️  No data to consolidate")
                consolidated_items = []
                analysis_document = "# No data available for analysis"

            # Step 3: Analysis Phase
            print("\n🧠 PHASE 3: Analysis & Intelligence")
            print("-" * 30)
            
            if consolidated_items:
                print("🤖 Running AI analysis on consolidated data...")
                # Pass the analysis document to the analyst agent
                analyzed_events = await self.analyst_agent.analyze_consolidated_data(consolidated_items, analysis_document)
                print(f"✅ Analysis complete: {len(analyzed_events)} high-impact events identified")
            else:
                print("⚠️  No relevant data to analyze")
                analyzed_events = []

            # Step 4: Validation Phase
            print("\n🔍 PHASE 4: Validation")
            print("-" * 30)
            
            if analyzed_events:
                print("🔍 Validating events...")
                # Prepare internal data for validation
                internal_data = {
                    'sec_filings': sec_data,
                    'news': news_data,
                    'procurement': procurement_data
                }
                
                validated_events = self.validator.validate_all_events(analyzed_events, internal_data)
                print(f"✅ Validation complete: {len(validated_events)} events validated")
            else:
                print("⚠️  No events to validate")
                validated_events = []

            # Step 5: Archiving Phase
            print("\n💾 PHASE 5: Archiving")
            print("-" * 30)
            
            if validated_events:
                print("💾 Saving validated findings...")
                for event in validated_events:
                    # Prepare finding for database
                    finding = {
                        'company': event.get('company', ''),
                        'headline': event.get('title', event.get('headline', '')),
                        'what_happened': event.get('insights', {}).get('what_happened', ''),
                        'why_it_matters': event.get('insights', {}).get('why_it_matters', ''),
                        'consulting_angle': event.get('insights', {}).get('consulting_angle', ''),
                        'source_url': event.get('link', event.get('source_url', '')),
                        'event_type': event.get('financial_analysis', {}).get('event_type', 
                                           event.get('procurement_analysis', {}).get('title', '')),
                        'value_usd': event.get('financial_analysis', {}).get('value_usd', 
                                           event.get('procurement_analysis', {}).get('value_usd', 0)),
                        'source_type': event.get('source', '')
                    }
                    
                    result = self.archivist.save_finding(finding)
                    if result == "New":
                        print(f"  ✅ Saved: {finding['headline']}")
                    elif result == "SemanticDuplicate":
                        print(f"  🔄 Skipped (semantic duplicate): {finding['headline']}")
                    elif result == "ExactDuplicate":
                        print(f"  🔄 Skipped (exact duplicate): {finding['headline']}")
                    else:
                        print(f"  ⚠️  {result}: {finding['headline']}")
            else:
                print("⚠️  No findings to archive")

            # Step 6: Reporting Phase
            print("\n📋 PHASE 6: Reporting")
            print("-" * 30)
            
            print("📊 Generating daily report...")
            report_content = self.reporter.generate_report()
            
            # Also generate CSV version
            csv_file = self.reporter.generate_csv_report()
            
            # Get summary
            summary = self.reporter.get_report_summary()
            
            # Print summary
            print(f"\n📈 Daily Summary:")
            print(f"   Total Findings: {summary.get('total_findings', 0)}")
            print(f"   Total Value: ${summary.get('total_value', 0):,}")
            if summary.get('event_breakdown'):
                print(f"   Event Types: {', '.join([f'{k} ({v})' for k, v in summary['event_breakdown'].items()])}")

        except Exception as e:
            print(f"❌ Error in research workflow: {e}")
            # Log the error but don't raise to prevent scheduler from stopping
            import traceback
            print(f"📋 Full traceback: {traceback.format_exc()}")
            # Return gracefully instead of raising
            return False

        finally:
            end_time = time.time()
            duration = end_time - start_time
            print(f"\n⏱️  Workflow completed in {duration:.2f} seconds")
            print("=" * 60)
            return True

def setup_scheduler():
    """Setup the scheduler for automated daily runs."""
    scheduler = BlockingScheduler(timezone="America/Los_Angeles")
    
    # Schedule to run every weekday at 7:00 AM Pacific Time
    scheduler.add_job(
        lambda: asyncio.run(ResearchOrchestrator().research_workflow()),
        CronTrigger(day_of_week='mon-fri', hour=7, minute=0),
        id='daily_research',
        name='Daily Research Workflow'
    )
    
    print("⏰ Scheduler configured to run every weekday at 7:00 AM PT")
    print("🔄 Press Ctrl+C to exit")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\n🛑 Scheduler stopped by user")

if __name__ == "__main__":
    # Setup database first
    print("🗄️  Setting up database...")
    setup_database()
    
    # Check command line arguments for mode
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Manual test mode
        asyncio.run(ResearchOrchestrator().research_workflow())
    else:
        # Default: run manual test
        print("💡 Usage:")
        print("  python main.py test - Run manual test")
        print("  python main.py      - Run manual test (default)")
        print()
        asyncio.run(ResearchOrchestrator().research_workflow())
