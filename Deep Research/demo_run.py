import os
import time
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import AgentEventHandler
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

# --- THE "PARANOID" PROMPT (Proven to get ~11-14 sources, aiming for 20) ---
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

# --- THE MATRIX-STYLE EVENT HANDLER ---
class DeepResearchEventHandler(AgentEventHandler):
    """
    This handler hooks into the live server events to print thoughts/searches 
    the moment they happen, replicating the Microsoft Demo experience.
    """
    def __init__(self):
        super().__init__()
        self.last_printed_step = None

    def on_run_step_created(self, step):
        # When a new "Brain Step" starts (e.g., Searching, Thinking)
        if step.type == "tool_calls":
            print(f"\n  ⚡ [ACTIVATING TOOL] Analyzing request...", end="", flush=True)
        elif step.type == "message_creation":
            print(f"\n  📝 [DRAFTING] Synthesizing report...", end="", flush=True)

    def on_run_step_delta(self, delta, snapshot):
        # This captures the "Streaming Updates" inside a step
        if delta.step_details and delta.step_details.tool_calls:
            for tool_call in delta.step_details.tool_calls:
                # Check if it's a Bing Search (Grounding)
                if getattr(tool_call, 'bing_grounding', None):
                    query = getattr(tool_call.bing_grounding, 'query', None)
                    if query:
                        print(f"\n  🌐 [BING SEARCH] {query}")
                
                # Check if it's the Deep Research "Reasoning" (Chain of Thought)
                # Note: Sometimes o3 emits thoughts as 'code_interpreter' logs or specific function args
                elif getattr(tool_call, 'function', None):
                    args = getattr(tool_call.function, 'arguments', '')
                    if args:
                        # Clean up the raw JSON string for display
                        clean_args = args.replace('\n', ' ').strip()[:100]
                        print(f"\r  🧠 [THOUGHT] {clean_args}...", end="", flush=True)

    def on_message_delta(self, delta, snapshot):
        # This captures the final text being typed out
        if delta.content:
            for content_part in delta.content:
                if content_part.type == "text":
                    # Print text as it streams (The "Typewriter" effect)
                    print(content_part.text.value, end="", flush=True)

    def on_error(self, error):
        print(f"\n  ❌ [STREAM ERROR] {error}")

def main():
    print(f"\n--- DEFENSE INTELLIGENCE TERMINAL [Streaming Mode] ---")
    
    # 1. Initialize Client
    client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential()
    )

    # 2. Define Tool
    deep_tool = DeepResearchToolDefinition(
        deep_research=DeepResearchDetails(
            deep_research_model=DEEP_MODEL,
            deep_research_bing_grounding_connections=[
                DeepResearchBingGroundingConnection(connection_id=BING_CONNECTION)
            ]
        )
    )

    # 3. Create Agent
    print(f"[*] Deploying Streaming Agent...")
    agent = client.agents.create_agent(
        model=MODEL_DEPLOYMENT,
        name="defense-streamer",
        instructions=COMBINED_INSTRUCTIONS,
        tools=[deep_tool]
    )

    # 4. Hardcoded Prompt (The Stress Test)
    user_query = """
    Conduct a comprehensive market analysis on "Anduril Industries".
    REQUIREMENTS:
    1. RECOMPETES: Top 3 contracts ending 2025-2026.
    2. PROTESTS: Identify 2 specific GAO protest decisions.
    3. COMPLIANCE: CMMC / NIST 800-171 status.
    
    CONSTRAINT: 20 UNIQUE SOURCES. Verify everything.
    """
    
    # 5. Start Thread
    thread = client.agents.threads.create()
    client.agents.messages.create(
        thread_id=thread.id,
        role=MessageRole.USER,
        content=user_query
    )

    print(f"[*] Prompt Sent. Opening Data Stream...\n")
    print("="*80)

    # 6. THE STREAMING EXECUTION
    # This replaces the "While Loop" with a live connection
    with client.agents.create_stream(
        thread_id=thread.id,
        assistant_id=agent.id,
        event_handler=DeepResearchEventHandler() # <--- The Magic Hook
    ) as stream:
        stream.until_done()

    print("\n" + "="*80)
    print(f"✅ STREAM COMPLETE")

    # 7. Final Audit (To verify the 20-source count)
    print(f"\n📊 PERFORMING FINAL CITATION AUDIT...")
    messages = client.agents.messages.list(thread_id=thread.id)
    messages_list = list(messages) if hasattr(messages, '__iter__') else messages.data
    
    for msg in messages_list:
        if getattr(msg, 'role', '') == "assistant":
            for content in getattr(msg, 'content', []):
                if getattr(content, 'type', '') == "text":
                    text_obj = getattr(content, 'text', None)
                    if text_obj:
                        unique_urls = set()
                        annotations = getattr(text_obj, 'annotations', [])
                        if annotations:
                            for ann in annotations:
                                if hasattr(ann, 'url_citation'):
                                    url = getattr(ann.url_citation, 'url', None)
                                    if url: unique_urls.add(url)
                        
                        print(f"Total UNIQUE Sources Found: {len(unique_urls)}")
                        if len(unique_urls) >= 15:
                            print(f"🏆 SUCCESS: {len(unique_urls)} sources.")
                        else:
                            print(f"⚠️  WARNING: Only {len(unique_urls)} sources.")
            break

    try:
        client.agents.delete_agent(agent.id)
    except:
        pass

if __name__ == "__main__":
    main()