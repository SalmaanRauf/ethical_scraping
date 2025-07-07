import asyncio
import time
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# Import all agent classes
from extractors.sam_extractor import SAMExtractor
from extractors.news_extractor import NewsExtractor
from extractors.sec_extractor import SECExtractor
from agents.analyst_agent import AnalystAgent
from agents.validator import Validator
from agents.archivist import Archivist
from agents.reporter import Reporter

# Import configuration
from config.database_setup import setup_database

class ResearchOrchestrator:
    def __init__(self):
        self.sam_extractor = SAMExtractor()
        self.news_extractor = NewsExtractor()
        self.sec_extractor = SECExtractor()
        self.analyst_agent = AnalystAgent()
        self.validator = Validator()
        self.archivist = Archivist()
        self.reporter = Reporter()

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
            procurement_data = self.sam_extractor.get_all_notices()
            
            print("📰 Extracting news articles...")
            news_data = self.news_extractor.get_all_news()
            
            print("📄 Extracting SEC filings...")
            sec_data = self.sec_extractor.get_recent_filings(days_back=7)
            
            # Combine all raw data
            all_raw_data = procurement_data + news_data + sec_data
            print(f"✅ Data extraction complete: {len(all_raw_data)} total items")
            
            # Save raw data for validation
            self.archivist.save_raw_data(all_raw_data)

            # Step 2: Analysis Phase
            print("\n🧠 PHASE 2: Analysis & Intelligence")
            print("-" * 30)
            
            if all_raw_data:
                print("🤖 Running AI analysis...")
                analyzed_events = await self.analyst_agent.analyze_all_data(all_raw_data)
                print(f"✅ Analysis complete: {len(analyzed_events)} high-impact events identified")
            else:
                print("⚠️  No data to analyze")
                analyzed_events = []

            # Step 3: Validation Phase
            print("\n🔍 PHASE 3: Validation")
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

            # Step 4: Archiving Phase
            print("\n💾 PHASE 4: Archiving")
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
                    elif result == "Repeat":
                        print(f"  🔄 Skipped (repeat): {finding['headline']}")
            else:
                print("⚠️  No findings to archive")

            # Step 5: Reporting Phase
            print("\n📋 PHASE 5: Reporting")
            print("-" * 30)
            
            print("📊 Generating daily report...")
            report_content = self.reporter.generate_report()
            
            # Also generate CSV version
            csv_file = self.reporter.generate_csv_report()
            
            # Get summary
            summary = self.reporter.get_report_summary()
            print(f"📈 Report Summary: {summary.get('total_findings', 0)} findings, ${summary.get('total_value', 0):,} total value")

            # Workflow complete
            end_time = time.time()
            duration = end_time - start_time
            
            print("\n" + "=" * 60)
            print(f"✅ Research workflow complete in {duration:.2f} seconds")
            print(f"📊 Final Stats:")
            print(f"   - Raw data items: {len(all_raw_data)}")
            print(f"   - High-impact events: {len(analyzed_events)}")
            print(f"   - Validated events: {len(validated_events)}")
            print(f"   - Database findings: {summary.get('total_findings', 0)}")
            print("=" * 60)

        except Exception as e:
            print(f"❌ Error in research workflow: {e}")
            import traceback
            traceback.print_exc()

def run_manual_test():
    """Run a single manual test of the workflow."""
    print("🧪 Running manual test of the research workflow...")
    orchestrator = ResearchOrchestrator()
    asyncio.run(orchestrator.research_workflow())
    print("✅ Manual test complete.")

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
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Manual test mode
        run_manual_test()
    elif len(sys.argv) > 1 and sys.argv[1] == "scheduler":
        # Scheduler mode
        setup_scheduler()
    else:
        # Default: run manual test
        print("💡 Usage:")
        print("  python main.py test      - Run manual test")
        print("  python main.py scheduler - Start automated scheduler")
        print("  python main.py           - Run manual test (default)")
        print()
        run_manual_test()
