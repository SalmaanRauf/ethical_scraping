# Agentic Account Research System - Build Log (Tasks 16-17)

---

## Begin Task 16: Implement Archivist, Validator, and Reporter Agents

**Description:**
Create the Archivist agent for database operations and deduplication, the Validator agent for internal/external validation, and the Reporter agent for generating daily reports.

**File:** `agents/archivist.py`
```python
import sqlite3
import hashlib
from datetime import datetime
from typing import Dict, Any, List

class Archivist:
    def __init__(self, db_path='data/research.db'):
        self.db_path = db_path

    def _generate_hash(self, headline: str, company: str) -> str:
        """Creates a unique hash for an event."""
        content = f"{headline.strip()}{company.strip()}".encode('utf-8')
        return hashlib.md5(content).hexdigest()

    def save_finding(self, finding: Dict[str, Any]) -> str:
        """Saves a new finding to the database if it doesn't exist."""
        event_hash = self._generate_hash(finding['headline'], finding['company'])

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Check for existence
            cursor.execute("SELECT id FROM findings WHERE event_hash = ?", (event_hash,))
            if cursor.fetchone():
                print(f"🔄 Event '{finding['headline']}' is a repeat. Skipping save.")
                conn.close()
                return "Repeat"

            # Insert new record
            cursor.execute("""
                INSERT INTO findings (
                    event_hash, date_found, company, headline, what_happened, 
                    why_it_matters, consulting_angle, source_url, event_type, 
                    value_usd, source_type
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_hash, 
                datetime.now().isoformat(), 
                finding['company'], 
                finding['headline'], 
                finding.get('what_happened', ''),
                finding.get('why_it_matters', ''),
                finding.get('consulting_angle', ''),
                finding.get('source_url', ''),
                finding.get('event_type', ''),
                finding.get('value_usd', 0),
                finding.get('source_type', '')
            ))

            conn.commit()
            print(f"✅ Saved new finding: {finding['headline']}")
            return "New"
            
        except Exception as e:
            print(f"❌ Error saving finding: {e}")
            conn.rollback()
            return "Error"
        finally:
            conn.close()

    def save_raw_data(self, data_items: List[Dict[str, Any]]) -> None:
        """Save raw data for validation purposes."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            for item in data_items:
                cursor.execute("""
                    INSERT INTO raw_data (
                        date_collected, data_type, company, title, content, 
                        source_url, source_type
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(),
                    item.get('type', 'unknown'),
                    item.get('company', ''),
                    item.get('title', ''),
                    item.get('text', item.get('summary', '')),
                    item.get('link', item.get('source_url', '')),
                    item.get('source', '')
                ))
            
            conn.commit()
            print(f"✅ Saved {len(data_items)} raw data items")
            
        except Exception as e:
            print(f"❌ Error saving raw data: {e}")
            conn.rollback()
        finally:
            conn.close()

    def get_todays_findings(self) -> List[Dict[str, Any]]:
        """Get all findings from today."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        today = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute("""
            SELECT * FROM findings 
            WHERE date_found LIKE ? 
            ORDER BY created_at DESC
        """, (f"{today}%",))
        
        columns = [description[0] for description in cursor.description]
        findings = []
        
        for row in cursor.fetchall():
            findings.append(dict(zip(columns, row)))
        
        conn.close()
        return findings

    def get_findings_by_date_range(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Get findings within a date range."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM findings 
            WHERE date_found BETWEEN ? AND ?
            ORDER BY created_at DESC
        """, (start_date, end_date))
        
        columns = [description[0] for description in cursor.description]
        findings = []
        
        for row in cursor.fetchall():
            findings.append(dict(zip(columns, row)))
        
        conn.close()
        return findings

    def save_validation_result(self, finding_id: int, method: str, result: bool, details: str = "") -> None:
        """Save validation result for a finding."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO validation_log (
                    finding_id, validation_method, validation_result, validation_details
                )
                VALUES (?, ?, ?, ?)
            """, (finding_id, method, result, details))
            
            conn.commit()
            print(f"✅ Saved validation result for finding {finding_id}")
            
        except Exception as e:
            print(f"❌ Error saving validation result: {e}")
            conn.rollback()
        finally:
            conn.close()

    def get_database_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}
        
        # Count findings
        cursor.execute("SELECT COUNT(*) FROM findings")
        stats['total_findings'] = cursor.fetchone()[0]
        
        # Count today's findings
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("SELECT COUNT(*) FROM findings WHERE date_found LIKE ?", (f"{today}%",))
        stats['todays_findings'] = cursor.fetchone()[0]
        
        # Count raw data
        cursor.execute("SELECT COUNT(*) FROM raw_data")
        stats['total_raw_data'] = cursor.fetchone()[0]
        
        # Count validation logs
        cursor.execute("SELECT COUNT(*) FROM validation_log")
        stats['total_validations'] = cursor.fetchone()[0]
        
        conn.close()
        return stats 
```

