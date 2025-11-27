import os
import time
import traceback
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

def extract_text_from_message(msg) -> Optional[str]:
    """
    Safely extract text content from a message object.
    Returns None if no text content is found.
    """
    try:
        content_items = getattr(msg, 'content', [])
        if not content_items:
            return None
        
        text_parts = []
        for content in content_items:
            content_type = getattr(content, 'type', None)
            if content_type == "text":
                text_obj = getattr(content, 'text', None)
                if text_obj:
                    text_val = getattr(text_obj, 'value', None)
                    if text_val:
                        text_parts.append(text_val)
        
        return "\n".join(text_parts) if text_parts else None
    except Exception as e:
        print(f"[DEBUG] extract_text_from_message error: {e}")
        return None

def print_message_with_metadata(msg, is_new: bool = True):
    """
    Print a message with proper formatting and metadata.
    """
    try:
        text = extract_text_from_message(msg)
        if not text:
            return
        
        # Determine message type
        prefix = "🧠 [NEW UPDATE]" if is_new else "📄 [MESSAGE]"
        
        # Print main content
        print(f"\n{prefix}")
        print("-" * 60)
        print(text)
        
        # Print metadata if available (Chain of Thought summaries)
        metadata = getattr(msg, 'metadata', {})
        if metadata:
            if 'cot_summary' in metadata:
                print(f"\n💭 Thought Process: {metadata['cot_summary']}")
            if 'reasoning' in metadata:
                print(f"🔍 Reasoning: {metadata['reasoning']}")
        
        print("-" * 60)
    except Exception as e:
        print(f"[DEBUG] print_message_with_metadata error: {e}")

def extract_citations_from_message(msg) -> Set[str]:
    """
    Extract unique URLs from message annotations.
    """
    unique_urls = set()
    try:
        content_items = getattr(msg, 'content', [])
        for content in content_items:
            content_type = getattr(content, 'type', None)
            if content_type == "text":
                text_obj = getattr(content, 'text', None)
                if text_obj:
                    annotations = getattr(text_obj, 'annotations', [])
                    for ann in annotations:
                        url_citation = getattr(ann, 'url_citation', None)
                        if url_citation:
                            url = getattr(url_citation, 'url', None)
                            if url:
                                unique_urls.add(url)
    except Exception as e:
        pass  # Silent fail for citation extraction
    
    return unique_urls

def is_agent_message(msg) -> bool:
    """
    Check if a message is from the agent/assistant.
    Handles various possible role representations.
    """
    try:
        msg_role = getattr(msg, 'role', None)
        if msg_role is None:
            return False
        
        # Get the actual string value of the role
        role_str = str(msg_role).lower()
        
        # Check against various possible values
        # Azure might use 'agent', 'assistant', or other values
        agent_keywords = ['agent', 'assistant', 'bot']
        return any(keyword in role_str for keyword in agent_keywords)
    except Exception as e:
        return False

