import os
import time
import json
import logging
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

# --- CONFIGURATION ---
PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
MODEL_DEPLOYMENT = os.getenv("MODEL_DEPLOYMENT_NAME")
DEEP_MODEL = os.getenv("DEEP_RESEARCH_MODEL_DEPLOYMENT_NAME")
BING_CONNECTION = os.getenv("BING_CONNECTION_NAME")

# --- PROMPT V4: THE "SCORCHED EARTH" AUDITOR ---
COMBINED_INSTRUCTIONS = """
# ROLE: Senior Defense Sector BD Intelligence Agent (Deep Research Mode)
You are an expert analyst at Protiviti. Your goal is VOLUME and VERIFICATION.

# MISSION: Anduril Industries Deep Dive
1. **Recompetes:** Identify contracts ending 2025-2027 (Contract #, Value).
2. **Protests:** Find GAO Decision B-numbers.
3. **Compliance:** CMMC / NIST 800-171 status.

# THE "20-SOURCE" RULE
- **Constraint:** You must acquire 20 DISTINCT unique citations.
- **Diversity:** Do not cite 'cinch.com' or 'anduril.com' more than 3 times each.
- **Fallback:** If stuck, search 'usaspending.gov', 'defense.gov', 'breakingdefense.com'.

If you have fewer than 15 sources, your job is NOT done. Loop and search again.
"""

def main():
    print(f"\n--- DEFENSE INTELLIGENCE TERMINAL [Deep Dive Mode] ---")
    
    client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential()
    )

    # --- FIX: Fetch Connection ID dynamically ---
    try:
        bing_conn_obj = client.connections.get(connection_name=BING_CONNECTION)
        bing_conn_id = bing_conn_obj.id
    except:
        bing_conn_id = BING_CONNECTION

    deep_tool = DeepResearchToolDefinition(
        deep_research=DeepResearchDetails(
            deep_research_model=DEEP_MODEL,
            deep_research_bing_grounding_connections=[
                DeepResearchBingGroundingConnection(connection_id=bing_conn_id)
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

    user_query = """
    Conduct a comprehensive market analysis on "Anduril Industries".
    REQUIREMENTS:
    1. RECOMPETES: Top 3 contracts ending 2025-2026.
    2. PROTESTS: Identify 2 specific GAO protest decisions.
    3. COMPLIANCE: CMMC / NIST 800-171 status.
    CONSTRAINT: 20 UNIQUE SOURCES. Verify everything.
    """
    
    print(f"[*] Sending Prompt...")

    thread = client.agents.threads.create()
    client.agents.messages.create(
        thread_id=thread.id,
        role=MessageRole.USER,
        content=user_query
    )

    print(f"[*] Starting Run loop...")
    run = client.agents.runs.create(thread_id=thread.id, agent_id=agent.id)

    # Track distinct CONTENT we have printed, not just Step IDs
    printed_thoughts = set()
    printed_queries = set()
    start_time = time.time()
    
    print(f"\n🚀 MONITORING AGENT BRAIN (Real-time Updates)...\n")

    # --- IMPROVED POLLING LOOP ---
    while run.status in ["queued", "in_progress", "requires_action"]:
        time.sleep(2) # Polling wait
        
        try:
            # 1. Get Latest Run & Steps
            run = client.agents.runs.get(thread_id=thread.id, run_id=run.id)
            steps = client.agents.list_run_steps(thread_id=thread.id, run_id=run.id)
            
            # 2. Check Run-Level Metadata for high-level thoughts
            # (Sometimes the big 'Plan' appears here)
            if run.metadata and 'cot_summary' in run.metadata:
                thought = run.metadata['cot_summary']
                if thought not in printed_thoughts:
                    print(f"🧠 [PLANNING] {thought}", flush=True)
                    printed_thoughts.add(thought)

            # 3. Check Individual Steps
            steps_data = list(steps) if hasattr(steps, '__iter__') else steps.data
            sorted_steps = sorted(steps_data, key=lambda x: getattr(x, 'created_at', 0))
            
            for step in sorted_steps:
                # Dump the step to dict to avoid SDK attribute errors
                try:
                    step_raw = step.model_dump() if hasattr(step, 'model_dump') else step.__dict__
                except:
                    continue

                # --- A. Check for Thoughts (Step Metadata) ---
                meta = step_raw.get('metadata', {}) or {}
                if 'cot_summary' in meta:
                    thought = meta['cot_summary']
                    if thought and thought not in printed_thoughts:
                        print(f"🤔 [THOUGHT] {thought}", flush=True)
                        printed_thoughts.add(thought)

                # --- B. Check for Bing Queries (Tool Calls) ---
                step_details = step_raw.get('step_details', {})
                if step_details and 'tool_calls' in step_details:
                    for tool in step_details['tool_calls']:
                        # Deep Research uses 'bing_grounding' or similar inside the tool args
                        try:
                            # Look for 'query' in the function arguments
                            if 'function' in tool:
                                args_str = tool['function'].get('arguments', '')
                                if args_str and args_str not in printed_queries:
                                    # It's a JSON string, try to parse it cleanly
                                    try:
                                        import json
                                        args_json = json.loads(args_str)
                                        if 'query' in args_json:
                                            q = args_json['query']
                                            print(f"🌐 [SEARCH] {q}", flush=True)
                                            printed_queries.add(args_str) # Mark exact args as seen
                                    except:
                                        # If raw string isn't valid JSON yet (streaming), skip or print raw
                                        pass
                            
                            # Look for explicit bing_grounding dict (older SDK versions)
                            elif 'bing_grounding' in tool:
                                q = tool['bing_grounding'].get('query')
                                if q and q not in printed_queries:
                                    print(f"🌐 [SEARCH] {q}", flush=True)
                                    printed_queries.add(q)
                        except:
                            pass

                # --- C. Check for Report Drafting ---
                if step_raw.get('type') == 'message_creation' and step.status == 'in_progress':
                     # Only print this once per step ID
                     if step.id not in printed_thoughts:
                         print(f"📝 [WRITING] Synthesizing findings...", flush=True)
                         printed_thoughts.add(step.id)

        except Exception as e:
            # Silently ignore polling errors to keep terminal clean
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
                            val = getattr(text_obj, 'value', '')
                            print(val)
                            
                            # --- SOURCE AUDIT ---
                            print("\n" + "-"*40)
                            print(f"📊 FINAL SOURCE AUDIT:")
                            unique_urls = set()
                            annotations = getattr(text_obj, 'annotations', [])
                            if annotations:
                                for ann in annotations:
                                    try:
                                        url_citation = getattr(ann, 'url_citation', None)
                                        if url_citation:
                                            url = getattr(url_citation, 'url', None)
                                            if url: unique_urls.add(url)
                                    except:
                                        pass
                            
                            for i, url in enumerate(unique_urls, 1):
                                print(f" [{i}] {url}")
                            
                            print(f"\nTotal UNIQUE Sources: {len(unique_urls)}")
                            if len(unique_urls) < 15:
                                print(f"⚠️  Result: {len(unique_urls)} sources.")
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