**File:** `agents/validator.py`
```python
import os
import requests
from typing import Dict, Any, List
from googleapiclient.discovery import build
from dotenv import load_dotenv

class Validator:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        self.api_key = os.getenv("Google_Search_API_KEY")
        self.cse_id = os.getenv("GOOGLE_CSE_ID")
        
        # Target companies for validation
        self.target_companies = [
            "Capital One", "Truist", "Freddie Mac", "Navy Federal", 
            "PenFed", "Fannie Mae", "EagleBank", "Capital Bank N.A."
        ]

    def validate_event_internal(self, event_headline: str, company_name: str, internal_data: Dict[str, List]) -> bool:
        """
        Internal validation: Check if keywords from headline appear in internal data sources.
        """
        # Extract key words from headline (first 3-5 words)
        headline_words = event_headline.split()[:5]
        
        # Check SEC filings
        for filing in internal_data.get('sec_filings', []):
            if (company_name.lower() in filing.get('company', '').lower() and 
                any(word.lower() in filing.get('text', '').lower() for word in headline_words)):
                print(f"✅ Internally validated via SEC filing: {event_headline}")
                return True
        
        # Check news articles
        for article in internal_data.get('news', []):
            if (company_name.lower() in article.get('company', '').lower() and 
                any(word.lower() in article.get('title', '').lower() for word in headline_words)):
                print(f"✅ Internally validated via news article: {event_headline}")
                return True
        
        # Check procurement notices
        for notice in internal_data.get('procurement', []):
            if (company_name.lower() in notice.get('title', '').lower() and 
                any(word.lower() in notice.get('description', '').lower() for word in headline_words)):
                print(f"✅ Internally validated via procurement notice: {event_headline}")
                return True
        
        return False

    def validate_event_external(self, event_headline: str, company_name: str) -> bool:
        """
        External validation using Google Custom Search API.
        """
        if not self.api_key or not self.cse_id:
            print("⚠️  Google Search API credentials not found. Skipping external validation.")
            return False
        
        try:
            service = build("customsearch", "v1", developerKey=self.api_key)
            
            # Create search query
            query = f'"{event_headline}" "{company_name}"'
            
            # Search for recent results (last month)
            res = service.cse().list(
                q=query, 
                cx=self.cse_id, 
                num=3,
                dateRestrict='m1'  # Restrict to last month
            ).execute()
            
            # If we get at least one result, consider it validated
            if 'items' in res and len(res['items']) > 0:
                print(f"✅ Externally validated via Google Search: {event_headline}")
                print(f"   Found {len(res['items'])} confirming sources")
                return True
            else:
                print(f"❌ No external confirmation found for: {event_headline}")
                return False
                
        except Exception as e:
            print(f"❌ Google Search validation failed: {e}")
            return False

    def validate_event(self, event: Dict[str, Any], internal_data: Dict[str, List]) -> Dict[str, Any]:
        """
        Main validation method that combines internal and external validation.
        Now requires double-sourcing: at least two confirmations (internal and/or external).
        """
        event_headline = event.get('headline', '')
        company_name = event.get('company', '')
        
        print(f"🔍 Validating event: {event_headline}")
        
        # Step 1: Internal validation
        internal_validated = self.validate_event_internal(event_headline, company_name, internal_data)
        
        # Step 2: External validation (Google Search)
        external_validated = self.validate_event_external(event_headline, company_name)
        
        # Step 3: News cross-check (if both internal and external are not true)
        news_validated = False
        for article in internal_data.get('news', []):
            if (company_name.lower() in article.get('company', '').lower() and 
                event_headline.lower() in article.get('title', '').lower()):
                news_validated = True
                break
        
        # Count confirmations
        confirmations = sum([internal_validated, external_validated, news_validated])
        
        if confirmations >= 2:
            event['validation_status'] = 'validated_double_source'
            event['validation_method'] = 'double_source'
        elif confirmations == 1:
            event['validation_status'] = 'validated_single_source'
            event['validation_method'] = 'single_source'
        else:
            event['validation_status'] = 'unvalidated'
            event['validation_method'] = 'none'
        
        event['validation_confirmations'] = confirmations
        return event

    def validate_all_events(self, events: List[Dict[str, Any]], internal_data: Dict[str, List]) -> List[Dict[str, Any]]:
        """
        Validate all events in a batch, requiring double-sourcing for full validation.
        """
        validated_events = []
        
        for event in events:
            validated_event = self.validate_event(event, internal_data)
            validated_events.append(validated_event)
        
        # Count validation results
        double_count = sum(1 for e in validated_events if e['validation_status'] == 'validated_double_source')
        single_count = sum(1 for e in validated_events if e['validation_status'] == 'validated_single_source')
        unvalidated_count = sum(1 for e in validated_events if e['validation_status'] == 'unvalidated')
        
        print(f"📊 Validation Summary:")
        print(f"   - Double-sourced: {double_count}")
        print(f"   - Single-sourced: {single_count}")
        print(f"   - Unvalidated: {unvalidated_count}")
        
        return validated_events

    def get_validation_stats(self, events: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Get validation statistics for a list of events.
        """
        stats = {
            'total_events': len(events),
            'validated_internal': 0,
            'validated_external': 0,
            'unvalidated': 0
        }
        
        for event in events:
            status = event.get('validation_status', 'unvalidated')
            if status in stats:
                stats[status] += 1
        
        return stats 
```

