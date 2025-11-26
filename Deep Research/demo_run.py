#!/usr/bin/env python3
"""
Microsoft Demo: Deep Research Tool with Defense Sector Intelligence
This script replicates Microsoft's demo showing the step-by-step research process.
"""
import os
import time
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

# Load environment variables
load_dotenv()

# --- CONFIGURATION ---
PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
MODEL_DEPLOYMENT = os.getenv("MODEL_DEPLOYMENT_NAME")       # gpt-4o (The Orchestrator)
DEEP_MODEL = os.getenv("DEEP_RESEARCH_MODEL_DEPLOYMENT_NAME") # o3-deep-research (The Brain)
BING_CONNECTION = os.getenv("BING_CONNECTION_NAME")

# --- THE HYBRID PROMPT ---
# PART 1: The "Microsoft Demo" Persona (How to behave)
# PART 2: Your "Defense.md" Constraints (What to find)
COMBINED_INSTRUCTIONS = """
# ROLE: Senior Defense Sector BD Intelligence Agent
You are an expert research analyst at Protiviti specializing in U.S. Defense sector opportunities.

# CORE OBJECTIVE (Deep Research Mode)
You are utilizing the "Deep Research" capability. This means you must NOT stop at the first answer.
You are expected to:
1. Plan a multi-step research strategy.
2. Execute initial searches.
3. CRITICALLY EVALUATE the findings. If they are thin, generic, or lack citations, you MUST loop and search again.
4. Synthesize disparate data points (e.g., connecting a GAO protest to a generic SAM.gov award).

# TARGETS & SIGNALS (From Defense.md)
Focus your research on these High-Value Signals:
- Active RFI/RFP Releases (Immediate opportunity)
- Recompete Windows (Incumbent vulnerability 12-18 months out)
- CMMC & Cyber Compliance Mandates (NIST 800-171)
- IV&V Requirements (Independent Verification & Validation)

# CRITICAL CONSTRAINTS (The "Greedy" Rules)
1. **SOURCE QUANTITY**: You MUST aim for 15+ distinct, verifiable citations.
   - If you have fewer than 10, your research is INCOMPLETE. Continue searching.
2. **SOURCE HIERARCHY**:
   - TIER 1 (Must Have): SAM.gov, FPDS.gov, GAO.gov, defense.gov.
   - TIER 2 (Context): Defense News, Breaking Defense, GovConWire.
3. **VERIFIABILITY**: Every claim (dates, dollar values, contract #s) must have a clickable citation.
4. **NO HALLUCINATION**: If you cannot find a specific contract number, state that clearly. Do not guess.

# OUTPUT FORMAT
Provide a comprehensive "Executive Briefing" style report with:
- Executive Summary
- Key Signals Detected
- Detailed Opportunity Analysis (Incumbent, Value, Timeline)
- Recommended Actions (Immediate, Week 2, Week 3)
- CITATIONS SECTION (List all 15+ sources)
"""

def print_step_details(step):
    """
    Visualizes the 'Brain' of the agent in the terminal.
    Replicates the 'scrolling text' effect from the Azure demo.
    """
    try:
        step_type = getattr(step, 'type', None)
        
        # 1. VISUALIZE SEARCHES (The "Doing")
        if step_type == "tool_calls":
            step_details = getattr(step, 'step_details', None)
            if step_details:
                tool_calls = getattr(step_details, 'tool_calls', [])
                for tool_call in tool_calls:
                    tool_type = getattr(tool_call, 'type', '')
                    if tool_type == 'bing_grounding':
                        bing_grounding = getattr(tool_call, 'bing_grounding', None)
                        if bing_grounding:
                            query = getattr(bing_grounding, 'query', 'Unknown query')
                            print(f"  [BING SEARCH] Query: {query}")
                    elif getattr(tool_call, 'function', None):
                        # This is the Deep Research tool itself thinking
                        print(f"  [DEEP RESEARCH] Planning next research phase...")

        # 2. VISUALIZE THOUGHTS (The "Thinking")
        elif step_type == "message_creation":
            print(f"  [AGENT] Drafting findings...")
            
    except Exception as e:
        print(f"  [DEBUG] Error displaying step: {e}")

