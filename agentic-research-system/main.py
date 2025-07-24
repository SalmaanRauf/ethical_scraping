import asyncio
import time
import signal
import sys
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# Import shared application context
from services.app_context import app_context

# Import configuration
from config.database_setup import setup_database

class ResearchOrchestrator:
    def __init__(self):
        # Use shared application context instead of creating new instances
        self.app_context = app_context
        
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
        try:
            await self.app_context.cleanup()
            print("✅ Cleanup completed successfully")
        except Exception as e:
            print(f"❌ Error during cleanup: {e}")

    async def research_workflow(self):
        """The main, sequential workflow for the research task."""
        start_time = time.time()
        print("🚀 Starting daily research workflow...")
        print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        try:
            # Ensure app context is initialized
            if not self.app_context.initialized:
                await self.app_context.initialize()
            
            # Step 1: Data Extraction Phase
            print("\n📊 PHASE 1: Data Extraction")
            print("-" * 30)
            
            # Use shared extractors
            sam_extractor = self.app_context.extractors['sam']
            news_extractor = self.app_context.extractors['news']
            sec_extractor = self.app_context.extractors['sec']
            
            # Extract data from all sources
            print("🔍 Extracting SAM.gov procurement notices...")
            procurement_data = await sam_extractor.get_all_notices()
            
            print("📰 Extracting news articles...")
            news_data = await news_extractor.get_all_news()
            
            print("📄 Extracting SEC filings...")
            sec_data = await sec_extractor.get_recent_filings(days_back=7)
            
            # Combine all raw data
            all_raw_data = procurement_data + news_data + sec_data
            print(f"✅ Data extraction complete: {len(all_raw_data)} total items")
            
            # Step 2: Data Consolidation Phase
            print("\n📋 PHASE 2: Data Consolidation")
            print("-" * 30)
            
            # Use shared data consolidator
            data_consolidator = self.app_context.agents['data_consolidator']
            consolidated_result = data_consolidator.process_raw_data(all_raw_data)
            
            if not consolidated_result:
                print("❌ Data consolidation failed")
                return
            
            consolidated_items = consolidated_result.get('consolidated_items', [])
            analysis_document = consolidated_result.get('analysis_document', '')
            
            print(f"✅ Data consolidation complete: {len(consolidated_items)} relevant items")
            
            # Step 3: Analysis Phase
            print("\n🧠 PHASE 3: Analysis")
            print("-" * 30)
            
            # Use shared analyst agent
            analyst_agent = self.app_context.agents['analyst_agent']
            # Set company profiles for the analyst agent
            analyst_agent.set_profiles(self.app_context.profile_loader.load_profiles())
            analyzed_events = await analyst_agent.analyze_consolidated_data(
                consolidated_items, analysis_document
            )
            
            print(f"✅ Analysis complete: {len(analyzed_events)} events identified")
            
            # Step 4: Validation Phase
            print("\n✅ PHASE 4: Validation")
            print("-" * 30)
            
            # Use shared validator
            validator = self.app_context.agents['validator']
            validated_events = await validator.validate_events(analyzed_events)
            
            print(f"✅ Validation complete: {len(validated_events)} events validated")
            
            # Step 5: Archiving Phase
            print("\n📦 PHASE 5: Archiving")
            print("-" * 30)
            
            # Use shared archivist
            archivist = self.app_context.agents['archivist']
            archived_events = await archivist.archive_events(validated_events)
            
            print(f"✅ Archiving complete: {len(archived_events)} events archived")
            
            # Step 6: Reporting Phase
            print("\n📊 PHASE 6: Reporting")
            print("-" * 30)
            
            # Use shared reporter
            reporter = self.app_context.agents['reporter']
            report_content = reporter.generate_report()
            
            print("✅ Report generation complete")
            
            # Final summary
            end_time = time.time()
            duration = end_time - start_time
            print(f"\n🎉 Research workflow completed in {duration:.2f} seconds")
            print(f"📊 Total events processed: {len(archived_events)}")
            
        except Exception as e:
            print(f"❌ Error in research workflow: {e}")
            import traceback
            traceback.print_exc()

def setup_scheduler():
    """Setup the scheduler for automated daily runs."""
    scheduler = BlockingScheduler(timezone="America/Los_Angeles")
    
    # Schedule daily runs at 7:00 AM PT on weekdays
    scheduler.add_job(
        func=lambda: asyncio.run(ResearchOrchestrator().research_workflow()),
        trigger=CronTrigger(day_of_week="mon-fri", hour=7, minute=0),
        id="daily_research",
        name="Daily Research Workflow"
    )
    
    print("⏰ Scheduler configured to run every weekday at 7:00 AM PT")
    print("🔄 Starting scheduler... (Press Ctrl+C to stop)")
    
    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\n🛑 Scheduler stopped by user")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            # Test mode
            asyncio.run(ResearchOrchestrator().research_workflow())
        elif sys.argv[1] == "scheduler":
            # Scheduler mode
            setup_scheduler()
        else:
            print("Usage:")
            print("  python main.py test - Run manual test")
            print("  python main.py scheduler - Start automated scheduler")
    else:
        # Default to test mode
        asyncio.run(ResearchOrchestrator().research_workflow())