**File:** `agents/reporter.py`
```python
import sqlite3
import pandas as pd
from datetime import date, datetime
from typing import List, Dict, Any
import os

class Reporter:
    def __init__(self, db_path='data/research.db'):
        self.db_path = db_path
        # Ensure reports directory exists
        os.makedirs('reports', exist_ok=True)

    def generate_report(self) -> str:
        """
        Queries DB for today's findings and generates a report.
        """
        today_str = date.today().isoformat()
        conn = sqlite3.connect(self.db_path)

        try:
            # Query for findings found today
            query = f"""
                SELECT 
                    date_found, company, headline, what_happened, 
                    why_it_matters, consulting_angle, source_url, 
                    event_type, value_usd, source_type
                FROM findings 
                WHERE date_found LIKE '{today_str}%'
                ORDER BY created_at DESC
            """
            
            df = pd.read_sql_query(query, conn)
            
            if df.empty:
                report_content = "# Daily Intelligence Report\n\n"
                report_content += f"**Date:** {today_str}\n\n"
                report_content += "## Summary\n\n"
                report_content += "No material updates found today.\n\n"
                report_content += "---\n"
                report_content += "*Report generated by Agentic Account Research System*"
            else:
                # Add Key Person columns for personnel as per requirements
                # The report now includes the following columns in this order:
                # 'Date', 'Company', 'Headline', 'What Happened?', 'Why it Matters', 'Consulting Angle', 'Source 1 (URL)',
                # 'Key Person 1 (URL, Role, Score)', 'Key Person 2 (URL, Role, Score)', 'Event Type', 'Value (USD)'
                # The report format now matches the required schema exactly.
                df['Key Person 1 (URL, Role, Score)'] = "N/A - Manual Lookup Required"
                df['Key Person 2 (URL, Role, Score)'] = "N/A - Manual Lookup Required"
                
                # Rename columns to match final schema
                df.rename(columns={
                    'date_found': 'Date', 
                    'company': 'Company', 
                    'headline': 'Headline', 
                    'what_happened': 'What Happened?', 
                    'why_it_matters': 'Why it Matters', 
                    'consulting_angle': 'Consulting Angle', 
                    'source_url': 'Source 1 (URL)',
                    'event_type': 'Event Type',
                    'value_usd': 'Value (USD)'
                }, inplace=True)
                
                # Reorder columns to match required output schema
                column_order = [
                    'Date', 'Company', 'Headline', 'What Happened?', 
                    'Why it Matters', 'Consulting Angle', 'Source 1 (URL)',
                    'Key Person 1 (URL, Role, Score)', 'Key Person 2 (URL, Role, Score)',
                    'Event Type', 'Value (USD)'
                ]
                
                # Only include columns that exist in the dataframe
                existing_columns = [col for col in column_order if col in df.columns]
                df = df[existing_columns]
                
                # Generate markdown report
                report_content = "# Daily Intelligence Report\n\n"
                report_content += f"**Date:** {today_str}\n\n"
                report_content += f"**Total Events Found:** {len(df)}\n\n"
                report_content += "## Summary\n\n"
                
                # Add summary statistics
                if 'Event Type' in df.columns:
                    event_counts = df['Event Type'].value_counts()
                    report_content += "**Events by Type:**\n"
                    for event_type, count in event_counts.items():
                        report_content += f"- {event_type}: {count}\n"
                    report_content += "\n"
                
                if 'Value (USD)' in df.columns:
                    total_value = df['Value (USD)'].sum()
                    if total_value > 0:
                        report_content += f"**Total Value:** ${total_value:,}\n\n"
                
                report_content += "## Detailed Findings\n\n"
                report_content += df.to_markdown(index=False)
                report_content += "\n\n---\n"
                report_content += "*Report generated by Agentic Account Research System*"

        except Exception as e:
            print(f"❌ Error generating report: {e}")
            report_content = f"# Error Generating Report\n\nError: {e}"
        finally:
            conn.close()

        # Save report to a file
        report_filename = f"reports/report-{today_str}.md"
        try:
            with open(report_filename, 'w', encoding='utf-8') as f:
                f.write(report_content)
            print(f"✅ Report generated: {report_filename}")
        except Exception as e:
            print(f"❌ Error saving report: {e}")

        return report_content

    def generate_csv_report(self) -> str:
        """
        Generate a CSV version of today's report.
        """
        today_str = date.today().isoformat()
        conn = sqlite3.connect(self.db_path)

        try:
            # Query for findings found today
            query = f"""
                SELECT 
                    date_found, company, headline, what_happened, 
                    why_it_matters, consulting_angle, source_url, 
                    event_type, value_usd, source_type
                FROM findings 
                WHERE date_found LIKE '{today_str}%'
                ORDER BY created_at DESC
            """
            
            df = pd.read_sql_query(query, conn)
            
            if not df.empty:
                # Add Key Person columns for personnel as per requirements
                # The report now includes the following columns in this order:
                # 'Date', 'Company', 'Headline', 'What Happened?', 'Why it Matters', 'Consulting Angle', 'Source 1 (URL)',
                # 'Key Person 1 (URL, Role, Score)', 'Key Person 2 (URL, Role, Score)', 'Event Type', 'Value (USD)'
                # The report format now matches the required schema exactly.
                df['Key Person 1 (URL, Role, Score)'] = "N/A - Manual Lookup Required"
                df['Key Person 2 (URL, Role, Score)'] = "N/A - Manual Lookup Required"
                
                # Rename columns
                df.rename(columns={
                    'date_found': 'Date', 
                    'company': 'Company', 
                    'headline': 'Headline', 
                    'what_happened': 'What Happened?', 
                    'why_it_matters': 'Why it Matters', 
                    'consulting_angle': 'Consulting Angle', 
                    'source_url': 'Source 1 (URL)',
                    'event_type': 'Event Type',
                    'value_usd': 'Value (USD)'
                }, inplace=True)
                
                # Save CSV
                csv_filename = f"reports/report-{today_str}.csv"
                df.to_csv(csv_filename, index=False)
                print(f"✅ CSV report generated: {csv_filename}")
                return csv_filename
            else:
                print("No data found for CSV report")
                return ""
                
        except Exception as e:
            print(f"❌ Error generating CSV report: {e}")
            return ""
        finally:
            conn.close()

    def get_report_summary(self) -> Dict[str, Any]:
        """
        Get a summary of today's findings for quick review.
        """
        today_str = date.today().isoformat()
        conn = sqlite3.connect(self.db_path)

        try:
            # Get basic counts
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM findings WHERE date_found LIKE '{today_str}%'")
            total_findings = cursor.fetchone()[0]
            
            # Get event type breakdown
            cursor.execute(f"""
                SELECT event_type, COUNT(*) 
                FROM findings 
                WHERE date_found LIKE '{today_str}%' 
                GROUP BY event_type
            """)
            event_breakdown = dict(cursor.fetchall())
            
            # Get total value
            cursor.execute(f"""
                SELECT SUM(value_usd) 
                FROM findings 
                WHERE date_found LIKE '{today_str}%' AND value_usd > 0
            """)
            total_value = cursor.fetchone()[0] or 0
            
            return {
                'date': today_str,
                'total_findings': total_findings,
                'event_breakdown': event_breakdown,
                'total_value': total_value
            }
            
        except Exception as e:
            print(f"❌ Error getting report summary: {e}")
            return {}
        finally:
            conn.close() 
```