def main():
    print(f"\n--- DEFENSE INTELLIGENCE TERMINAL [Microsoft Demo Mode] ---")
    
    # 1. Initialize Client (using same method as deep_research_client.py)
    credential = DefaultAzureCredential()
    client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=credential
    )

    # 2. Configure Deep Research Tool
    deep_tool = DeepResearchToolDefinition(
        deep_research=DeepResearchDetails(
            deep_research_model=DEEP_MODEL,
            deep_research_bing_grounding_connections=[
                DeepResearchBingGroundingConnection(connection_id=BING_CONNECTION)
            ]
        )
    )

    # 3. Create the Agent (The "Brain")
    print(f"[*] Deploying Agent with Defense.md Logic...")
    try:
        agent = client.agents.create_agent(
            model=MODEL_DEPLOYMENT,
            name="defense-deep-researcher",
            instructions=COMBINED_INSTRUCTIONS, # <--- The Hybrid Prompt
            tools=[deep_tool]
        )
        print(f"[*] Agent Ready: {agent.id}")
    except Exception as e:
        print(f"[ERROR] Failed to create agent: {e}")
        print("Check that:")
        print("  - PROJECT_ENDPOINT is set correctly")
        print("  - MODEL_DEPLOYMENT_NAME is deployed in your AI Project")
        print("  - DEEP_RESEARCH_MODEL_DEPLOYMENT_NAME is deployed")
        print("  - BING_CONNECTION_NAME is correct")
        return

    # 4. Get User Query
    user_query = input("\nEnter Defense Target (e.g., 'Analyze Anduril Industries contracts'): ")
    
    # 5. Start the Thread
    thread = client.agents.threads.create()
    client.agents.messages.create(
        thread_id=thread.id,
        role=MessageRole.USER,
        content=user_query
    )

    # 6. Run & Stream (The "Demo Loop")
    print(f"\nSTARTING DEEP RESEARCH RUN... (This may take 2-5 minutes)\n")
    
    run = client.agents.runs.create(
        thread_id=thread.id,
        agent_id=agent.id,
    )

    processed_steps = set()
    start_time = time.time()

    # --- THE TERMINAL VISUALIZATION LOOP ---
    while run.status in ["queued", "in_progress", "requires_action"]:
        time.sleep(1.5) # Poll frequency
        
        # Update Run Status
        run = client.agents.runs.get(thread_id=thread.id, run_id=run.id)
        
        # Fetch Steps (The "Brain Activity")
        try:
            steps = client.agents.runs.list_steps(thread_id=thread.id, run_id=run.id)
            
            # Handle different response formats
            steps_list = list(steps) if hasattr(steps, '__iter__') else (steps.data if hasattr(steps, 'data') else [])
            
            # Sort chronologically to show flow
            sorted_steps = sorted(steps_list, key=lambda x: getattr(x, 'created_at', 0))
            
            for step in sorted_steps:
                step_id = getattr(step, 'id', None)
                if step_id and step_id not in processed_steps:
                    print_step_details(step) # <--- The Visualizer Function
                    processed_steps.add(step_id)
        except Exception as e:
            print(f"  [DEBUG] Error fetching steps: {e}")

    # 7. Output Final Report
    if run.status == "completed":
        duration = time.time() - start_time
        print(f"\nRESEARCH COMPLETE ({duration:.1f}s)")
        print("\n" + "="*80)
        
        messages = client.agents.messages.list(thread_id=thread.id)
        
        # Handle messages (can be PagedList or similar)
        messages_list = list(messages) if hasattr(messages, '__iter__') else messages.data
        
        for msg in messages_list:
            if getattr(msg, 'role', '') == "assistant":
                # Print the final report text
                for content in getattr(msg, 'content', []):
                    if getattr(content, 'type', '') == "text":
                        text_obj = getattr(content, 'text', None)
                        if text_obj:
                            text_value = getattr(text_obj, 'value', str(text_obj))
                            print(text_value)
                            
                            # Explicitly verify citations
                            print("\n" + "-"*40)
                            print(f"CITATION AUDIT:")
                            count = 0
                            annotations = getattr(text_obj, 'annotations', [])
                            if annotations:
                                for ann in annotations:
                                    url_citation = getattr(ann, 'url_citation', None)
                                    if url_citation:
                                        url = getattr(url_citation, 'url', None)
                                        if url:
                                            count += 1
                                            print(f" [{count}] {url}")
                            print(f"\nTotal Sources Found: {count}")
                break
    else:
        print(f"\nRUN FAILED: {run.last_error}")

    # Cleanup
    try:
        client.agents.delete_agent(agent.id)
        print("\n[*] Agent cleaned up.")
    except:
        pass

if __name__ == "__main__":
    main()