def main():
    print(f"\n{'='*80}")
    print(f"🎯 DEFENSE INTELLIGENCE TERMINAL - Azure AI Deep Research")
    print(f"{'='*80}\n")
    
    # Initialize client
    client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential()
    )

    # --- Connection Setup ---
    print(f"[1/5] 🔌 Establishing Bing Search connection...")
    try:
        bing_conn_obj = client.connections.get(connection_name=BING_CONNECTION)
        bing_conn_id = bing_conn_obj.id
        print(f"      ✓ Connected: {bing_conn_id[:50]}...")
    except Exception as e:
        bing_conn_id = BING_CONNECTION
        print(f"      ✓ Using connection name: {BING_CONNECTION}")

    # --- Tool Definition ---
    print(f"[2/5] 🛠️  Configuring Deep Research tool...")
    deep_tool = DeepResearchToolDefinition(
        deep_research=DeepResearchDetails(
            deep_research_model=DEEP_MODEL,
            deep_research_bing_grounding_connections=[
                DeepResearchBingGroundingConnection(connection_id=bing_conn_id)
            ]
        )
    )
    print(f"      ✓ Tool configured with model: {DEEP_MODEL}")

    # --- Agent Creation ---
    print(f"[3/5] 🤖 Deploying Deep Research agent...")
    agent = client.agents.create_agent(
        model=MODEL_DEPLOYMENT,
        name="defense-deep-researcher",
        instructions=COMBINED_INSTRUCTIONS,
        tools=[deep_tool]
    )
    print(f"      ✓ Agent deployed: {agent.id}")

    # --- Query Definition ---
    user_query = """
    Conduct a comprehensive market analysis on "Anduril Industries".
    REQUIREMENTS:
    1. RECOMPETES: Top 3 contracts ending 2025-2026.
    2. PROTESTS: Identify 2 specific GAO protest decisions.
    3. COMPLIANCE: CMMC / NIST 800-171 status.
    CONSTRAINT: 20 UNIQUE SOURCES. Verify everything.
    """
    
    # --- Thread & Message Creation ---
    print(f"[4/5] 💬 Creating conversation thread...")
    thread = client.agents.threads.create()
    print(f"      ✓ Thread created: {thread.id}")
    
    client.agents.messages.create(
        thread_id=thread.id,
        role=MessageRole.USER,
        content=user_query
    )
    print(f"      ✓ Query submitted")

    # --- Run Execution ---
    print(f"[5/5] 🚀 Initiating Deep Research run...\n")
    run = client.agents.runs.create(thread_id=thread.id, agent_id=agent.id)

    start_time = time.time()
    
    print(f"{'='*80}")
    print(f"📡 LIVE PROGRESS MONITORING (Polling every 1.5s)")
    print(f"{'='*80}\n")

    # --- PSEUDO-STREAMING WITH SAFE ITERATION ---
    printed_message_ids: Set[str] = set()
    last_status = None
    poll_count = 0
    all_citations: Set[str] = set()
    
    while run.status in ["queued", "in_progress", "requires_action"]:
        poll_count += 1
        
        # Status indicator (only print if status changed)
        if run.status != last_status:
            status_icon = "⏳" if run.status == "queued" else "⚙️" if run.status == "in_progress" else "❓"
            print(f"\n{status_icon} Status: {run.status.upper()}")
            last_status = run.status
        
        # Show activity indicator every 5 polls
        if poll_count % 5 == 0:
            elapsed = time.time() - start_time
            print(f"   ⏱️  Elapsed: {elapsed:.1f}s | Messages tracked: {len(printed_message_ids)}")
        
        try:
            # CRITICAL: Don't convert to list - iterate directly
            # This avoids blocking on the paginator
            messages = client.agents.messages.list(
                thread_id=thread.id,
                order="asc",
                limit=100
            )
            
            # Iterate the paginator directly - DO NOT call list()
            # Process messages as they come
            for msg in messages:
                # Skip if already printed
                if msg.id in printed_message_ids:
                    continue
                
                # Check if this is an agent message
                if is_agent_message(msg):
                    print_message_with_metadata(msg, is_new=True)
                    
                    # Extract citations from this message
                    msg_citations = extract_citations_from_message(msg)
                    if msg_citations:
                        all_citations.update(msg_citations)
                        print(f"📚 Running citation count: {len(all_citations)} sources")
                
                # Mark as printed
                printed_message_ids.add(msg.id)
                
                # Break after processing to avoid blocking
                # We'll catch new messages on next poll
                break
            
            # Refresh run status
            run = client.agents.runs.get(thread_id=thread.id, run_id=run.id)
            
        except Exception as e:
            # Log error but continue
            error_msg = str(e)
            if "ASSISTANT" not in error_msg:  # Don't spam the known enum error
                print(f"⚠️  Polling error: {error_msg[:100]}")
        
        # Poll every 1.5 seconds
        time.sleep(1.5)

    # --- COMPLETION HANDLING ---
    print("\n" + "="*80)
    
    duration = time.time() - start_time
    
    if run.status == "completed":
        print(f"✅ RESEARCH COMPLETED in {duration:.1f}s ({poll_count} polls)")
        print("="*80)
        
        # Fetch final messages one more time
        print("\n📊 FINAL REPORT & CITATION AUDIT")
        print("-"*80)
        
        try:
            messages = client.agents.messages.list(
                thread_id=thread.id,
                order="desc",
                limit=10
            )
            
            # Find the last agent message (iterate directly, don't convert to list)
            final_report = None
            for msg in messages:
                if is_agent_message(msg):
                    final_report = msg
                    break
            
            if final_report:
                # Print the final report text
                final_text = extract_text_from_message(final_report)
                if final_text:
                    print(f"\n📄 FINAL REPORT:")
                    print("-"*80)
                    print(final_text)
                    print("-"*80)
                
                # Extract all citations from final report
                final_citations = extract_citations_from_message(final_report)
                all_citations.update(final_citations)
                
                # Print citation audit
                print(f"\n📚 UNIQUE SOURCES CITED:")
                print("-"*80)
                sorted_urls = sorted(list(all_citations))
                for i, url in enumerate(sorted_urls, 1):
                    print(f"  [{i:2d}] {url}")
                
                print(f"\n{'='*80}")
                print(f"📈 TOTAL UNIQUE SOURCES: {len(all_citations)}")
                
                if len(all_citations) >= 20:
                    print(f"🏆 MISSION ACCOMPLISHED - Target exceeded!")
                elif len(all_citations) >= 15:
                    print(f"✅ SUCCESS - Solid research base")
                else:
                    print(f"⚠️  BELOW TARGET - Only {len(all_citations)} sources found")
                
                print("="*80)
                
            else:
                print("⚠️  No final report found in messages")
        except Exception as e:
            print(f"⚠️  Error fetching final report: {e}")
            
    elif run.status == "failed":
        print(f"❌ RUN FAILED after {duration:.1f}s")
        if hasattr(run, 'last_error') and run.last_error:
            print(f"\nError Details:")
            print(f"  Code: {getattr(run.last_error, 'code', 'Unknown')}")
            print(f"  Message: {getattr(run.last_error, 'message', 'Unknown')}")
    else:
        print(f"⚠️  RUN ENDED WITH STATUS: {run.status} (after {duration:.1f}s)")

    # --- Cleanup ---
    print(f"\n🧹 Cleaning up resources...")
    try:
        client.agents.delete_agent(agent.id)
        print(f"   ✓ Agent deleted")
    except Exception as e:
        print(f"   ⚠️  Could not delete agent: {e}")

    print(f"\n{'='*80}")
    print(f"🏁 SESSION COMPLETE")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    main()