End Task 16

---

## Begin Task 17: Implement Main Orchestrator, Scheduler, and Test Suite

**Description:**
Create the main orchestrator to run the workflow, add scheduler for daily runs, and implement a comprehensive test suite.

**File:** `main.py`
```python
import asyncio
import time
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# Import all agent classes
from agents.sam_extractor import SAMExtractor
from agents.news_extractor import NewsExtractor
from agents.sec_extractor import SECExtractor
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
```

**File:** `test_system.py`
```python
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

def test_environment():
    """Test environment setup and API keys."""
    print("🔧 Testing Environment Setup...")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    required_keys = [
        "SEC_API_KEY",
        "MARKETAUX_API_KEY", 
        "SAM_API_KEY",
        "OPENAI_API_KEY",
        "Google_Search_API_KEY",
        "GOOGLE_CSE_ID"
    ]
    
    missing_keys = []
    for key in required_keys:
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
        from agents.sam_extractor import SAMExtractor
        sam = SAMExtractor()
        notices = sam.get_all_notices()
        print(f"✅ SAM Extractor: {len(notices)} notices found")
    except Exception as e:
        print(f"❌ SAM Extractor failed: {e}")
    
    # Test News Extractor
    try:
        from agents.news_extractor import NewsExtractor
        news = NewsExtractor()
        articles = news.get_all_news()
        print(f"✅ News Extractor: {len(articles)} articles found")
    except Exception as e:
        print(f"❌ News Extractor failed: {e}")
    
    # Test SEC Extractor
    try:
        from agents.sec_extractor import SECExtractor
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
```

End Task 17 

---

## Ethical HTTP Utility for Extractors

**Update:**
A new utility (`agents/http_utils.py`) provides ethical HTTP requests for all extractors. It features:
- User-agent rotation
- robots.txt compliance
- Randomized delay between requests
- Centralized `ethical_get()` function

All extractors (e.g., `sam_extractor.py`, `news_extractor.py`) now use `ethical_get()` for all HTTP requests, ensuring ethical and robust data collection.

**Example Usage in Extractors:**
```python
from agents.http_utils import ethical_get

response = ethical_get(url, params=params, timeout=30)
if response is None:
    print("Blocked or failed by ethical_get.")
    return []
response.raise_for_status()
data = response.json()
``` 