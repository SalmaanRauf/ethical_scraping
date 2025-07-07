# Agentic Account Research System - Build Log (Tasks 13-15)

---

## Begin Task 13: Create SK Function - Insight Generator

**Description:**
Create the Insight Generator function to generate structured insights from events.

**Commands:**
```bash
mkdir -p sk_functions/InsightGenerator
```

**File:** `sk_functions/InsightGenerator/skprompt.txt`
```
You are a strategy consultant. You have been given structured data about a significant corporate event.
Generate a concise, three-bullet brief in a JSON format.

Input Data (JSON):
{{$input}}

JSON Output:
{
  "what_happened": "A concise, neutral summary of the event.",
  "why_it_matters": "The immediate impact on the company, its market, or its strategy.",
  "consulting_angle": "The potential opportunity or risk this creates that would be relevant to a consultant (e.g., need for integration planning, new technology adoption, market entry strategy)."
}
```

End Task 13

---

## Begin Task 14: Implement Analyst Agent

**Description:**
Create the Analyst Agent to orchestrate all Semantic Kernel functions and run the full analysis pipeline.

**File:** `agents/analyst_agent.py`

```python
import json
import asyncio
from typing import List, Dict, Any
from config.kernel_setup import get_kernel
from semantic_kernel.functions import KernelFunction

class AnalystAgent:
    def __init__(self):
        self.kernel = get_kernel()
        self.functions = {}
        self._load_functions()

    def _load_functions(self):
        """Load all Semantic Kernel functions."""
        try:
            # Load triage function
            self.functions['triage'] = self.kernel.add_function(
                prompt_template_file="sk_functions/Triage/skprompt.txt",
                function_name="triage",
                description="Categorize and filter data for relevance"
            )
            
            # Load financial specialist function
            self.functions['financial'] = self.kernel.add_function(
                prompt_template_file="sk_functions/FinancialSpecialist/skprompt.txt",
                function_name="financial_specialist",
                description="Detect financial events over $10M (strictly enforced)"
            )
            
            # Load procurement specialist function
            self.functions['procurement'] = self.kernel.add_function(
                prompt_template_file="sk_functions/ProcurementSpecialist/skprompt.txt",
                function_name="procurement_specialist",
                description="Analyze procurement notices"
            )
            
            # Load earnings call specialist function
            self.functions['earnings'] = self.kernel.add_function(
                prompt_template_file="sk_functions/EarningsCallSpecialist/skprompt.txt",
                function_name="earnings_specialist",
                description="Analyze earnings call transcripts"
            )
            
            # Load insight generator function
            self.functions['insight'] = self.kernel.add_function(
                prompt_template_file="sk_functions/InsightGenerator/skprompt.txt",
                function_name="insight_generator",
                description="Generate structured insights"
            )
            
            print("✅ All Semantic Kernel functions loaded successfully")
            
        except Exception as e:
            print(f"❌ Error loading functions: {e}")
            raise

    async def triage_data(self, data_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Triage data to filter out irrelevant items."""
        relevant_items = []
        
        for item in data_items:
            try:
                # Prepare text for analysis
                text = ""
                if item.get('type') == 'news':
                    text = f"{item.get('title', '')} {item.get('summary', '')}"
                elif item.get('data_type') == 'filing':
                    text = item.get('text', '')[:2000]  # Limit text length
                elif item.get('type') == 'procurement':
                    text = f"{item.get('title', '')} {item.get('description', '')}"
                
                if not text.strip():
                    continue
                
                # Run triage
                result = await self.kernel.invoke_function(
                    self.functions['triage'],
                    input_str=text
                )
                
                # Parse result
                try:
                    triage_result = json.loads(str(result))
                    if triage_result.get('is_relevant', False):
                        item['triage_result'] = triage_result
                        relevant_items.append(item)
                except json.JSONDecodeError:
                    print(f"Warning: Could not parse triage result for item: {item.get('title', 'Unknown')}")
                    continue
                    
            except Exception as e:
                print(f"Error during triage for item: {e}")
                continue
        
        print(f"Triage complete: {len(relevant_items)} relevant items found out of {len(data_items)}")
        return relevant_items

    async def analyze_financial_events(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze items for financial events."""
        financial_events = []
        
        for item in items:
            if item.get('triage_result', {}).get('category') in ['News Article', 'SEC Filing']:
                try:
                    text = ""
                    if item.get('type') == 'news':
                        text = f"{item.get('title', '')} {item.get('summary', '')}"
                    elif item.get('data_type') == 'filing':
                        text = item.get('text', '')[:2000]
                    
                    if not text.strip():
                        continue
                    
                    # Run financial analysis
                    result = await self.kernel.invoke_function(
                        self.functions['financial'],
                        input_str=text
                    )
                    
                    # Parse result
                    try:
                        financial_result = json.loads(str(result))
                        if financial_result.get('event_found', False):
                            # Check monetary threshold - only include if >= $10M
                            value_usd = financial_result.get('value_usd', 0)
                            if value_usd and value_usd >= 10_000_000:
                                item['financial_analysis'] = financial_result
                                financial_events.append(item)
                            else:
                                print(f"Financial event found but value ${value_usd:,} is below $10M threshold")
                    except json.JSONDecodeError:
                        continue
                        
                except Exception as e:
                    print(f"Error during financial analysis: {e}")
                    continue
        
        print(f"Financial analysis complete: {len(financial_events)} events >= $10M found")
        return financial_events

    async def analyze_procurement(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze procurement notices."""
        procurement_events = []
        
        for item in items:
            if item.get('type') == 'procurement':
                try:
                    text = f"{item.get('title', '')} {item.get('description', '')}"
                    
                    if not text.strip():
                        continue
                    
                    # Run procurement analysis
                    result = await self.kernel.invoke_function(
                        self.functions['procurement'],
                        input_str=text
                    )
                    
                    # Parse result
                    try:
                        procurement_result = json.loads(str(result))
                        if procurement_result.get('is_relevant', False):
                            # Check monetary threshold - only include if >= $10M
                            value_usd = procurement_result.get('value_usd', 0)
                            if value_usd and value_usd >= 10_000_000:
                                item['procurement_analysis'] = procurement_result
                                procurement_events.append(item)
                            else:
                                print(f"Procurement notice found but value ${value_usd:,} is below $10M threshold")
                    except json.JSONDecodeError:
                        continue
                        
                except Exception as e:
                    print(f"Error during procurement analysis: {e}")
                    continue
        
        print(f"Procurement analysis complete: {len(procurement_events)} relevant notices >= $10M found")
        return procurement_events

    async def analyze_earnings_calls(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze earnings call transcripts."""
        earnings_events = []
        
        for item in items:
            if (item.get('data_type') == 'filing' and 
                item.get('type') in ['10-Q', '10-K']):
                try:
                    text = item.get('text', '')[:3000]  # Limit for earnings call analysis
                    
                    if not text.strip():
                        continue
                    
                    # Run earnings call analysis
                    result = await self.kernel.invoke_function(
                        self.functions['earnings'],
                        input_str=text
                    )
                    
                    # Parse result
                    try:
                        earnings_result = json.loads(str(result))
                        if earnings_result.get('guidance_found', False):
                            # Check monetary threshold - only include if >= $10M
                            value_usd = earnings_result.get('value_usd', 0)
                            if value_usd and value_usd >= 10_000_000:
                                item['earnings_analysis'] = earnings_result
                                earnings_events.append(item)
                            else:
                                print(f"Earnings guidance found but value ${value_usd:,} is below $10M threshold")
                    except json.JSONDecodeError:
                        continue
                        
                except Exception as e:
                    print(f"Error during earnings call analysis: {e}")
                    continue
        
        print(f"Earnings call analysis complete: {len(earnings_events)} guidance items >= $10M found")
        return earnings_events

    async def generate_insights(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate insights for all events."""
        insights = []
        
        for event in events:
            try:
                # Prepare data for insight generation
                insight_data = {
                    'company': event.get('company', ''),
                    'title': event.get('title', ''),
                    'source': event.get('source', ''),
                    'type': event.get('type', '')
                }
                
                # Add analysis results
                if 'financial_analysis' in event:
                    insight_data.update(event['financial_analysis'])
                elif 'procurement_analysis' in event:
                    insight_data.update(event['procurement_analysis'])
                elif 'earnings_analysis' in event:
                    insight_data.update(event['earnings_analysis'])
                
                # Generate insight
                result = await self.kernel.invoke_function(
                    self.functions['insight'],
                    input_str=json.dumps(insight_data)
                )
                
                # Parse result
                try:
                    insight_result = json.loads(str(result))
                    event['insights'] = insight_result
                    insights.append(event)
                except json.JSONDecodeError:
                    print(f"Warning: Could not parse insight for event: {event.get('title', 'Unknown')}")
                    continue
                    
            except Exception as e:
                print(f"Error generating insight: {e}")
                continue
        
        print(f"Insight generation complete: {len(insights)} insights generated")
        return insights

    async def analyze_all_data(self, data_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Main method to analyze all data through the complete pipeline."""
        print(f"Starting analysis of {len(data_items)} data items...")
        
        # Step 1: Triage
        relevant_items = await self.triage_data(data_items)
        
        # Step 2: Specialized analysis
        financial_events = await self.analyze_financial_events(relevant_items)
        procurement_events = await self.analyze_procurement(relevant_items)
        earnings_events = await self.analyze_earnings_calls(relevant_items)
        
        # Step 3: Combine all events
        all_events = financial_events + procurement_events + earnings_events
        
        # Step 4: Generate insights
        final_insights = await self.generate_insights(all_events)
        
        print(f"Analysis complete: {len(final_insights)} high-impact events identified")
        return final_insights
```

