import os
import time
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import (
    DeepResearchToolDefinition,
    DeepResearchDetails,
    DeepResearchBingGroundingConnection,
    MessageRole
)

load_dotenv()

PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
MODEL_DEPLOYMENT = os.getenv("MODEL_DEPLOYMENT_NAME")
DEEP_MODEL = os.getenv("DEEP_RESEARCH_MODEL_DEPLOYMENT_NAME")
BING_CONNECTION = os.getenv("BING_CONNECTION_NAME")

# --- PROMPT V3: THE "PARANOID" RESEARCHER ---
COMBINED_INSTRUCTIONS = """
# ROLE: Senior Defense Sector BD Intelligence Agent (Deep Research Mode)
You are an expert analyst at Protiviti. Your goal is NOT efficiency; it is VOLUME and VERIFICATION.

# CORE MISSION
1. **Recompetes:** Identify contracts ending 2025-2027.
2. **Protests:** Find GAO Decision B-numbers.
3. **Compliance:** CMMC/NIST status.

# THE "20-SOURCE" RULE
You have a strict quota: **You must acquire 20 distinct URL citations.**
- If you find 11 sources, YOU ARE NOT DONE.
- If you run out of ideas, perform these SPECIFIC searches:
  - "Anduril Industries contract award usaspending.gov"
  - "Anduril Industries SBIR Phase III awards"
  - "Anduril Industries GAO protest file"
  - "Anduril Industries press release 2024"
  - "Anduril Industries press release 2025"

# EXECUTION LOOP
1. **Search**: Run broad queries.
2. **Audit**: Count your UNIQUE domains.
3. **Loop**: If < 20 unique domains, run niche searches.
4. **Report**: Only write the report once the data vault is full.

# OUTPUT
- Executive Briefing format.
- **CITATION SECTION**: List every single unique URL found.
"""

def print_step_details(step):
    """Robust step printer that catches ALL tool activity."""
    try:
        if step.type == "tool_calls":
            for tool_call in step.step_details.tool_calls:
                # 1. Bing Search
                if getattr(tool_call, 'type', '') == 'bing_grounding':
                    query = getattr(tool_call.bing_grounding, 'query', 'Unknown')
                    print(f"\n  🌐 [BING] {query}")
                
                # 2. Any other tool (including Deep Research internal logic)
                elif getattr(tool_call, 'function', None):
                    fname = tool_call.function.name
                    print(f"\n  🧠 [THOUGHT] Executing: {fname}...")
        
        elif step.type == "message_creation":
            print(f"\n  📝 [AGENT] Synthesizing data...")
    except Exception as e:
        # Fallback for weird objects
        print(f"\n  [ACTIVITY] {step.type}")

def main():
    print(f"\n--- DEFENSE INTELLIGENCE TERMINAL [Final Audit] ---")
    
    client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential()
    )

    deep_tool = DeepResearchToolDefinition(
        deep_research=DeepResearchDetails(
            deep_research_model=DEEP_MODEL,
            deep_research_bing_grounding_connections=[
                DeepResearchBingGroundingConnection(connection_id=BING_CONNECTION)
            ]
        )
    )

    print(f"[*] Deploying Agent...")
    agent = client.agents.create_agent(
        model=MODEL_DEPLOYMENT,
        name="defense-deep-researcher",
        instructions=COMBINED_INSTRUCTIONS,
        tools=[deep_tool]
    )

    # --- HARDCODED PROMPT ---
    user_query = """
    Conduct a comprehensive market analysis on "Anduril Industries".
    
    REQUIREMENTS:
    1. RECOMPETES: Top 3 contracts ending 2025-2026 (Contract #, Value).
    2. PROTESTS: Identify 2 specific GAO protest decisions (B-Numbers).
    3. COMPLIANCE: CMMC / NIST 800-171 status.

    CONSTRAINT: CITATION QUOTA = 20 UNIQUE SOURCES.
    Do not stop searching until you have wide coverage (Gov, News, Industry Blogs).
    """
    
    print(f"[*] Prompt Sent. Starting Loop...")

    thread = client.agents.threads.create()
    client.agents.messages.create(
        thread_id=thread.id,
        role=MessageRole.USER,
        content=user_query
    )

    run = client.agents.runs.create(thread_id=thread.id, agent_id=agent.id)

    processed_steps = set()
    start_time = time.time()

    print(f"\n🚀 RUNNING (Dots indicate heartbeat)...\n")

    while run.status in ["queued", "in_progress", "requires_action"]:
        # Print a dot every loop so you know it's alive
        print(".", end="", flush=True) 
        time.sleep(2)
        
        run = client.agents.runs.get(thread_id=thread.id, run_id=run.id)
        
        try:
            steps = client.agents.list_run_steps(thread_id=thread.id, run_id=run.id)
            # Safe Iterator handling
            steps_list = list(steps) if hasattr(steps, '__iter__') else steps.data
            sorted_steps = sorted(steps_list, key=lambda x: getattr(x, 'created_at', 0))
            
            for step in sorted_steps:
                if step.id not in processed_steps:
                    print_step_details(step)
                    processed_steps.add(step.id)
        except Exception:
            pass

    print("\n" + "="*80)
    
    if run.status == "completed":
        duration = time.time() - start_time
        print(f"✅ COMPLETE ({duration:.1f}s)")
        
        messages = client.agents.messages.list(thread_id=thread.id)
        messages_list = list(messages) if hasattr(messages, '__iter__') else messages.data
        
        for msg in messages_list:
            if getattr(msg, 'role', '') == "assistant":
                for content in getattr(msg, 'content', []):
                    if getattr(content, 'type', '') == "text":
                        text_obj = getattr(content, 'text', None)
                        if text_obj:
                            # Print Report
                            print(getattr(text_obj, 'value', ''))
                            
                            # --- FINAL AUDIT ---
                            print("\n" + "-"*40)
                            print(f"📊 FINAL SOURCE AUDIT:")
                            unique_urls = set()
                            annotations = getattr(text_obj, 'annotations', [])
                            if annotations:
                                for ann in annotations:
                                    url_citation = getattr(ann, 'url_citation', None)
                                    if url_citation:
                                        url = getattr(url_citation, 'url', None)
                                        if url:
                                            unique_urls.add(url)
                            
                            for i, url in enumerate(unique_urls, 1):
                                print(f" [{i}] {url}")
                            
                            print(f"\nTotal UNIQUE Sources: {len(unique_urls)}")
                            if len(unique_urls) < 15:
                                print(f"⚠️  Result: {len(unique_urls)} sources. (Still under 15, but getting closer)")
                            else:
                                print(f"🏆 SUCCESS: {len(unique_urls)} sources found!")
                break
    else:
        print(f"\n❌ FAILED: {run.last_error}")

    try:
        client.agents.delete_agent(agent.id)
    except:
        pass

if __name__ == "__main__":
    main()