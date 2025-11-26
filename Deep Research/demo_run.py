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

# Load environment variables
load_dotenv()

PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
MODEL_DEPLOYMENT = os.getenv("MODEL_DEPLOYMENT_NAME")       # gpt-4o (Orchestrator)
DEEP_MODEL = os.getenv("DEEP_RESEARCH_MODEL_DEPLOYMENT_NAME") # o3-deep-research (Brain)
BING_CONNECTION = os.getenv("BING_CONNECTION_NAME")

# --- THE PROMPT ---
# I kept your exact logic but added the "Anti-Laziness" constraints we discussed.
COMBINED_INSTRUCTIONS = """
# ROLE: Senior Defense Sector BD Intelligence Agent (Deep Research Mode)

You are an expert research analyst at Protiviti specializing in U.S. Defense sector opportunities.

# PHASE 1: RESEARCH STRATEGY
1. **Plan:** Break the request into search pillars (Contracts, Protests, Tech Specs).
2. **Execute:** Perform parallel searches.
3. **Evaluate:**
   - Did you find specific contract numbers? If no, SEARCH AGAIN.
   - Did you find the original RFP? If no, SEARCH AGAIN.
   - Do you have 15+ DISTINCT sources? (Citing the same URL 5 times does NOT count).

# PHASE 2: DEFENSE INTELLIGENCE REQUIREMENTS
**Priority Sources (TIER 1):** SAM.gov, FPDS.gov, GAO.gov, defense.gov.
**High-Value Signals:**
- Recompete Windows (Contracts ending 2025-2026)
- CMMC/NIST 800-171 Compliance Statements
- GAO Bid Protest Decisions (Won/Lost)

# PHASE 3: CRITICAL OUTPUT CONSTRAINTS
- **Quantity:** You MUST cite a minimum of 15 DISTINCT, UNIQUE URLs.
- **Diversity:** Do not cite the same domain (e.g., anduril.com) more than 3 times total. Find diverse 3rd party verification.
- **Traceability:** Every claim of a dollar value, date, or contract number must have a citation.

If you fail to meet the 15-unique-source threshold, perform another search loop specifically for "Tier 2" industry news sources.
"""

def print_step_details(step):
    """
    Visualizes the agent's thinking. 
    (I simplified the nesting here to make it cleaner, but it does the exact same thing)
    """
    try:
        step_type = getattr(step, 'type', None)
        if step_type == "tool_calls":
            step_details = getattr(step, 'step_details', None)
            if step_details:
                for tool_call in getattr(step_details, 'tool_calls', []):
                    if getattr(tool_call, 'type', '') == 'bing_grounding':
                        # Show the actual search query
                        query = getattr(tool_call.bing_grounding, 'query', 'Unknown')
                        print(f"  🌐 [BING] {query}")
                    elif getattr(tool_call, 'function', None):
                        # Show when the Deep Research tool is thinking
                        print(f"  🧠 [THOUGHT] Processing research plan...")
        elif step_type == "message_creation":
            print(f"  📝 [AGENT] Drafting response...")
    except Exception:
        pass

def main():
    print(f"\n--- DEFENSE INTELLIGENCE TERMINAL [Deep Audit Mode] ---")
    
    # 1. Initialize Client
    client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential()
    )

    # 2. Configure Tool
    deep_tool = DeepResearchToolDefinition(
        deep_research=DeepResearchDetails(
            deep_research_model=DEEP_MODEL,
            deep_research_bing_grounding_connections=[
                DeepResearchBingGroundingConnection(connection_id=BING_CONNECTION)
            ]
        )
    )

    # 3. Create Agent
    print(f"[*] Deploying Agent...")
    agent = client.agents.create_agent(
        model=MODEL_DEPLOYMENT,
        name="defense-deep-researcher",
        instructions=COMBINED_INSTRUCTIONS,
        tools=[deep_tool]
    )

    # 4. HARDCODED PROMPT (To prevent the Copy-Paste Error)
    # This matches exactly what you were trying to paste.
    user_query = """
    Conduct a comprehensive market analysis on "Anduril Industries" and their "Lattice OS" ecosystem. 

    I specifically need to identify:
    1. RECOMPETE OPPORTUNITIES: Find their top 3 contracts ending in 2025-2026. Provide Contract Numbers and Dollar Values.
    2. PROTEST ACTIVITY: Identify 2 specific GAO bid protest decisions involving Anduril (won or lost).
    3. COMPLIANCE: Search for any public mentions of their CMMC or NIST 800-171 compliance status.

    CONSTRAINT: You must cite at least 15 DISTINCT sources. Do not cite the same URL multiple times to inflate the count.
    """
    
    print(f"\n[*] Sending Stress Test Prompt:\n{user_query.strip()[:100]}...")

    # 5. Start Run
    thread = client.agents.threads.create()
    client.agents.messages.create(
        thread_id=thread.id,
        role=MessageRole.USER,
        content=user_query
    )

    print(f"\n🚀 STARTING RUN... (Watch for [BING] queries)\n")
    run = client.agents.runs.create(thread_id=thread.id, agent_id=agent.id)

    processed_steps = set()
    start_time = time.time()

    # --- THE FIXED VISUALIZATION LOOP ---
    while run.status in ["queued", "in_progress", "requires_action"]:
        time.sleep(2)
        run = client.agents.runs.get(thread_id=thread.id, run_id=run.id)
        
        try:
            # FIX: Use 'list_run_steps' instead of 'runs.list_steps'
            steps = client.agents.list_run_steps(thread_id=thread.id, run_id=run.id)
            
            # Handle iterator safely
            steps_list = list(steps) if hasattr(steps, '__iter__') else steps.data
            sorted_steps = sorted(steps_list, key=lambda x: getattr(x, 'created_at', 0))
            
            for step in sorted_steps:
                step_id = getattr(step, 'id', None)
                if step_id and step_id not in processed_steps:
                    print_step_details(step)
                    processed_steps.add(step_id)
        except Exception:
            pass

    # 6. Output & Audit
    if run.status == "completed":
        duration = time.time() - start_time
        print(f"\n✅ COMPLETE ({duration:.1f}s)")
        print("\n" + "="*80)
        
        messages = client.agents.messages.list(thread_id=thread.id)
        # Handle iterator safely
        messages_list = list(messages) if hasattr(messages, '__iter__') else messages.data
        
        for msg in messages_list:
            if getattr(msg, 'role', '') == "assistant":
                for content in getattr(msg, 'content', []):
                    if getattr(content, 'type', '') == "text":
                        text_obj = getattr(content, 'text', None)
                        if text_obj:
                            # Print Report
                            print(getattr(text_obj, 'value', ''))
                            
                            # --- NEW: REAL CITATION AUDIT ---
                            print("\n" + "-"*40)
                            print(f"📊 REAL CITATION AUDIT (Unique URLs):")
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
                                print(f"⚠️ WARNING: Failed to meet 15-source constraint.")
                break
    else:
        print(f"\n❌ FAILED: {run.last_error}")

    try:
        client.agents.delete_agent(agent.id)
    except:
        pass

if __name__ == "__main__":
    main()