End Task 14

---

## Begin Task 15: Implement SQLite Database Setup

**Description:**
Create the SQLite database setup script and schema for findings, raw data, and validation logs.

**File:** `config/database_setup.py`

```python
import sqlite3
import os
from datetime import datetime

def setup_database():
    """Creates the database and the findings table if they don't exist."""
    
    # Ensure data directory exists
    os.makedirs('data', exist_ok=True)
    
    conn = sqlite3.connect('data/research.db')
    cursor = conn.cursor()

    # Create table to store high-impact findings
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS findings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_hash TEXT UNIQUE NOT NULL,
        date_found TEXT NOT NULL,
        company TEXT NOT NULL,
        headline TEXT NOT NULL,
        what_happened TEXT,
        why_it_matters TEXT,
        consulting_angle TEXT,
        source_url TEXT,
        event_type TEXT,
        value_usd INTEGER,
        source_type TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Create table to store raw data for validation
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS raw_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date_collected TEXT NOT NULL,
        data_type TEXT NOT NULL,
        company TEXT,
        title TEXT,
        content TEXT,
        source_url TEXT,
        source_type TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Create table to store validation results
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS validation_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        finding_id INTEGER,
        validation_method TEXT,
        validation_result BOOLEAN,
        validation_details TEXT,
        validated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (finding_id) REFERENCES findings (id)
    )
    ''')

    conn.commit()
    conn.close()
    print("✅ Database setup complete.")
    print("   - findings table created")
    print("   - raw_data table created") 
    print("   - validation_log table created")

def reset_database():
    """Reset the database by dropping all tables and recreating them."""
    conn = sqlite3.connect('data/research.db')
    cursor = conn.cursor()
    
    cursor.execute("DROP TABLE IF EXISTS findings")
    cursor.execute("DROP TABLE IF EXISTS raw_data")
    cursor.execute("DROP TABLE IF EXISTS validation_log")
    
    conn.commit()
    conn.close()
    
    print("🗑️  Database reset complete.")
    setup_database()

def check_database_status():
    """Check the current status of the database."""
    conn = sqlite3.connect('data/research.db')
    cursor = conn.cursor()
    
    # Check if tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print("📊 Database Status:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
        count = cursor.fetchone()[0]
        print(f"   - {table[0]}: {count} records")
    
    conn.close()

if __name__ == '__main__':
    setup_database()
    check_database_status()
```

End Task 15

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