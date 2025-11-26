import os
import time
import json
import logging
from typing import Optional
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import (
    DeepResearchToolDefinition,
    DeepResearchDetails,
    DeepResearchBingGroundingConnection,
    MessageRole,
    AgentRole
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

# --- HELPER FUNCTION (From Video Implementation) ---
def fetch_and_print_new_agent_response(
    client: AIProjectClient, 
    thread_id: str, 
    last_message_id: Optional[str] = None
) -> Optional[str]:
    """
    Polls for NEW messages from the agent while the run is active.
    Deep Research emits 'cot_summary' updates as messages during execution.
    """
    try:
        # Get the latest message
        messages = client.agents.messages.list(
            thread_id=thread_id,
            limit=1,
            order="desc"
        )
        
        # Safe iteration (handle iterator vs list)
        msg_list = list(messages) if hasattr(messages, '__iter__') else messages.data
        if not msg_list:
            return last_message_id

        latest_msg = msg_list[0]

        # Only process if it's a NEW message and from the AGENT
        if latest_msg.id != last_message_id and latest_msg.role == AgentRole.AGENT:
            
            # Print the content (This is where 'cot_summary' appears)
            for content in latest_msg.content:
                if hasattr(content, 'text'):
                    text_val = content.text.value
                    print(f"\n🧠 [AGENT UPDATE] {text_val}")
                    
                    # Check for explicit CoT metadata if available
                    if hasattr(content, 'metadata') and 'cot_summary' in content.metadata:
                        print(f"   (Thought: {content.metadata['cot_summary']})")
            
            return latest_msg.id
            
    except Exception as e:
        # Suppress polling errors to keep terminal clean
        pass
    
    return last_message_id

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

    start_time = time.time()
    
    print(f"\n🚀 MONITORING AGENT BRAIN (Real-time Updates)...\n")

    # --- REPLACED: NEW MESSAGE POLLING LOOP ---
    last_msg_id = None
    
    while run.status in ["queued", "in_progress", "requires_action"]:
        time.sleep(3) # Wait between checks
        
        # 1. Check for NEW MESSAGES (The "Thinking" Updates)
        last_msg_id = fetch_and_print_new_agent_response(client, thread.id, last_msg_id)
        
        # 2. Refresh Run Status
        run = client.agents.runs.get(thread_id=thread.id, run_id=run.id)

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