import os
import time
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
"""

# --- THE MISSING HELPER FUNCTION FROM THE VIDEO ---
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
        messages = client.agents.messages.list(
            thread_id=thread_id,
            limit=1,
            order="desc"
        )
        
        msg_list = list(messages) if hasattr(messages, '__iter__') else messages.data
        if not msg_list:
            return last_message_id

        latest_msg = msg_list[0]

        if latest_msg.id != last_message_id and latest_msg.role == AgentRole.AGENT:
            for content in latest_msg.content:
                if hasattr(content, 'text'):
                    text_val = content.text.value
                    print(f"\n🧠 [AGENT UPDATE] {text_val}")
                    if hasattr(content, 'metadata') and 'cot_summary' in content.metadata:
                        print(f"   (Thought: {content.metadata['cot_summary']})")
            return latest_msg.id
            
    except Exception:
        pass
    
    return last_message_id

def main():
    print(f"\n--- DEFENSE INTELLIGENCE TERMINAL [Video Implementation] ---")
    
    client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential()
    )

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

    agent = client.agents.create_agent(
        model=MODEL_DEPLOYMENT,
        name="defense-deep-researcher",
        instructions=COMBINED_INSTRUCTIONS,
        tools=[deep_tool]
    )

    user_query = "Conduct a comprehensive market analysis on 'Anduril Industries'. CONSTRAINT: 20 UNIQUE SOURCES."
    
    thread = client.agents.threads.create()
    client.agents.messages.create(
        thread_id=thread.id,
        role=MessageRole.USER,
        content=user_query
    )

    print(f"[*] Starting Deep Research Run...")
    run = client.agents.runs.create(thread_id=thread.id, agent_id=agent.id)

    # --- POLLING LOOP WITH MESSAGE CHECK ---
    last_msg_id = None
    
    while run.status in ["queued", "in_progress", "requires_action"]:
        time.sleep(3) 
        last_msg_id = fetch_and_print_new_agent_response(client, thread.id, last_msg_id)
        run = client.agents.runs.get(thread_id=thread.id, run_id=run.id)

    print("\n" + "="*80)
    
    # --- THIS WAS MISSING: THE FINAL REPORT & SOURCE CHECK ---
    if run.status == "completed":
        print(f"✅ COMPLETE")
        
        # We fetch the messages one last time to get the FINAL, clean report
        messages = client.agents.messages.list(thread_id=thread.id)
        messages_list = list(messages) if hasattr(messages, '__iter__') else messages.data
        
        for msg in messages_list:
            if getattr(msg, 'role', '') == "assistant":
                for content in getattr(msg, 'content', []):
                    if getattr(content, 'type', '') == "text":
                        text_obj = getattr(content, 'text', None)
                        if text_obj:
                            # 1. Print the Final Report (Cleanly)
                            print("\n📜 FINAL INTELLIGENCE REPORT:")
                            print(text_obj.value)
                            
                            # 2. AUDIT THE SOURCES (Crucial for your prompt)
                            print("\n" + "-"*40)
                            print(f"📊 SOURCE VERIFICATION:")
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
                                print(f"⚠️  WARNING: Target Missed ({len(unique_urls)}/20)")
                            else:
                                print(f"🏆 TARGET HIT: {len(unique_urls)} sources confirmed.")
                break
    else:
        print(f"\n❌ FAILED: {run.last_error}")

    try:
        client.agents.delete_agent(agent.id)
    except:
        pass

if __name__ == "__main__":
    main()