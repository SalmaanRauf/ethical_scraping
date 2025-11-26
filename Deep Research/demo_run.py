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
# We keep the high-pressure source constraint.
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

def extract_bing_query(step_obj):
    """
    Senior Staff Level Debugging:
    Recursively hunt for 'bing_grounding' or 'query' inside the raw step dictionary.
    This bypasses SDK attribute changes/versions.
    """
    try:
        # Convert to dict if it's a model
        data = step_obj.model_dump() if hasattr(step_obj, 'model_dump') else (
            step_obj.as_dict() if hasattr(step_obj, 'as_dict') else step_obj.__dict__
        )
    except:
        return None

    # Recursive search function
    def search_dict(d):
        if isinstance(d, dict):
            # Check for Bing Grounding specific signature
            if 'bing_grounding' in d and 'query' in d['bing_grounding']:
                return f"🌐 [BING] {d['bing_grounding']['query']}"
            
            # Check for generic tool calls that might be Deep Research thinking
            if 'type' in d and d['type'] == 'function':
                if 'name' in d and 'deep_research' in d.get('name', ''):
                    return "🧠 [THOUGHT] Deep Research Loop Planning..."
            
            # Recurse
            for k, v in d.items():
                res = search_dict(v)
                if res: return res
        
        elif isinstance(d, list):
            for item in d:
                res = search_dict(item)
                if res: return res
        return None

    return search_dict(data)

def main():
    print(f"\n--- DEFENSE INTELLIGENCE TERMINAL [Deep Dive Mode] ---")
    
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

    # --- HARDCODED STRESS TEST ---
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

    processed_steps = set()
    start_time = time.time()
    
    # Force print initial status
    print(f"\n🚀 MONITORING AGENT BRAIN (Real-time)...\n")

    while run.status in ["queued", "in_progress", "requires_action"]:
        time.sleep(2) # Polling wait
        
        # Refresh Status
        run = client.agents.runs.get(thread_id=thread.id, run_id=run.id)
        
        try:
            # Fetch steps
            steps = client.agents.list_run_steps(thread_id=thread.id, run_id=run.id)
            
            # Iterate safely
            steps_data = list(steps) if hasattr(steps, '__iter__') else steps.data
            sorted_steps = sorted(steps_data, key=lambda x: getattr(x, 'created_at', 0))
            
            for step in sorted_steps:
                if step.id not in processed_steps:
                    # 1. Try to extract Bing Query using the Universal Extractor
                    log_msg = extract_bing_query(step)
                    
                    if log_msg:
                        print(log_msg)
                    elif getattr(step, 'type', '') == 'message_creation':
                        print(f"  📝 [DRAFTING] Synthesizing Report Part...")
                    else:
                        # Fallback: Print type just so we know it's alive
                        # print(f"  [ACTIVITY] {getattr(step, 'type', 'Unknown')}")
                        pass

                    processed_steps.add(step.id)
        except Exception as e:
            # Don't crash on visualization errors, just keep polling
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
                                    url_citation = getattr(ann, 'url_citation', None)
                                    if url_citation:
                                        url = getattr(url_citation, 'url', None)
                                        if url: unique_urls.add(url)
                            
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