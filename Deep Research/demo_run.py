import os
import time
from typing import Optional, Set
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
    print(f"\n--- DEFENSE INTELLIGENCE TERMINAL [Safe Pseudo-Streaming] ---")
    
    client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential()
    )

    # --- Connection Setup ---
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
    
    # Create Thread & Message
    thread = client.agents.threads.create()
    client.agents.messages.create(
        thread_id=thread.id,
        role=MessageRole.USER,
        content=user_query
    )

    print(f"[*] Starting Run (Background Mode)...")
    # CRITICAL: We do NOT use stream() here. We use create() to run in background.
    run = client.agents.runs.create(thread_id=thread.id, agent_id=agent.id)

    start_time = time.time()
    
    print(f"\n🚀 MONITORING AGENT THREAD (Safe Polling)...")
    print("=" * 60)

    # --- SAFE PSEUDO-STREAMING LOGIC ---
    printed_message_ids: Set[str] = set()
    
    while run.status in ["queued", "in_progress", "requires_action"]:
        time.sleep(3) # Wait 3 seconds to avoid API throttling
        
        try:
            # 1. Fetch the LATEST messages (reversed so we print oldest first)
            # We fetch up to 20 to ensure we catch bursts of updates
            messages = client.agents.messages.list(
                thread_id=thread.id,
                order="asc", # Get oldest first to maintain chronological order
                limit=50 
            )
            
            # Safe list conversion
            msg_list = list(messages) if hasattr(messages, '__iter__') else messages.data

            # 2. Iterate through messages
            for msg in msg_list:
                # If we haven't seen this message ID yet...
                if msg.id not in printed_message_ids:
                    
                    # Only print Assistant (Agent) messages
                    if msg.role == MessageRole.ASSISTANT:
                        
                        # Print every text block in the new message
                        for content in getattr(msg, 'content', []):
                            if getattr(content, 'type', '') == "text":
                                text_val = getattr(content, 'text', None).value
                                if text_val:
                                    print(f"\n🧠 [AGENT UPDATE] {text_val}")
                                    
                                    # Check for metadata (Thoughts)
                                    meta = getattr(msg, 'metadata', {})
                                    if meta and 'cot_summary' in meta:
                                        print(f"   (Thought: {meta['cot_summary']})")

                    # Mark as seen
                    printed_message_ids.add(msg.id)

            # 3. Refresh Run Status
            run = client.agents.runs.get(thread_id=thread.id, run_id=run.id)
            
        except Exception as e:
            # If a poll fails, just wait and try again. Do NOT crash.
            pass

    print("\n" + "="*80)
    
    if run.status == "completed":
        duration = time.time() - start_time
        print(f"✅ COMPLETE ({duration:.1f}s)")
        
        # --- FINAL CLEAN REPORT & AUDIT ---
        # We fetch one last time to ensure we have the absolute final text
        messages = client.agents.messages.list(thread_id=thread.id, order="desc", limit=1)
        messages_list = list(messages) if hasattr(messages, '__iter__') else messages.data
        
        if messages_list:
            last_msg = messages_list[0]
            if last_msg.role == MessageRole.ASSISTANT:
                for content in getattr(last_msg, 'content', []):
                    if getattr(content, 'type', '') == "text":
                        text_obj = getattr(content, 'text', None)
                        if text_obj:
                            
                            # AUDIT
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
                                print(f"⚠️  Result: {len(unique_urls)} sources (Missed Target).")
                            else:
                                print(f"🏆 SUCCESS: {len(unique_urls)} sources found!")
    else:
        print(f"\n❌ FAILED: {run.last_error}")

    try:
        client.agents.delete_agent(agent.id)
    except:
        pass

if __name__ == "__main__":
    main()